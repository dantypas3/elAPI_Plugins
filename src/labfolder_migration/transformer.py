# src/labfolder_migration/transformer.py
import json
import logging
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from src.labfolder_migration.fetcher import LabFolderFetcher
from src.labfolder_migration.importer import Importer

# configure logging
ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "transformer.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(str(LOG_FILE))],
)
logger = logging.getLogger(__name__)


class Transformer:
    def __init__(
        self,
        entries: List[Dict[str, Any]],
        fetcher: LabFolderFetcher,
        importer: Importer,
        logger: logging.Logger = None,
    ) -> None:
        self._entries = pd.DataFrame(entries)
        self._fetcher = fetcher
        self._importer = importer
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def transform_experiment_data(self) -> Dict[Any, List[Dict[str, Any]]]:
        experiment_data: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
        for _, row in self._entries.iterrows():
            record = {
                "name": f"{row['author'].get('first_name')} {row['author'].get('last_name')}",
                "entry_creation_date": row["creation_date"],
                "elements": row["elements"],
                "entry_number": row["entry_number"],
                "entry_id": row["id"],
                "last_editor_name": (
                    f"{row['last_editor'].get('first_name')} {row['last_editor'].get('last_name')}"
                ),
                "tags": row["tags"].tolist() if isinstance(row["tags"], np.ndarray) else row["tags"],
                "entry_title": row["title"],
                "last_edited": row["version_date"],
                "project_creation_date": row["project"].get("creation_date"),
                "labfolder_project_id": row["project"].get("id"),
                "number_of_entries": row["project"].get("number_of_entries"),
                "project_title": row["project"].get("title"),
                "project_owner": (
                    f"{row['author'].get('first_name')} {row['author'].get('last_name')}"
                ),
                "Labfolder_ID": row["project"].get("id"),
            }
            experiment_data[row["project_id"]].append(record)
        return experiment_data

    def transform_projects_content(
        self,
        project: List[Dict[str, Any]],
        max_entries: int = None,
        category: int = 38,
    ) -> List[str]:
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
        self._importer.patch_experiment(exp_id, full_body, category, uid=1130, extra_fields=extra_fields)
        return entry_htmls

    def collect_title_and_tags(self, project: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
        title = project[0].get("project_title", "")
        tags: List[str] = []
        for entry in project:
            tag_list = entry.get("tags")
            if isinstance(tag_list, np.ndarray):
                tags.extend(tag_list.tolist())
            elif isinstance(tag_list, list):
                tags.extend(tag_list)
        return title, tags

    def build_entry_html(self, entry: Dict[str, Any], exp_id: str) -> str:
        header = (
            f"\n----Entry {entry['entry_number']} of {entry['number_of_entries']}----<br>"
            f"<strong>Entry: {entry['entry_title']} (labfolder id: {entry['entry_id']})</strong><br>"
        )
        blocks: List[str] = []

        for element in entry.get("elements", []):
            typ = element.get("type")

            if typ == "TEXT":
                try:
                    blocks.append(self._fetcher.fetch_text(element))
                except Exception as e:
                    self.logger.error("TEXT fetch failed for %s: %s", element.get("id"), e)

            elif typ == "FILE":
                path = self._fetcher.fetch_file(element)
                if path:
                    try:
                        self._importer.upload_file(exp_id, path)
                        blocks.append(f"<p>[Attached file: {path.name}]</p>")
                    except Exception as e:
                        self.logger.error("FILE upload failed for %s: %s", path.name, e)
                        blocks.append(f"<p>[Failed to attach file: {element.get('id')}]</p>")

            elif typ == "IMAGE":
                path = self._fetcher.fetch_image(element)
                if path:
                    try:
                        self._importer.upload_file(exp_id, path)
                        blocks.append(f"<p>[Attached image: {path.name}]</p>")
                    except Exception as e:
                        self.logger.error("IMAGE upload failed for %s: %s", path.name, e)
                        blocks.append(f"<p>[Failed to attach image: {element.get('id')}]</p>")

            elif typ == "DATA":
                try:
                    data = self._fetcher.fetch_data(element)
                    rows = [
                        f"<tr><td>{d.get('title')}</td><td>{d.get('value')}</td><td>{d.get('unit')}</td></tr>"
                        for d in data.get("data_elements", [])
                    ]
                    table_html = "<table><tr><th>Title</th><th>Value</th><th>Unit</th></tr>" + "".join(rows) + "</table>"
                    blocks.append(table_html)
                except Exception as e:
                    self.logger.error("DATA fetch failed for %s: %s", element.get("id"), e)

            elif typ == "TABLE":
                try:
                    tbl_json = self._fetcher.fetch_table(element)
                    if tbl_json:
                        data_table = tbl_json.get("content", {}).get("dataTable", {})
                        header_row = data_table.get("0", {})
                        cols = [header_row[col]["value"] for col in sorted(header_row, key=int)]
                        rows = []
                        for row_idx in sorted(k for k in data_table if k != "0"):
                            row_data = data_table[row_idx]
                            rows.append([row_data[col]["value"] for col in sorted(row_data, key=int)])
                        df_table = pd.DataFrame(rows, columns=cols)
                        tmp_dir = Path(tempfile.gettempdir())
                        xlsx_path = tmp_dir / f"table_{element.get('id')}.xlsx"
                        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
                            df_table.to_excel(writer, sheet_name="table", index=False)
                        self._importer.upload_file(exp_id, xlsx_path)
                        blocks.append(f"<p>[Attached table XLSX: {xlsx_path.name}]</p>")
                    else:
                        blocks.append(f"<p>[No table content for element {element.get('id')}]</p>")
                except Exception as e:
                    self.logger.error("TABLE conversion failed for %s: %s", element.get("id"), e)
                    blocks.append(f"<p>[Error converting table {element.get('id')}]</p>")

            elif typ == "WELL_PLATE":
                try:
                    xlsx_path = self._fetcher.fetch_well_plate_xlsx(element)
                    if xlsx_path:
                        self._importer.upload_file(exp_id, xlsx_path)
                        blocks.append(f"<p>[Attached well plate XLSX: {xlsx_path.name}]</p>")
                    else:
                        blocks.append(f"<p>[Failed to convert well plate to XLSX for {element.get('id')}]</p>")
                except Exception as e:
                    self.logger.error("WELL_PLATE conversion failed for %s: %s", element.get("id"), e)
                    blocks.append(f"<p>[Error handling well plate {element.get('id')}]</p>")

            else:
                self.logger.warning("Skipping element %s of type %s", element.get("id"), typ)
                blocks.append(f"<p>[Skipped element: {element.get('id')}]</p>")

        dt = datetime.strptime(entry["entry_creation_date"], "%Y-%m-%dT%H:%M:%S.%f%z")
        created = f"Created: {dt.date().isoformat()}<br>"
        return header + ("\n".join(blocks) + "<br>") + created + "<hr><hr>"

    def build_extra_fields(self, first_entry: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "Project owner": first_entry.get("project_owner"),
            "Project creation date": first_entry.get("project_creation_date"),
            "Labfolder project ID": first_entry.get("Labfolder_ID"),
        }

    def build_footer_html(self, first_entry: Dict[str, Any]) -> str:
        """
        Render project-level metadata in a right-aligned footer.
        """
        return (
            '<div style="text-align: right; margin-top: 20px;">'
            '<h5 style="margin:0 0 4px 0;">Labfolder Info</h5>'
            f"Project created: {first_entry.get('project_creation_date')}<br>"
            f"Labfolder project id: {first_entry.get('labfolder_project_id')}<br>"
            f"Author: {first_entry.get('project_owner')}<br>"
            f"Last edited: {first_entry.get('last_edited')}<br>"
            '</div>'
        )
