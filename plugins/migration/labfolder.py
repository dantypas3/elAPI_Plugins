import requests
import json
from PIL import Image
import cairosvg
from io import BytesIO
from datetime import datetime
from urllib.parse import urljoin
from typing import List, Dict, Any, Optional
from pathlib import Path

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
        login_url = f"{self.base_url}/auth/login"
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
        return resp.json()["token"]

    def logout(self) -> None:
        if not self._token:
            return
        logout_url = f"{self.base_url}/auth/logout"
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
                "sort": "creation_date",
                "limit": limit,
                "offset": offset,
            }

            resp = requests.get(ertries_url, headers=self.headers, params=params)
            resp.raise_for_status()
            project_entries.extend(resp.json())

            data = resp.json()

            if len(data) < limit:
                break
            offset += limit

        return project_entries

    def get_entry_elements(self):
        entries = []
        project_entries = self.get_project_entries()

        for entry in project_entries:
            date = entry['version_date']
            dt = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%f%z')
            date = dt.date().isoformat()
            contents= ""


            for element in entry.get("elements", []):
                element_type = element.get("type")
                element_id = element.get("id")

                if element_type == "TEXT":
                    text_url = f"{self.base_url}/elements/text/{element_id}"
                    text_respond = requests.get(text_url, headers=self.headers)
                    text_json = text_respond.json()
                    content = text_json.get("content", "")
                    contents += content + "\n"

                elif element["type"] == "FILE":
                    file_url = f"{self.base_url}/elements/file/{element_id}/download"

                    response = requests.get(file_url, headers=self.headers, stream=True)
                    filename = response.headers.get("Content-Disposition", "filename=attached_file").split(
                            "filename=")[1].strip('"')
                    temp_path = Path(f"/tmp_{filename}")

                    with open(temp_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)

                elif element_type == "DATA":
                    data_url = f"{self.base_url}/elements/data/{element_id}"
                    response = requests.get(data_url, headers=self.headers)
                    data_json = response.json()
                    #Should we keep this header for data?
                    contents += "DATA:\n" + json.dumps(data_json, indent=2) + "\n\n"

                elif element_type == "TABLE":
                    table_url = f"{self.base_url}/elements/table/{element_id}"
                    response = requests.get(table_url, headers=self.headers)
                    table_json = response.json()
                    #Should we keep this header for table?
                    contents += "TABLE:\n"
                    columns = table_json.get("columns", [])
                    rows = table_json.get("rows", [])
                    contents += "\t".join(columns) + "\n"
                    for row in rows:
                        contents += "\t".join(map(str, row)) + "\n"
                    contents += "\n"

                elif element_type == "IMAGE":
                    metadata_url = f"{self.base_url}/elements/image/{element_id}"
                    meta_resp = requests.get(metadata_url, headers=self.headers)
                    metadata = meta_resp.json()

                    filename = metadata.get("title", f"image_{element_id}.jpg")
                    image_path = Path(f"/tmp_{filename}")

                    download_url = f"{self.base_url}/elements/image/{element_id}/original-data"
                    img_resp = requests.get(download_url, headers=self.headers, stream=True)

                    content_disp = img_resp.headers.get("Content-Disposition", "")
                    if "filename=" in content_disp:
                        filename = content_disp.split("filename=")[1].strip('"')
                        image_path = Path(f"/tmp_{filename}")

                    with open(image_path, "wb") as f:
                        for chunk in img_resp.iter_content(chunk_size=8192):
                            f.write(chunk)

                    # Step 1: Open base image
                    base_img = Image.open(image_path).convert("RGBA")

                    # Step 2: Convert SVG annotation to PNG using cairosvg
                    svg_data = metadata.get("annotation_layer_svg")
                    if svg_data:
                        png_bytes = cairosvg.svg2png(bytestring=svg_data.encode("utf-8"),
                                                     output_width=base_img.width,
                                                     output_height=base_img.height)
                        overlay = Image.open(BytesIO(png_bytes)).convert("RGBA")

                        # Step 3: Combine base image + annotation overlay
                        combined = Image.alpha_composite(base_img, overlay)

                        # Step 4: Save final result
                        output_path = image_path.with_stem(f"{image_path.stem}_with_annotations")
                        combined.save(output_path)

            if contents:
                entries.append({
                    "date": date,
                    "text_content": contents.strip()
                })

        return entries

    def __enter__(self):
        """Allow `with Labfolder() as client:` to auto-login."""
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Auto-logout when exiting a `with` block."""
        self.logout()
