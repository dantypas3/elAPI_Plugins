import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import requests

from src.labfolder_migration.fetcher import LabFolderFetcher
from src.labfolder_migration.importer import Importer

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "transformer.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(LOG_FILE)),
    ],
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
        """
        Group raw entry dicts by project_id, normalizing fields into a
        record list.
        """
        experiment_data: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
        for _, row in self._entries.iterrows():
            record = {
                "name": f"{row['author'].get('first_name')}"
                f" {row['author'].get('last_name')}",
                "entry_creation_date": row["creation_date"],
                "elements": row["elements"],
                "entry_number": row["entry_number"],
                "entry_id": row["id"],
                "last_editor_name": (
                    f"{row['last_editor'].get('first_name')} "
                    f"{row['last_editor'].get('last_name')}"
                ),
                "tags": row["tags"],
                "entry_title": row["title"],
                "last_edited": row["version_date"],
                "project_creation_date": row["project"].get("creation_date"),
                "labfolder_project_id": row["project"].get("id"),
                "number_of_entries": row["project"].get("number_of_entries"),
                "project_title": row["project"].get("title"),
                "project_owner": (
                    f"{row['author'].get('first_name')} "
                    f"{row['author'].get('last_name')}"
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
        """
        For one project:
        - create an eLabFTW experiment,
        - build each entry’s HTML  (including TEXT, FILE, IMAGE, DATA,
        TABLE, WELL_PLATE),
        - patch the experiment with body, category, and extra_fields,
        - return the list of HTML blocks.
        """
        title, tags = self.collect_title_and_tags(project)
        exp_id = self._importer.create_experiment(title, tags)

        entry_htmls: List[str] = []
        for idx, entry in enumerate(project, start=1):
            if max_entries and idx > max_entries:
                break
            entry_htmls.append(self.build_entry_html(entry, exp_id))

        first_entry = project[0]
        entry_htmls.append(self.build_footer_html(first_entry))
        full_body = "".join(entry_htmls)

        extra_fields = self.build_extra_fields(first_entry)
        # TODO uid mapping
        self._importer.patch_experiment(
            exp_id, full_body, category, uid=1130, extra_fields=extra_fields
        )

        return entry_htmls

    def collect_title_and_tags(
        self, project: List[Dict[str, Any]]
    ) -> Tuple[str, List[str]]:
        """
        Extract a single project title and aggregate all entry tags.
        """
        title = project[0].get("project_title", "")
        tags: List[str] = []
        for entry in project:
            tags.extend(entry.get("tags", np.array([])).tolist())
        return title, tags

    def build_entry_html(self, entry: Dict[str, Any], exp_id: str) -> str:
        """
        Render one entry’s:
        - header,
        - body (TEXT, FILE, IMAGE, DATA, TABLE, WELL_PLATE),
        - creation date,
        - divider.
        """
        header = (
            f"\n----Entry {entry['entry_number']}  of"
            f" {entry['number_of_entries']}----<br>"
            f"<strong>Entry: {entry['entry_title']}  (labfolder id:"
            f" {entry['entry_id']})</strong><br>"
        )
        blocks: List[str] = []

        for element in entry.get("elements", []):
            if not element:
                continue
            typ = element.get("type")

            if typ == "TEXT":
                try:
                    blocks.append(self._fetcher.fetch_text(element))
                except (OSError, requests.exceptions.RequestException) as e:
                    self.logger.error(
                        "TEXT fetch failed for %s: %s", element.get("id"), e
                    )

            elif typ == "FILE":
                path = self._fetcher.fetch_file(element)
                if path:
                    try:
                        self._importer.upload_file(exp_id, path)
                        blocks.append(f"<p>[Attached file: {path.name}]</p>")
                    except (
                        OSError,
                        requests.exceptions.RequestException,
                    ) as e:
                        self.logger.error(
                            "FILE upload failed for %s: %s", path.name, e
                        )
                        blocks.append(
                            f"<p>[Failed to attach file: "
                            f" {element.get('id')}]</p>"
                        )

            elif typ == "IMAGE":
                path = self._fetcher.fetch_image(element)
                if path:
                    try:
                        self._importer.upload_file(exp_id, path)
                        blocks.append(f"<p>[Attached image: {path.name}]</p>")
                    except (
                        OSError,
                        requests.exceptions.RequestException,
                    ) as e:
                        self.logger.error(
                            "IMAGE upload failed for %s: %s", path.name, e
                        )
                        blocks.append(
                            f"<p>[Failed to attach image: "
                            f" {element.get('id')}]</p>"
                        )

            elif typ == "DATA":
                try:
                    data = self._fetcher.fetch_data(element)
                    rows = [
                        (
                            f"<tr><td>{d.get('title')}</td><td>"
                            f"{d.get('value')}</td><td>{d.get('unit')}</td></tr>"
                        )
                        for d in data.get("data_elements", [])
                    ]
                    table_html = (
                        "<table><tr><th>Title</th><th>"
                        "Value</th><th>Unit</th></tr>"
                        + "".join(rows)
                        + "</table>"
                    )
                    blocks.append(table_html)
                except (OSError, requests.exceptions.RequestException) as e:
                    self.logger.error(
                        "DATA fetch failed for %s: %s", element.get("id"), e
                    )
            elif typ == "TABLE":
                table = self._fetcher.fetch_table(element)
                if table and table.get("content"):
                    title = table.get("title", "Untitled Table")
                    content = table["content"].get("dataTable", {})

                    tbl = [f"<p><strong>{title}</strong></p>", "<table>"]

                    headers = content.get("0", {})
                    hdr_cells = "".join(
                        f"<th>{headers[col]['value']}</th>"
                        for col in sorted(headers, key=int)
                    )
                    tbl.append(f"<tr>{hdr_cells}</tr>")

                    for row_idx in sorted(n for n in content if n != "0"):
                        row = content[row_idx]
                        cells = "".join(
                            f"<td>{row.get(col, {}).get('value', '')}</td>"
                            for col in sorted(row, key=int)
                        )
                        tbl.append(f"<tr>{cells}</tr>")
                    tbl.append("</table>")

                    blocks.extend(tbl)
                else:
                    blocks.append("<p>[Empty or invalid table]</p>")

            elif typ == "WELL_PLATE":
                try:
                    plate = self._fetcher.fetch_well_plate(element)
                    if plate:
                        title = plate.get("title", "Untitled Well Plate")
                        blocks.append(f"<p><strong>{title}</strong></p>")
                        blocks.append(
                            f"<pre>{plate.get('content')}\nMeta: "
                            f" {plate.get('meta_data')}</pre>"
                        )
                except (OSError, requests.exceptions.RequestException) as e:
                    self.logger.error(
                        "WELL_PLATE fetch failed for %s: %s",
                        element.get("id"),
                        e,
                    )

            else:
                self.logger.warning(
                    "Skipping element %s of type %s", element.get("id"), typ
                )
                blocks.append(f"<p>[Skipped element: {element.get('id')}]</p>")

        dt = datetime.strptime(
            entry["entry_creation_date"], "%Y-%m-%dT%H:%M:%S.%f%z"
        )
        created = f"Created: {dt.date().isoformat()}<br>"
        body_html = ("\n".join(blocks) + "<br>") if blocks else ""
        return header + body_html + created + "<hr><hr>"

    def build_extra_fields(
        self, first_entry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Return the dict of fields to merge under metadata.extra_fields.
        """
        return {
            "Project Owner": first_entry.get("project_owner"),
            "project_creation_date": first_entry.get("project_creation_date"),
            "Labfolder_ID": first_entry.get("Labfolder_ID"),
            "project_title": first_entry.get("project_title"),
        }

    def build_footer_html(self, first_entry: Dict[str, Any]) -> str:
        """Render project‑level metadata in a right‑aligned footer."""
        return (
            '<div style="text-align: right; margin-top: 20px;">'
            '<h5 style="margin:0 0 4px 0;">Labfolder Info</h5>'
            f"Project created: "
            f"{first_entry.get('project_creation_date')}<br>"
            f"Labfolder project id: "
            f" {first_entry.get('labfolder_project_id')}<br>"
            f"Author: {first_entry.get('project_owner')}<br>"
            f"Last edited: {first_entry.get('last_edited')}<br>"
            "</div>"
        )
