from collections import defaultdict
from typing import Dict, Any, List, Tuple
from datetime import datetime
from pathlib import Path
import tempfile

import pandas as pd
import numpy as np

from src.labfolder_migration.fetcher import LabFolderFetcher
from src.labfolder_migration.importer import Importer


class Transformer:
    def __init__(
        self,
        entries: List[Dict[str, Any]],
        fetcher: LabFolderFetcher,
        importer: Importer,
    ) -> None:
        self._entries = pd.DataFrame(entries)
        self._fetcher = fetcher
        self._importer = importer

    def transform_experiment_data(self) -> Dict[Any, List[Dict[str, Any]]]:
        experiment_data: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
        for _, row in self._entries.iterrows():
            record = {
                "name": f"{row['author'].get('first_name')} {row['author'].get('last_name')}",
                "entry_creation_date": row["creation_date"],
                "elements": row["elements"],
                "entry_number": row["entry_number"],
                "entry_id": row["id"],
                "last_editor_name": f"{row['last_editor'].get('first_name')} {row['last_editor'].get('last_name')}",
                "tags": row["tags"],
                "entry_title": row["title"],
                "last_edited": row["version_date"],
                "project_creation_date": row["project"].get("creation_date"),
                "labfolder_project_id": row["project"].get("id"),
                "number_of_entries": row["project"].get("number_of_entries"),
                "project_title": row["project"].get("title"),
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
        self._importer.patch_experiment(exp_id, full_body, category)
        return entry_htmls

    def collect_title_and_tags(
        self,
        project: List[Dict[str, Any]]
    ) -> Tuple[str, List[str]]:
        title = project[0].get("project_title", "")
        tags: List[str] = []
        for entry in project:
            tags.extend(entry.get("tags", np.array([])).tolist())
        return title, tags

    def build_entry_html(self, entry: Dict[str, Any], exp_id: str) -> str:
        header = (
            f"\n----Entry {entry['entry_number']} of {entry['number_of_entries']}----<br>"
            f"<strong>Entry: {entry['entry_title']} (labfolder id: {entry['entry_id']})</strong><br>"
        )
        blocks: List[str] = []
        for element in entry.get("elements", []):
            if not element:
                continue
            typ = element.get("type")
            if typ == "TEXT":
                blocks.append(self._fetcher.fetch_text(element))
            elif typ == "FILE":
                temp_path: Path = self._fetcher.fetch_file(element)
                self._importer.upload_file(exp_id, temp_path)
                blocks.append(f"<p>[Attached file: {temp_path.name}]</p>")
            else:
                continue

        dt = datetime.strptime(entry["entry_creation_date"], "%Y-%m-%dT%H:%M:%S.%f%z")
        created = f"Created: {dt.date().isoformat()}<br>"
        body_html = ("\n".join(blocks) + "<br>") if blocks else ""

        return header + body_html + created + "<hr><hr>"

    def build_footer_html(self, first_entry: Dict[str, Any]) -> str:
        return (
            '<div style="text-align: right; margin-top: 20px;">'
            f"Project created: {first_entry.get('project_creation_date')}<br>"
            f"Labfolder project id: {first_entry.get('labfolder_project_id')}<br>"
            f"Author: {first_entry.get('name')}<br>"
            f"Last edited: {first_entry.get('last_edited')}<br>"
            "</div>"
        )
