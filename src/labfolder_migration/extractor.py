from typing import Any, Dict, List, Optional

from labfolder_migration import LabfolderClient


class LabFolderExtractor:
    """
    Wraps your Labfolder client to fetch raw entries.
    """

    def __init__(
        self,
        email: str,
        password: str,
        base_url: str,
    ) -> None:
        self._client = LabfolderClient(email, password, base_url)
        self._client.login()

    def get_projects(
        self, limit: int = 100, include_hidden: bool = True
    ) -> List[Dict[str, Any]]:
        """Fetch all projects, handling pagination."""

        projects: List[Dict[str, Any]] = []
        offset: int = 0
        while True:

            params = {
                "limit": limit,
                "offset": offset,
                "include_hidden": include_hidden,
            }

            resp = self._client.get("projects", params=params)

            resp.raise_for_status()
            data = resp.json()
            batch = data

            if not isinstance(batch, list):
                raise RuntimeError(f"Unexpected projects format: {data}")

            projects.extend(batch)

            if len(batch) < limit:
                break

            offset += limit

        return projects

    def get_project_entries(
        self,
        expand: Optional[List[str]] = None,
        limit: int = 50,
        include_hidden: bool = True,
    ) -> List[Dict[str, Any]]:
        """Fetch all entries across all projects with optional expansions."""
        project_entries: List[Dict[str, Any]] = []
        offset = 0

        expand_str = ' '.join(expand) if expand else None

        while True:
            params: Dict[str, Any] = {
                "limit": limit,
                "offset": offset,
                "include_hidden": include_hidden,
            }
            if expand_str:
                params["expand"] = expand_str

            response = self._client.get("entries", params=params)
            batch = response.json()

            if not isinstance(batch, list):
                raise RuntimeError(f"Unexpected entries format: {batch!r}")

            project_entries.extend(batch)
            if len(batch) < limit:
                break

            offset += limit

        return project_entries

