import json
import logging
import re
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import xlsxwriter

from src.labfolder_migration.fetcher import LabFolderFetcher
from src.labfolder_migration.importer import Importer


class Transformer:
    def __init__ (self, entries: List[Dict[str, Any]],
                  fetcher: LabFolderFetcher, importer: Importer,
                  logger: logging.Logger = None, ) -> None:
        self._entries = pd.DataFrame(entries)
        self._fetcher = fetcher
        self._importer = importer
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def transform_experiment_data (self) -> Dict[Any, List[Dict[str, Any]]]:
        experiment_data: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
        for _, row in self._entries.iterrows():
            record = {
                "name"                 : f"{row['author'].get('first_name')} {row['author'].get('last_name')}",
                "entry_creation_date"  : row["creation_date"],
                "elements"             : row["elements"],
                "entry_number"         : row["entry_number"],
                "entry_id"             : row["id"],
                "last_editor_name"     : f"{row['last_editor'].get('first_name')} {row['last_editor'].get('last_name')}",
                "tags"                 : row["tags"],
                "entry_title"          : row["title"],
                "last_edited"          : row["version_date"],
                "project_creation_date": row["project"].get("creation_date"),
                "labfolder_project_id" : row["project"].get("id"),
                "number_of_entries"    : row["project"].get(
                    "number_of_entries"),
                "project_title"        : row["project"].get("title"),
                "project_owner"        : f"{row['author'].get('first_name')} {row['author'].get('last_name')}",
                "Labfolder_ID"         : row["project"].get("id"),
                }
            experiment_data[row["project_id"]].append(record)
        return experiment_data

    def transform_projects_content (self, project: List[Dict[str, Any]],
                                    max_entries: int = None,
                                    category: int = 38) -> List[str]:
        title, tags = self.collect_title_and_tags(project)
        exp_id = self._importer.create_experiment(title, tags)
        entry_htmls: List[str] = []

        for idx, entry in enumerate(project, start=1):
            if max_entries and idx > max_entries:
                break
            entry_htmls.append(self.build_entry_html(entry, exp_id))

        entry_htmls.append(self.build_footer_html(project[0]))
        full_body = "".join(entry_htmls)
        extra_fields = self.build_extra_fields(project[0])
        self._importer.patch_experiment(exp_id, full_body, category, uid=1130,
                                        extra_fields=extra_fields)
        return entry_htmls

    def collect_title_and_tags (self, project: List[Dict[str, Any]]) -> Tuple[
        str, List[str]]:
        title = project[0].get("project_title", "")
        tags: List[str] = []
        for entry in project:
            tags.extend(entry.get("tags", np.array([])).tolist())
        return title, tags

    def build_entry_html (self, entry: Dict[str, Any], exp_id: str) -> str:
        header = (
            f"\n----Entry {entry['entry_number']} of {entry['number_of_entries']}----<br>"
            f"<strong>Entry: {entry['entry_title']} (labfolder id: {entry['entry_id']})</strong><br>")
        blocks: List[str] = []

        for element in entry.get("elements", []):
            if not element:
                continue
            typ = element.get("type")

            if typ == "TABLE":
                metadata = self._fetcher.fetch_table(element)
                if metadata:
                    try:
                        excel_files = self._export_table_to_excel(metadata)
                        for sheet_name, xlsx_path in excel_files:
                            self._importer.upload_file(exp_id, xlsx_path)
                            blocks.append(
                                f"<p>[Attached TABLE sheet '{sheet_name}': {xlsx_path.name}]</p>")
                    except Exception as e:
                        self.logger.error(
                            "TABLE Excel conversion/upload failed for %s: %s",
                            metadata.get("id"), e, )
                        blocks.append(
                            f"<p>[Failed to convert/upload TABLE to Excel: {metadata.get('id')}]</p>")
                else:
                    blocks.append("<p>[Empty or invalid TABLE]</p>")

            elif typ == "WELL_PLATE":
                metadata = self._fetcher.fetch_well_plate(element)
                if metadata:
                    try:
                        excel_files = self._export_well_plate_to_excel(
                            metadata)
                        if excel_files:
                            for sheet_name, xlsx_path in excel_files:
                                self._importer.upload_file(exp_id, xlsx_path)
                                blocks.append(
                                    f"<p>[Attached WELL_PLATE sheet '{sheet_name}': {xlsx_path.name}]</p>")
                        else:
                            blocks.append(
                                "<p>[No data to convert for WELL_PLATE]</p>")
                    except Exception as e:
                        self.logger.error(
                            "WELL_PLATE Excel conversion/upload failed for %s: %s",
                            metadata.get("id"), e, )
                        blocks.append(
                            f"<p>[Failed to convert/upload WELL_PLATE to Excel: {metadata.get('id')}]</p>")
                else:
                    blocks.append("<p>[Empty or invalid WELL_PLATE]</p>")

            elif typ == "TEXT":
                try:
                    text = self._fetcher.fetch_text(element)
                    blocks.append(f"<pre>{text}</pre>")
                except Exception as e:
                    self.logger.error("TEXT fetch failed for %s: %s",
                                      element.get("id"), e)
                    blocks.append(
                        f"<p>[Failed to fetch TEXT: {element.get('id')}]</p>")

            elif typ == "FILE":
                path = self._fetcher.fetch_file(element)
                if path:
                    try:
                        self._importer.upload_file(exp_id, path)
                        blocks.append(f"<p>[Attached FILE: {path.name}]</p>")
                    except Exception as e:
                        self.logger.error("FILE upload failed for %s: %s",
                                          path.name, e)
                        blocks.append(
                            f"<p>[Failed to attach FILE: {element.get('id')}]</p>")

            elif typ == "IMAGE":
                path = self._fetcher.fetch_image(element)
                if path:
                    try:
                        self._importer.upload_file(exp_id, path)
                        blocks.append(f"<p>[Attached IMAGE: {path.name}]</p>")
                    except Exception as e:
                        self.logger.error("IMAGE upload failed for %s: %s",
                                          path.name, e)
                        blocks.append(
                            f"<p>[Failed to attach IMAGE: {element.get('id')}]</p>")

            elif typ == "DATA":
                try:
                    data = self._fetcher.fetch_data(element)
                    rows = [(f"<tr><td>{d.get('title')}</td>"
                             f"<td>{d.get('value')}</td>"
                             f"<td>{d.get('unit')}</td></tr>") for d in
                            data.get("data_elements", [])]
                    table_html = (
                            "<table><tr><th>Title</th><th>Value</th><th>Unit</th></tr>" + "".join(
                        rows) + "</table>")
                    blocks.append(table_html)
                except Exception as e:
                    self.logger.error("DATA fetch failed for %s: %s",
                                      element.get("id"), e)
                    blocks.append(
                        f"<p>[Failed to fetch DATA: {element.get('id')}]</p>")

            else:
                self.logger.warning("Skipping element %s of type %s",
                                    element.get("id"), typ)
                blocks.append(f"<p>[Skipped element: {element.get('id')}]</p>")

        dt = datetime.strptime(entry["entry_creation_date"],
                               "%Y-%m-%dT%H:%M:%S.%f%z")
        created = f"Created: {dt.date().isoformat()}<br>"
        body_html = ("\n".join(blocks) + "<br>") if blocks else ""
        return header + body_html + created + "<hr><hr>"

    def _export_table_to_excel (self, metadata: Dict[str, Any]) -> List[
        Tuple[str, Path]]:
        excel_files: List[Tuple[str, Path]] = []
        content = metadata.get("content")
        if not isinstance(content, dict):
            return excel_files

        tmp_dir = Path(tempfile.gettempdir())
        for sheet_name, sheet in content.get("sheets", {}).items():

            xlsx_path = tmp_dir / f"{sheet_name}.xlsx"
            if xlsx_path.exists():
                xlsx_path.unlink()

            wb = xlsxwriter.Workbook(str(xlsx_path))
            ws = wb.add_worksheet(sheet_name)

            data_table = sheet.get("data", {}).get("dataTable", {})
            for r in range(int(sheet.get("rowCount") or 0)):
                row = data_table.get(str(r), {}) or {}
                for c in range(int(sheet.get("columnCount") or 0)):
                    raw = row.get(str(c), {})

                    cell = raw if isinstance(raw, dict) else {
                        "value": raw
                        }

                    val = cell.get("value")
                    sty = cell.get("style", {}) or {}

                    fmt_kwargs = {}
                    m = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)",
                                 sty.get("foreColor", ""), )
                    if m:
                        r_val, g_val, b_val = map(int, m.groups())
                        fmt_kwargs[
                            "font_color"] = f"#{r_val:02x}{g_val:02x}{b_val:02x}"

                    fmt = wb.add_format(fmt_kwargs) if fmt_kwargs else None

                    if val is None:
                        if fmt:
                            ws.write_blank(r, c, None, fmt)
                        else:
                            ws.write_blank(r, c, None)
                        continue

                    if isinstance(val, (dict, list)):
                        val = json.dumps(val)

                    if fmt:
                        ws.write(r, c, val, fmt)
                    else:
                        ws.write(r, c, val)

            wb.close()
            excel_files.append((sheet_name, xlsx_path))

        return excel_files

    def _export_well_plate_to_excel (self, metadata: Dict[str, Any]) -> List[
        Tuple[str, Path]]:
        content = metadata.get("content")

        if isinstance(content, dict) and content.get("sheets"):
            return self._export_table_to_excel(metadata)

        excel_files: List[Tuple[str, Path]] = []
        if isinstance(content, str) and content.strip():
            from csv import Sniffer
            from io import StringIO

            text = content.strip()
            try:
                sep = Sniffer().sniff(text.splitlines()[0]).delimiter
            except Exception:
                sep = ","

            df = pd.read_csv(StringIO(text), sep=sep, header=None)
            tmp_dir = Path(tempfile.gettempdir())

            xlsx_path = tmp_dir / "well_plate.xlsx"
            if xlsx_path.exists():
                xlsx_path.unlink()

            wb = xlsxwriter.Workbook(str(xlsx_path))
            ws = wb.add_worksheet("well_plate")
            for r_idx, row in df.iterrows():
                for c_idx, v in enumerate(row.tolist()):
                    ws.write(r_idx, c_idx, v)
            wb.close()
            excel_files.append(("well_plate", xlsx_path))

        return excel_files

    def build_extra_fields (self, first_entry: Dict[str, Any]) -> Dict[
        str, Any]:
        return {
            "Project Owner"        : first_entry.get("project_owner"),
            "project_creation_date": first_entry.get("project_creation_date"),
            "Labfolder_ID"         : first_entry.get("Labfolder_ID"),
            }

    def build_footer_html (self, first_entry: Dict[str, Any]) -> str:
        return ('<div style="text-align: right; margin-top: 20px;">'
                '<h5 style="margin:0 0 4px 0;">Labfolder Info</h5>'
                f"Project created: {first_entry.get('project_creation_date')}<br>"
                f"Labfolder project id: {first_entry.get('labfolder_project_id')}<br>"
                f"Author: {first_entry.get('project_owner')}<br>"
                f"Last edited: {first_entry.get('last_edited')}<br>"
                "</div>")
