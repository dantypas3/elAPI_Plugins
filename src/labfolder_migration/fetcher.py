from typing import Any, Dict, List, Optional

from labfolder_migration import LabfolderClient


class LabFolderFetcher:
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

    def fetch_entries(
        self,
        expand = None,
        limit: int = 50,
        include_hidden: bool = True,
    ) -> List[Dict[str, Any]]:
        """Fetch all entries across all projects with optional expansions."""
        project_entries: List[Dict[str, Any]] = []
        offset = 0

        expand_str = ','.join(expand) if expand else None

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


    def fetch_text(self, element):
        text_response = self._client.get("elements/test", params=element.get("id"))
        return text_response.json().get("content", "")
