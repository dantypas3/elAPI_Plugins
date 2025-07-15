from typing import Any, Dict, List, Optional
from collections import defaultdict

from src.elabftw_client.utils.endpoints import get_fixed
import requests
import numpy as np


class LabfolderClient:
    """Client for Labfolder v2 API."""

    def __init__(self, email: str, password: str, base_url: str):

        self.email = email

        self.password = password

        self.base_url = base_url.rstrip("/")

        self._token = None

        self._session = requests.Session()

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

            raise RuntimeError(
                f"Login failed ({resp.status_code}): {resp.text}"
            ) from e

        token = resp.json().get("token")

        if not token:
            raise RuntimeError("Login succeeded but no token returned")

        self._token = token.strip()

        self._session.headers.update(
            {"Authorization": f"Bearer {self._token}"}
        )

        return self._token

    def logout(self) -> None:
        """Invalidate the current token."""

        if not self._token:
            return

        url = f"{self.base_url}/auth/logout"

        self._session.post(url).raise_for_status()

        self._token = None

        self._session.headers.pop("Authorization", None)

    def get_projects(
        self, limit: int = 100, include_hidden: bool = True
    ) -> List[Dict[str, Any]]:
        """Fetch all projects, handling pagination."""

        projects: List[Dict[str, Any]] = []

        offset = 0

        while True:

            params = {
                "limit": limit,
                "offset": offset,
                "include_hidden": include_hidden,
            }

            resp = self._session.get(
                f"{self.base_url}/projects", params=params
            )

            resp.raise_for_status()

            data = resp.json()

            batch = data

            if not isinstance(batch, list):
                raise RuntimeError(f"Unexpected projects format: {data!r}")

            projects.extend(batch)

            if len(batch) < limit:
                break

            offset += limit

        return projects

    def get_project_data(self) -> List[Dict[str, Any]]:
        """Fetch all entries across all projects."""

        entries: List[Dict[str, Any]] = []

        for proj in self.get_projects():
            proj_id = proj["id"]

            resp = self._session.get(
                f"{self.base_url}/entries", params={"project_ids": proj_id,
                                                    "expand": "author,last_editor"}
            )
            resp.raise_for_status()

            entries.extend(resp.json())

        return entries

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
                "tags": row.get("tags"),
                "entry_title": row.get("title_y"),
                "project_title": row.get("title_x"),
                "name": f"{row.get('author.first_name')} {row.get('author.last_name')}",
                "folder_id": row.get("folder_id"),
                "group_id": row.get("group_id"),
                "last_edited": row.get("version_date"),
                "created": row.get("creation_date"),
            }
            experiment_data[row.get("project_id")].append(record)

        return experiment_data

    def get_text(self, project_data: Dict[Any, List[Dict[str, Any]]]) -> List[str]:
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
            # ── sort & basic info ──────────────────────────────────────────────
            records.sort(key=lambda r: r.get("entry_number", 0))
            first = records[0]
            project_title = first.get("project_title", "Untitled Project")

            # ── create empty experiment ───────────────────────────────────────
            post_resp = get_fixed("experiments").post(data={"title": project_title})
            exp_id = post_resp.headers.get("location").split("/")[-1]

            body_parts: List[str] = []

            # ── collect tags for this project (ensure JSON-safe list[str]) ────
            tags_payload: List[str] = []
            for rec in records:
                raw = rec.get("tags")
                if raw is None or (isinstance(raw, float) and np.isnan(raw)):
                    continue
                if isinstance(raw, np.ndarray):
                    raw = raw.tolist()
                if isinstance(raw, str):
                    # split comma-joined strings if you use them
                    raw = [t.strip() for t in raw.split(",") if t.strip()]
                if isinstance(raw, (list, tuple)):
                    tags_payload.extend(raw)

            # de-dupe while preserving order
            tags_payload = list(dict.fromkeys(tags_payload))

            # ── build every entry block ───────────────────────────────────────
            for rec in records:
                header = (
                    f"\n----Entry {rec.get('entry_number')} "
                    f"of {rec.get('total_entries')}----<br>"
                    f"<strong>Entry: {rec.get('entry_title')}</strong><br>"
                )

                # fetch each TEXT element
                content_blocks: List[str] = []
                for element in rec.get("elements", []):
                    if element and element.get("type") == "TEXT":
                        url = f"{self.base_url}/elements/text/{element.get('id')}"
                        resp = self._session.get(url)
                        resp.raise_for_status()
                        content_blocks.append(resp.json().get("content", ""))

                timestamp = rec.get("last_edited") or rec.get("created")
                created_line = f"Created: {timestamp}<br>"
                divider = "<hr><hr>"

                entry_html = header
                if content_blocks:
                    entry_html += "\n".join(content_blocks) + "<br>"
                entry_html += created_line + divider

                body_parts.append(entry_html)
                texts.append(entry_html)

            # ── right-aligned metadata once per experiment ────────────────────
            metadata_html = (
                '<div style="text-align: right; margin-top: 20px;">'
                f"Labfolder folder_id: {first.get('folder_id')}<br>"
                f"Labfolder group_id: {first.get('group_id')}<br>"
                "owner_id: TODO (αντιστοίχηση του ονόματος με id)<br>"
                f"Created: {first.get('created')}<br>"
                f"Author: {first.get('name')}<br>"
                f"Last edited: {first.get('last_edited')}<br>"
                "TODO: Elab-ID jeder Person einfügen,<br> Extra-Felder noch,  "
                "besprechen<br>"
                "</div>"
            )
            body_parts.append(metadata_html)

            # ── patch the full body & category (no tags here!) ────────────────
            get_fixed("experiments").patch(
                    endpoint_id=exp_id,
                    data={
                        "body": "".join(body_parts),
                        "category": 38,
                        "tags" : tags_payload,
                        "fullname": first.get('name')
                    },
            )

            projects_checked += 1
            if projects_checked >= max_projects:
                break

        return texts