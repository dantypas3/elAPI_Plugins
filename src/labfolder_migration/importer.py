import json
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional

from elabftw_client.utils.endpoints import get_fixed


class Importer:
    """
    Wraps eLabFTW’s “experiments” endpoint to create, patch experiments,
    and upload file attachments.
    """

    def create_experiment (self, title: str, tags: List[str]) -> str:
        resp = get_fixed("experiments").post(data={
            "title": title,
            "tags" : tags,
            })
        try:
            body = resp.json()
            exp_id = str(body.get("id", "")).strip()
        except ValueError:
            exp_id = ""
        if not exp_id:
            location = resp.headers.get("Location", "") or resp.headers.get(
                "location", "")
            exp_id = location.rstrip("/").split("/")[-1]
        if not exp_id.isdigit():
            raise RuntimeError(f"Could not parse experiment ID: {exp_id!r}")
        return exp_id

    def patch_experiment (self, exp_id: str, body: str, category: int,
                          uid: Optional[int] = None, extra_fields: Optional[
                Dict[str, Any]] = None, ) -> None:
        if not exp_id.isdigit():
            raise ValueError(f"Invalid experiment ID: {exp_id!r}")

        ep = get_fixed("experiments")

        # 1) fetch current to preserve existing metadata.elabftw
        current = ep.get(endpoint_id=exp_id).json()
        raw_meta = current.get("metadata") or {}
        # if metadata came back as string, parse it
        if isinstance(raw_meta, str):
            try:
                metadata = json.loads(raw_meta)
            except json.JSONDecodeError:
                metadata = {}
        else:
            metadata = raw_meta

        # 2) keep or default the elabftw block
        elab_meta = metadata.get("elabftw", {
            "display_main_text"  : True,
            "extra_fields_groups": []
            })

        # 3) build an 'extra_fields' dict of simple strings
        ef_payload: Dict[str, Any] = {}
        if extra_fields:
            for k, v in extra_fields.items():
                ef_payload[k] = {
                    "type"       : "string",
                    "value"      : str(v),
                    "group_id"   : 0,
                    "description": "",
                    }
            # ensure group 0 is present
            groups = set(elab_meta.get("extra_fields_groups", []))
            groups.add(0)
            elab_meta["extra_fields_groups"] = sorted(groups)

        # 4) assemble the full metadata object
        new_meta: Dict[str, Any] = {
            "elabftw": elab_meta
            }
        if ef_payload:
            new_meta["extra_fields"] = ef_payload

        # 5) now PATCH using exactly the same shape your CSV script did:
        payload: Dict[str, Any] = {
            "body"    : body,
            "category": category,  # serialize metadata to JSON-string
            "metadata": json.dumps(new_meta),
            "userid"  : uid,
            }

        ep.patch(endpoint_id=exp_id, data=payload)

    def upload_file (self, exp_id: str, file_path: Path) -> None:
        if not exp_id.isdigit():
            raise ValueError(f"Invalid experiment ID for upload: {exp_id!r}")

        mime_type, _ = mimetypes.guess_type(file_path.as_posix())
        mime_type = mime_type or "application/octet-stream"
        with file_path.open("rb") as f:
            files = {
                "file": (file_path.name, f, mime_type)
                }
            get_fixed("experiments").post(endpoint_id=exp_id,
                                          sub_endpoint_name="uploads",
                                          files=files, )
