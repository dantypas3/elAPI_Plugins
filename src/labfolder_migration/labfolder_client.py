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
