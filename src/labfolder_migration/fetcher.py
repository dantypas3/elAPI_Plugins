import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from requests import HTTPError
import pandas as pd

from labfolder_migration import LabfolderClient

# configure logging
ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "labfolder_fetcher.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(str(LOG_FILE))],
)
logger = logging.getLogger(__name__)


class LabFolderFetcher:
    """
    Wraps LabfolderClient to fetch entries and elements,
    auto-renewing token if expired.
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

    def _get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """
        Wrapper around client.get that retries once on 401 by re-logging in.
        """
        try:
            return self._client.get(endpoint, params=params)
        except HTTPError as e:
            if e.response.status_code == 401:
                self._client.login()
                return self._client.get(endpoint, params=params)
            raise

    def fetch_entries(
        self,
        expand: Optional[List[str]] = None,
        limit: int = 50,
        include_hidden: bool = True,
    ) -> List[Dict[str, Any]]:
        """Fetch all entries across projects."""
        entries: List[Dict[str, Any]] = []
        offset = 0
        expand_str = ",".join(expand) if expand else None
        while True:
            params = {"limit": limit, "offset": offset, "include_hidden": include_hidden}
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
        """Fetch a TEXT element's content."""
        resp = self._get(f"elements/text/{element['id']}")
        return resp.json().get("content", "")

    def fetch_file(self, element: Dict[str, Any]) -> Optional[Path]:
        """Download a file element."""
        file_id = element.get("id")
        if not file_id:
            logger.error("Invalid file element (no id): %r", element)
            return None
        try:
            resp = self._get(f"elements/file/{file_id}/download")
        except HTTPError as e:
            logger.error("Failed to download file %s: %s", file_id, e)
            return None
        return self._save_response(resp)

    def fetch_image(self, element: Dict[str, Any]) -> Optional[Path]:
        """Download an IMAGE element."""
        image_id = element.get("id")
        if not image_id:
            logger.error("Invalid image element (no id): %r", element)
            return None
        try:
            resp = self._get(f"elements/image/{image_id}/original-data")
        except HTTPError as e:
            logger.error("Failed to download image %s: %s", image_id, e)
            return None
        return self._save_response(resp)

    def fetch_data(self, element: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fetch a DATA element's JSON."""
        data_id = element.get("id")
        if not data_id:
            logger.error("Invalid data element (no id): %r", element)
            return None
        try:
            resp = self._get(f"elements/data/{data_id}")
            return resp.json()
        except (HTTPError, ValueError) as e:
            logger.error("Failed to fetch data element %s: %s", data_id, e)
            return None

    def fetch_table(self, element: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fetch a TABLE element's JSON."""
        table_id = element.get("id")
        if not table_id:
            logger.error("Invalid table element (no id): %r", element)
            return None
        try:
            resp = self._get(f"elements/table/{table_id}")
            return resp.json()
        except (HTTPError, ValueError) as e:
            logger.error("Failed to fetch table element %s: %s", table_id, e)
            return None

    def fetch_well_plate_json(
        self, element: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Fetch WELL_PLATE JSON (content + meta_data)."""
        plate_id = element.get("id")
        if not plate_id:
            logger.error("Invalid well plate element (no id): %r", element)
            return None
        try:
            resp = self._get(f"elements/well-plate/{plate_id}")
            return resp.json()
        except (HTTPError, ValueError) as e:
            logger.error("Failed to fetch well plate JSON %s: %s", plate_id, e)
            return None

    def fetch_well_plate_xlsx(
        self, element: Dict[str, Any]
    ) -> Optional[Path]:
        """Convert WELL_PLATE JSON to XLSX and return path."""
        wp_json = self.fetch_well_plate_json(element)
        if not wp_json:
            return None
        plate_id = element.get("id")
        content = wp_json.get("content") or {}
        df_content = pd.json_normalize(content, sep='.')
        meta = wp_json.get("meta_data") or {}
        df_meta = pd.json_normalize(meta, sep='.')
        tmp_dir = Path(tempfile.gettempdir())
        xlsx_path = tmp_dir / f"wellplate_{plate_id}.xlsx"
        try:
            with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
                df_content.to_excel(writer, sheet_name='content', index=False)
                df_meta.to_excel(writer, sheet_name='meta_data', index=False)
            return xlsx_path
        except Exception as e:
            logger.error("Error writing XLSX for well plate %s: %s", plate_id, e)
            return None

    def _save_response(self, resp: requests.Response) -> Optional[Path]:
        """Helper to save binary response to temp file."""
        content_disp = resp.headers.get("Content-Disposition", "")
        filename = "unnamed"
        if "filename=" in content_disp:
            filename = content_disp.split("filename=")[1].strip().strip('"')
        tmp_dir = Path(tempfile.gettempdir())
        temp_path = tmp_dir / filename
        try:
            with temp_path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return temp_path
        except (OSError, requests.exceptions.RequestException) as e:
            logger.error("Error writing file %s: %s", temp_path, e)
            return None