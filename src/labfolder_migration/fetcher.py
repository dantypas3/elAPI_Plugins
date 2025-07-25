from typing import Any, Dict, List, Optional
from pathlib import Path
import tempfile
import requests
from requests import HTTPError
import logging

from labfolder_migration import LabfolderClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('labfolder_fetcher.log')
    ]
)
logger = logging.getLogger(__name__)

class LabFolderFetcher:
    """
    Wraps your Labfolder client to fetch raw entries and auto-renew token if expired.
    """
    def __init__(
        self,
        email: str,
        password: str,
        base_url: str,
    ) -> None:
        self.email = email
        self.password = password
        self.base_url = base_url.rstrip("/")
        self._client = LabfolderClient(email, password, self.base_url)
        self._client.login()

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """
        Wrapper around client.get that retries once on 401 by re-logging in.
        """
        try:
            resp = self._client.get(endpoint, params=params)
            return resp
        except HTTPError as e:
            if e.response.status_code == 401:
                # token expired: re-login and retry
                self._client.login()
                resp = self._client.get(endpoint, params=params)
                return resp
            raise

    def fetch_entries(
        self,
        expand: Optional[List[str]] = None,
        limit: int = 50,
        include_hidden: bool = True,
    ) -> List[Dict[str, Any]]:
        """Fetch all entries across projects, auto-renewing token if needed."""
        entries: List[Dict[str, Any]] = []
        offset = 0
        expand_str = ",".join(expand) if expand else None

        while True:
            params: Dict[str, Any] = {"limit": limit, "offset": offset, "include_hidden": include_hidden}
            if expand_str:
                params["expand"] = expand_str
            resp = self._get("entries", params=params)
            batch = resp.json()
            if not isinstance(batch, list):
                raise RuntimeError(f"Unexpected entries format: {batch!r}")
            entries.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return entries

    def fetch_text(self, element: Dict[str, Any]) -> str:
        text_id = f"elements/text/{element['id']}"
        resp = self._get(text_id)
        return resp.json().get("content", "")

    def fetch_file(self, element: Dict[str, Any]) -> Path:
        file_id = element.get("id")
        if not file_id:
            raise ValueError(f"Invalid file element: {element!r}")

        meta = self._get(f"elements/file/{file_id}").json()

        filename = meta.get("file_name") or meta.get("filename")
        if not filename:

            filename = "no_labfolder_name"
            logger.warning(f"Filename missing for file {file_id}; using generic name: {filename}")

        resp = self._get(f"elements/file/{file_id}/download")
        tmp_dir = Path(tempfile.gettempdir())
        temp_path = tmp_dir / filename
        with temp_path.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return temp_path