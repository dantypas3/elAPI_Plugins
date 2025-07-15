from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import requests

from src.elabftw_client.utils.endpoints import get_fixed


class LabfolderClient:
    """Client for Labfolder v2 API."""

    def __init__(self, email: str, password: str, base_url: str):

        self.email = email

        self.password = password

        self.base_url = base_url.rstrip("/")

        self._session = requests.Session()

        self._token = None

        self._session.headers.update(
            {
                "Content-Type": "application/json",
                "User-Agent": f"MyLabApp; {self.email}",
            }
        )

    def login(self) -> Optional[str]:
        """Authenticate and store bearer token."""

        url = f"{self.base_url}/auth/login"

        resp = self._session.post(
            url, json={"user": self.email, "password": self.password}
        )

        try:

            resp.raise_for_status()

        except requests.HTTPError as e:

            raise RuntimeError(f"Login failed ({resp.status_code}): {resp.text}") from e

        token = resp.json().get("token")

        if not token:
            raise RuntimeError("Login succeeded but no token returned")

        self._token = token.strip()

        self._session.headers.update({"Authorization": f"Bearer {self._token}"})

        return self._token

    def logout(self) -> None:
        """Invalidate the current token."""

        if not self._token:
            return

        url = f"{self.base_url}/auth/logout"

        self._session.post(url).raise_for_status()

        self._token = None

        self._session.headers.pop("Authorization", None)

    def get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> requests.Response:
        """Perform a GET request to the given API endpoint."""

        url = f"{self.base_url}/{endpoint}"
        response = self._session.get(url, params=params)
        response.raise_for_status()
        return response

    def get_project_elements(self, df) -> Dict[Any, List[Dict[str, Any]]]:
        """
        Turn a DataFrame of rows into a dict mapping project_id -> list of records.
        """
        experiment_data: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)

        for _, row in df.iterrows():
            record = {
                "elements": row.get("elements"),
                "project_creation_date": row.get("creation_date"),
                "entry_number": row.get("entry_number"),
                "total_entries": row.get("number_of_entries"),
                "tags": row.get("tags").tolist(),
                "entry_title": row.get("title_y"),
                "project_title": row.get("title_x"),
                "name": f"{row.get('author.first_name')} {row.get('author.last_name')}",
                "folder_id": row.get("folder_id"),
                "group_id": row.get("group_id"),
                "last_edited": row.get("version_date"),
                "created": row.get("creation_date_x"),
            }
            experiment_data[row["id_y"]].append(record)

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

    def get_text(self, element):
        url = f"{self.base_url}/elements/text/{element.get('id')}"
        resp = self._session.get(url)
        resp.raise_for_status()

        return resp.json().get("content", "")
