from typing import List
from pathlib import Path
from elabftw_client.utils.endpoints import get_fixed

import mimetypes


class Importer:
    """
    Wraps eLabFTW’s “experiments” endpoint to create and patch experiments, and upload files.
    """
    def create_experiment(self, title: str, tags: List[str]) -> str:
        resp = get_fixed("experiments").post(data={"title": title, "tags": tags})
        try:
            body = resp.json()
            exp_id = str(body.get("id", "")).strip()
        except ValueError:
            exp_id = ""
        if not exp_id:
            location = resp.headers.get("Location", "") or resp.headers.get("location", "")
            exp_id = location.rstrip("/").split("/")[-1]
        if not exp_id.isdigit():
            raise RuntimeError(f"Could not parse experiment ID: {exp_id!r}")
        return exp_id

    def patch_experiment(self, exp_id: str, body: str, category: int) -> None:
        if not exp_id.isdigit():
            raise ValueError(f"Invalid experiment ID: {exp_id!r}")
        get_fixed("experiments").patch(
            endpoint_id=exp_id,
            data={"body": body, "category": category},
        )

    def upload_file(self, exp_id: str, file_path: Path) -> None:
        """
        Upload a file attachment to the given experiment, preserving its MIME type.
        """
        if not exp_id.isdigit():
            raise ValueError(f"Invalid experiment ID for upload: {exp_id!r}")
        mime_type, _ = mimetypes.guess_type(file_path.as_posix())
        mime_type = mime_type or "application/octet-stream"
        with file_path.open("rb") as f:
            files = {"file": (file_path.name, f, mime_type)}

            get_fixed("experiments").post(
                endpoint_id=exp_id,
                sub_endpoint_name="uploads",
                files=files,
            )
