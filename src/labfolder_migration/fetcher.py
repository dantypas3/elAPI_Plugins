import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from requests import HTTPError

from labfolder_migration import LabfolderClient

ROOT = Path(__file__).resolve().parent.parent.parent
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
    Wraps your Labfolder client to fetch raw entries and auto-renew token if
    expired.
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
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> requests.Response:
        """
        Wrapper around client.get that retries once on 401 by re-logging in.
        """
        try:
            resp = self._client.get(endpoint, params=params)
            return resp
        except HTTPError as e:
            if e.response.status_code == 401:
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
            params: Dict[str, Any] = {
                "limit": limit,
                "offset": offset,
                "include_hidden": include_hidden,
            }
            if expand_str:
                params["expand"] = expand_str
            resp = self._get("entries", params=params)
            batch = resp.json()
            if not isinstance(batch, list):
                raise RuntimeError("Unexpected entries format: %r" % batch)
            entries.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return entries

    def fetch_text(self, element: Dict[str, Any]) -> str:
        text_id = f"elements/text/{element['id']}"
        resp = self._get(text_id)
        return resp.json().get("content", "")

    def fetch_file(self, element: Dict[str, Any]) -> Optional[Path]:
        """
        Download a file from Labfolder. Returns a Path, or None on any error.
        """
        file_id = element.get("id")
        if not file_id:
            logger.error("Invalid file element (no id) %r", element)
            return None

        try:
            resp = self._get(f"elements/file/{file_id}/download")
        except HTTPError as e:
            logger.error("Failed to download file %s: %s", file_id, e)
            return None

        content_disp = resp.headers.get("Content-Disposition", "")
        filename = "unnamed_file"

        if "filename=" in content_disp:
            parts = content_disp.split("filename=")
            if len(parts) > 1:
                filename = parts[1].strip().strip('"')

        tmp_dir = Path(tempfile.gettempdir())
        temp_path = tmp_dir / filename

        try:
            with temp_path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        except (OSError, requests.exceptions.RequestException) as e:
            logger.error("Error writing file %s: %s", temp_path, e)
            return None

        return temp_path

    def fetch_image(self, element: Dict[str, Any]) -> Optional[Path]:
        image_id = element.get("id")

        if not image_id:
            logger.error("Invalid image element (no id) %r", element)
            return None

        try:
            resp = self._get(f"elements/image/{image_id}/original-data")
        except HTTPError as e:
            logger.error("Failed to download image %s: %s", image_id, e)
            return None

        content_disp = resp.headers.get("Content-Disposition", "")
        filename = "unnamed_image"

        if "filename=" in content_disp:
            parts = content_disp.split("filename=")
            if len(parts) > 1:
                filename = parts[1].strip().strip('"')

        tmp_dir = Path(tempfile.gettempdir())
        temp_path = tmp_dir / filename

        try:
            with temp_path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        except (OSError, requests.exceptions.RequestException) as e:
            logger.error("Error writing image file %s: %s", temp_path, e)
            return None

        return temp_path

    def fetch_data(self, element: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch the latest version of a Labfolder data element container.

        Returns the JSON content as a dictionary, or None on error.
        """
        data_id = element.get("id")
        if not data_id:
            logger.error("Invalid data element (no id): %r", element)
            return None

        try:
            resp = self._get(f"elements/data/{data_id}")
            return resp.json()
        except HTTPError as e:
            logger.error("Failed to fetch data element %s: %s", data_id, e)
            return None
        except ValueError as e:
            logger.error(
                "Invalid JSON returned for data element %s: %s", data_id, e
            )
            return None

    def fetch_table(self, element: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch the latest version of a Labfolder table element.

        Returns the JSON content as a dictionary, or None on error.
        """
        table_id = element.get("id")
        if not table_id:
            logger.error("Invalid table element (no id): %r", element)
            return None

        try:
            resp = self._get(f"elements/table/{table_id}")
            return resp.json()
        except HTTPError as e:
            logger.error("Failed to fetch table element %s: %s", table_id, e)
            return None
        except ValueError as e:
            logger.error(
                "Invalid JSON returned for table element %s: %s", table_id, e
            )
            return None

    def fetch_well_plate(
        self, element: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch the latest version of a Labfolder well plate template element.

        Returns the JSON content as a dictionary, or None on error.
        """
        plate_id = element.get("id")
        if not plate_id:
            logger.error("Invalid well plate element (no id): %r", element)
            return None

        try:
            resp = self._get(f"elements/well-plate/{plate_id}")
            return resp.json()
        except HTTPError as e:
            logger.error(
                "Failed to fetch well plate element %s: %s", plate_id, e
            )
            return None
        except ValueError as e:
            logger.error(
                "Invalid JSON returned for well plate element %s: %s",
                plate_id,
                e,
            )
            return None
