from collections import defaultdict
from typing import Dict, Any, List

import pandas as pd

class Transformer:
    def __init__(self, entries):
        self._entries = pd.DataFrame(entries)

    def create_experiment_data(self):

        experiment_data: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)

        for _, entries_row in self._entries.iterrows():
            record = {
                "name"                  : f"{entries_row["author"].get("first_name")}"
                                          f" {entries_row["author"].get('last_name')}",
                "entry_creations_date"  : entries_row["creation_date"],
                "elements"              : entries_row["elements"],
                "entry_number"          : entries_row["entry_number"],
                "entry_id"              : entries_row["id"],
                "last_editor_name"      : f"{entries_row["last_editor"].get("first_name")} "
                                          f"{entries_row["last_editor"].get("last_name")}",
                "tags"                  : entries_row["tags"],
                "entry_title"           : entries_row["title"],
                "last_edited"           : entries_row["version_date"],
                "project_creation_date": entries_row["project"].get("creation_date"),
                "labfolder_folder_id": entries_row["project"].get("folder_id"),
                "labfolder_id": entries_row["project"].get("id"),
                "number_of_entries": entries_row["project"].get("number_of_entries"),
                "title": entries_row["project"].get("title"),
             }

            experiment_data[entries_row["project_id"]].append(record)

        return experiment_data

    def get_entry_content(
        self, project_data: Dict[Any, List[Dict[str, Any]]]
    ) -> List[str]:
        """
        Build one experiment per project, patch its body & category,
        THEN add tags via POST /experiments/{id}/tags.
        Returns a flat list of the HTML for all entries (for logging).
        """
        if not self._token:
            raise RuntimeError("Must call login() before get_text()")

        texts: List[str] = []
        max_projects = 5
        projects_checked = 0

        for project_id, records in project_data.items():

            records.sort(key=lambda r: r.get("entry_number", 0))
            first = records[0]
            project_title = first.get("project_title", "Untitled Project")

            post_resp = get_fixed("experiments").post(
                data={
                    "title": project_title,
                    "tags": first.get("tags"),
                }
            )
            exp_id = post_resp.headers.get("location").split("/")[-1]

            body_parts: List[str] = []

            for rec in records:

                header = (
                    f"\n----Entry {rec.get('entry_number')} "
                    f"of {rec.get('total_entries')}----<br>"
                    f"<strong>Entry: {rec.get('entry_title')}</strong><br>"
                )

                content_blocks: List[str] = []

                for element in rec.get("elements", []):
                    if element and element.get("type") == "TEXT":
                        content_blocks.append(self.get_text(element))

                date = rec.get("created")
                dt = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%f%z")
                date = dt.date().isoformat()
                created_line = f"Created: {date}<br>"
                divider = "<hr><hr>"

                entry_html = header
                if content_blocks:
                    entry_html += "\n".join(content_blocks) + "<br>"
                entry_html += created_line + divider

                body_parts.append(entry_html)
                texts.append(entry_html)

            metadata_html = (
                '<div style="text-align: right; margin-top: 20px;">'
                f"Labfolder folder_id: {first.get('folder_id')}<br>"
                f"Labfolder group_id: {first.get('group_id')}<br>"
                "owner_id: TODO (αντιστοίχηση του ονόματος με id)<br>"
                f"Created: {first.get('created')}<br>"
                f"Author: {first.get('name')}<br>"
                f"Last edited: {first.get('last_edited')}<br>"
                "</div>"
            )
            body_parts.append(metadata_html)

            # ── patch the full body & category (no tags here!) ────────────────
            get_fixed("experiments").patch(
                endpoint_id=exp_id,
                data={
                    "body": "".join(body_parts),
                    "category": 38,
                },
            )

            projects_checked += 1
            if projects_checked >= max_projects:
                break

        return texts
