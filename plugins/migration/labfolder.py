from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
import requests

class Labfolder:
    def __init__(self, email: Optional[str] = None, password: Optional[str] = None,
                 base_url: str = "https://labfolder.labforward.app/api/v2"):
        if email is None:
            print("Email is required")
        if password is None:
            print("Password is required")

        self.email = email
        self.password = password
        self.base_url = base_url.rstrip("/")
        self._token = None
        self.headers = {
            "Authorization": None,
            "Content-Type": "application/json"
        }

    def login(self) -> str:
        login_url = urljoin(self.base_url +"/", "auth/login")
        payload = {
            "user": self.email,
            "password": self.password
        }

        try:
            resp = requests.post(login_url, headers=self.headers, json=payload)
            resp.raise_for_status()
        except requests.HTTPError as e:
            raise RuntimeError(f"Login failed ({resp.status_code}): {resp.text}") from e

        self._token = resp.json()["token"].strip()
        self.headers["Authorization"] = f"Bearer {self._token}"
        print(self.headers)
        return resp.json()["token"]

    def logout(self) -> None:
        if not self._token:
            return
        logout_url = urljoin(self.base_url +"/", "logout")
        self.headers["Authorization"] = None
        requests.post(logout_url).raise_for_status()
        self._token = None

    def get_projects(self, include_hidden: bool = True) -> List:
        """Fetch all projects, handling pagination."""
        projects = []
        limit = 100
        offset = 0
        projects_url = urljoin(self.base_url + "/", "projects")

        while True:
            params = {
                "limit": limit,
                "offset": offset,
                "include_hidden": include_hidden}
            resp = requests.get(projects_url, headers=self.headers, params=params)
            resp.raise_for_status()

            data = resp.json()

            projects.extend(data)

            if len(data) < limit:
                break
            offset += limit

        return projects

    def get_project_entries(self) -> List[Dict[str, Any]]:
        """Fetch all entries across all projects."""
        project_entries = []
        limit = 50
        offset = 0
        ertries_url = urljoin(self.base_url + "/", "entries")

        while True:
            params = {
#                "sort": "title creation_date",
                "limit": limit,
                "offset": offset,
            }

            resp = requests.get(ertries_url, headers=self.headers, params=params)
            resp.raise_for_status()
            project_entries.extend(resp.json())

            data = resp.json()
            print(len(data))
            print()

            if len(data) < limit:
                break
            offset += limit

        return project_entries

    def get_entries(self) ->List:
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
