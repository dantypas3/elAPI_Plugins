import requests

from urllib.parse import urljoin

from typing import List, Dict, Any


class Labfolder:
    """Client for Labfolder v2 API."""

    def __init__(self, email: str, password: str,

                 base_url: str = "https://labfolder.labforward.app/api/v2"):

        self.email = email

        self.password = password

        self.base_url = base_url.rstrip("/")

        self._token = None

        self._session = requests.Session()

        self._session.headers.update({

            "Content-Type": "application/json",

            "User-Agent": f"MyLabApp; {self.email}"

        })

    def login(self) -> str:

        """Authenticate and store bearer token."""

        url = f"{self.base_url}/login"

        resp = self._session.post(url, json={"user": self.email, "password": self.password})

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

    def get_projects(self, limit: int = 100, include_hidden: bool = True

                     ) -> List[Dict[str, Any]]:

        """Fetch all projects, handling pagination."""

        projects: List[Dict[str, Any]] = []

        offset = 0

        while True:

            params = {"limit": limit, "offset": offset, "include_hidden": include_hidden}

            resp = self._session.get(f"{self.base_url}/projects", params=params)

            resp.raise_for_status()

            data = resp.json()

            batch = data.get("data", data)

            if not isinstance(batch, list):
                raise RuntimeError(f"Unexpected projects format: {data!r}")

            projects.extend(batch)

            if len(batch) < limit:
                break

            offset += limit

        return projects

    def get_project_entries(self) -> List[Dict[str, Any]]:

        """Fetch all entries across all projects."""

        entries: List[Dict[str, Any]] = []

        for proj in self.get_projects():
            proj_id = proj["id"]

            resp = self._session.get(f"{self.base_url}/entries", params={"project_ids": proj_id})

            resp.raise_for_status()

            entries.extend(resp.json())

        return entries

    def get_entries(self) -> List:

        entries = []

        project_entries = self.get_project_entries()

        for project in project_entries:

            for entry in project_entries[project]:
                entry_id = entry['id']

                entry_url = urljoin(self.base_url, f"entries/{entry_id}")

                req = requests.get(entry_url, headers=self._session.headers)

                req_json = req.json()

                print(req_json['id'])

                entries.append(req_json)

        return entries

    def __enter__(self):

        self.login()

        return self

    def __exit__(self, *args):

        self.logout()
