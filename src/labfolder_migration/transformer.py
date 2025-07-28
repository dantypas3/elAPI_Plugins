from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

import numpy as np
import pandas as pd
import logging

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
    def __init__ (
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

    def transform_experiment_data (self) -> Dict[Any, List[Dict[str, Any]]]:
        experiment_data: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
        for _, row in self._entries.iterrows():
            record = {
                "name"                 : f"{row['author'].get('first_name')} "
                                         f"{row['author'].get('last_name')}",
                "entry_creation_date"  : row["creation_date"],
                "elements"             : row["elements"],
                "entry_number"         : row["entry_number"],
                "entry_id"             : row["id"],
                "last_editor_name"     : f"{row['last_editor'].get('first_'
                                                                   'name')} "
                                         f"{row['last_editor'].get('last_name')}",
                "tags"                 : row["tags"],
                "entry_title"          : row["title"],
                "last_edited"          : row["version_date"],
                "project_creation_date": row["project"].get("creation_date"),
                "labfolder_project_id" : row["project"].get("id"),
                "number_of_entries"    : row["project"].get(
                    "number_of_entries"),
                "project_title"        : row["project"].get("title"),
                }
            experiment_data[row["project_id"]].append(record)
        return experiment_data

    def transform_projects_content (
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
        self._importer.patch_experiment(exp_id, full_body, category)
        return entry_htmls

    def collect_title_and_tags (
            self,
            project: List[Dict[str, Any]]
            ) -> Tuple[str, List[str]]:
        title = project[0].get("project_title", "")
        tags: List[str] = []
        for entry in project:
            tags.extend(entry.get("tags", np.array([])))
        return title, tags

    def build_entry_html (self, entry: Dict[str, Any], exp_id: str) -> str:
        header = (
            f"\n----Entry {entry['entry_number']} of "
            f"{entry['number_of_entries']}----<br>"
            f"<strong>Entry: {entry['entry_title']} (labfolder id: "
            f"{entry['entry_id']})</strong><br>"
        )
        blocks: List[str] = []

        for element in entry.get("elements", []):
            if not element:
                continue

            type = element.get("type")

            if type == "TEXT":
                try:
                    text = self._fetcher.fetch_text(element)
                    blocks.append(text)
                except Exception as e:
                    logger.error("Failed to fetch text for element %s: %s",
                                 element.get("id"), e)

            elif type == "FILE":
                file_temp_path: Path = self._fetcher.fetch_file(element)
                if file_temp_path:
                    try:
                        self._importer.upload_file(exp_id, file_temp_path)
                        blocks.append(
                            f"<p>[Attached file: {file_temp_path.name}]</p>")
                    except Exception as e:
                        logger.error("Failed to upload file %s: %s",
                                     file_temp_path.name, e)
                        blocks.append(
                            f"<p>Failed to attach file: {element.get('id')}</p>")

            elif type == "IMAGE":
                image_temp_path: Path = self._fetcher.fetch_image(element)
                if image_temp_path:
                    try:
                        self._importer.upload_file(exp_id, image_temp_path)
                        blocks.append(
                            f"<p>[Attached image: {image_temp_path.name}]</p>")
                    except Exception as e:
                        logger.error("Failed to upload image %s: %s",
                                     image_temp_path.name, e)
                        blocks.append(
                            f"<p>Failed to attach image: {element.get('id')}</p>")

            elif type == "DATA":
                try:
                    data = self._fetcher.fetch_data(element)
                    if data:
                        table_rows = [
                            f"<tr><td>{d.get('title')}</td><td>{d.get('value')}</td><td>{d.get('unit')}</td></tr>"
                            for d in data.get("data_elements", [])
                            ]
                        table_html = "<table><tr><th>Title</th><th>Value</th><th>Unit</th></tr>" + "".join(
                            table_rows) + "</table>"
                        blocks.append(table_html)
                except Exception as e:
                    logger.error("Failed to fetch data for element %s: %s",
                                 element.get("id"), e)

            elif type == "TABLE":
                try:
                    table = self._fetcher.fetch_table(element)
                    if table:
                        title = table.get("title", "Untitled Table")
                        content = table.get("content")
                        blocks.append(f"<p><strong>{title}</strong></p>")
                        blocks.append(
                            f"<pre>{content if content else '[Empty Table]'}</pre>")
                except Exception as e:
                    logger.error("Failed to fetch table for element %s: %s",
                                 element.get("id"), e)

            elif type == "WELL_PLATE":
                try:
                    plate = self._fetcher.fetch_well_plate(element)
                    if plate:
                        title = plate.get("title", "Untitled Well Plate")
                        blocks.append(f"<p><strong>{title}</strong></p>")
                        blocks.append(
                            f"<pre>Content: {plate.get('content')}\nMeta: {plate.get('meta_data')}</pre>")
                except Exception as e:
                    logger.error(
                        "Failed to fetch well plate for element %s: %s",
                        element.get("id"), e)

            else:
                logger.warning("Skipping file element %s (%s) (no local file)",
                               element.get("id"), element.get("type"))
                blocks.append(
                    f"<p>[No file to attach for element: {element.get('id')}]</p>")

        dt = datetime.strptime(entry["entry_creation_date"],
                               "%Y-%m-%dT%H:%M:%S.%f%z")
        created = f"Created: {dt.date().isoformat()}<br>"
        body_html = ("\n".join(blocks) + "<br>") if blocks else ""

        return header + body_html + created + "<hr><hr>"

    def build_footer_html (self, first_entry: Dict[str, Any]) -> str:
        return (
            '<div style="text-align: right; margin-top: 20px;">'
            f"Project created: {first_entry.get('project_creation_date')}<br>"
            f"Labfolder project id: "
            f"{first_entry.get('labfolder_project_id')}<br>"
            f"Author: {first_entry.get('name')}<br>"
            f"Last edited: {first_entry.get('last_edited')}<br>"
            "</div>"
        )
