import json
import math
import warnings

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Dict, Mapping, Optional, Union

from elapi.api import FixedEndpoint

from src.utils.content_extraction import canonicalize

import logging

import numpy as np
import pandas as pd

from utils.csv_tools import CsvTools
from utils.endpoints import get_fixed
from utils.validators import IDValidator
from .base_importer import BaseImporter

logger = logging.getLogger(__name__)


class ResourcesImporter(BaseImporter):

    def __init__ (self, csv_path: Union[Path, str]) -> None:
        self._endpoint = get_fixed("resources")
        self._resources_df: pd.DataFrame = CsvTools.csv_to_df(csv_path)

        self._cols_lower: Mapping[str, str]
        self._cols_cannon: Mapping[str, str]
        self._cols_lower, self._cols_canon = self._build_column_indexes(
            self._resources_df.columns)

        self._category_col: Optional[str] = self._find_col_like("category_id")

        self._new_resources_counter = 0
        self._patched_resources_counter = 0

    @classmethod
    def _build_column_indexes (cls, columns: pd.Index) -> tuple[
        Dict[str, str], Dict[str, str]]:
        """Return (lower_map, canon_map) with best-effort collision handling."""
        lower_map: Dict[str, str] = {}
        canon_map: Dict[str, str] = {}

        for original in columns:
            lower_key = original.lower()
            canon_key = canonicalize(original)

            "title : tITle"
            "title : TITLE"

            if lower_key not in lower_map:
                lower_map[lower_key] = original
            elif lower_map[lower_key] != original:
                logger.debug("Lowercase column collision: %r vs %r for key %r",
                             lower_map[lower_key], original, lower_key)

            if canon_key not in canon_map:
                canon_map[canon_key] = original
            elif canon_map[canon_key] != original:
                logger.warning(
                    "Canonical column collision: %r vs %r for key %r",
                    canon_map[canon_key], original, canon_key)

        return lower_map, canon_map

    def _find_col_like (self, target: str) -> Optional[str]:
        """Return the original column whose canonical name contains the target."""
        target = canonicalize(target)
        for canon_key, original in self._cols_canon.items():
            if target in canon_key:
                return original
        return None

    # ---------- Public conveniences ----------------------------------------

    def get_column (self, name: str) -> Optional[str]:
        """Resolve a possibly-messy column name to the original column in the DataFrame.

        Tries canonical match, then case-insensitive match. Returns None if not found.
        """
        canon = canonicalize(name)
        if canon in self._cols_canon:
            return self._cols_canon[canon]

        lower = name.lower()
        return self._cols_lower.get(lower)

    @property
    def category_col (self) -> Optional[str]:
        """Original column name that represents the category id, if present."""
        return self._category_col

    @property
    def df (self) -> pd.DataFrame:
        return self._resources_df

    @property
    def cols_lower (self) -> Mapping[str, str]:
        return self._cols_lower

    @property
    def endpoint (self) -> FixedEndpoint:
        return self._endpoint

    def attach_files (self, id, file_path) -> None:
        if not id.isdigit():
            raise ValueError(f"Invalid experiment ID for upload: {id!r}")

        with file_path.open("rb") as file:
            files = {
                "file": (file_path.name, file)
                }

            attach_file = self.endpoint.post(endpoint_id=id,
                                             sub_endpoint_name="uploads",
                                             files=files)
            return

    def create_new (self, row: pd.Series, template: str = "") -> str:

        title_col = self._find_col_like("title")
        if not title_col:
            raise ValueError("No 'title' column found in the resources CSV.")

        path_col = self._find_col_like("files_path")
        if not path_col:
            raise ValueError(
                "No 'files_path' column found in the resources CSV.")

        title_val = str(row[title_col]) if not pd.isna(row[title_col]) else ""
        files_dir = row[path_col] if path_col in row else ""
        tags_val = self._get_tags(row)

        payload = {
            "title"   : title_val,
            "tags"    : tags_val,
            "template": template,
            }

        resp = self.endpoint.post(data=payload)
        try:
            resp.raise_for_status()
        except Exception:
            raise RuntimeError(f"Creation of {title_val!r} failed with status "
                               f"{resp.status_code}: {resp.text}")

        resource_id = str(self.get_elab_id(resp))
        if files_dir:
            self.attach_files(resource_id, files_dir)

        self._new_resources_counter += 1
        return resource_id

    # def import_resources (self, csv_path: Union[Path, str],  #                       category_id: int = None, is_new: bool = True) -> int:  #  #     new_resources = 0  #  #     IDValidator("categories", category_id).validate()  #  #     resources_df = CsvTools.csv_to_df(csv_path)  #  #     for _, row in resources_df.iterrows():  #         new_resource = self._endpoint  #  #         resource: Dict[str, Any] = {}  #         resource_id: int  #         tags: List[str] = []  #  #         if is_new:  #  #             if "title" in resources_df.columns:  #                 title = resources_df["title"]  #  #             if "tags" in resources_df.columns:  #                 tag_list = resources_df["tags"]  #                 if isinstance(tag_list, np.ndarray):  #                     tags.extend(tag_list.tolist())  #                 elif isinstance(tag_list, list):  #                     tags.extend(tag_list)  #  #             data = {  #                 "title"   : row["title"],  #                 "template": category_id,  #                 "tags"    : tags  #                 }  #  #             resp = new_resource.post(data=data)  #  #             location = (resp.headers.get("Location",  #                                          "") or resp.headers.get(  #                 "location", ""))  #  #             new_resource_id = location.rstrip("/").split("/")[-1]  #  #         else:  #             resource_id = row["resource_id"]  #  #             if "title" in resources_df.columns:  #                 resource["title"] = row["title"]  #  #         if "date" in resources_df.columns:  #             date = row["date"]  #             dt = datetime.strptime(date, "%d.%m.%Y")  #             date = dt.date().isoformat()  #             resource["date"] = date  #         if "rating" in resources_df.columns:  #             resource["rating"] = row["rating"]  #         if "category" in resources_df.columns:  #             resource["category"] = row["category"]  #         if "locked" in resources_df.columns:  #             if resources_df["locked"] == 0:  #                 resource["locked"] = 0  #             else:  #                 resource["locked"] = 1  #         if "userid" in resources_df.columns:  #             resource["userid"] = row["userid"]  #         if "is_bookable" in resources_df.columns:  #             resource["is_bookable"] = row["is_bookable"]  #         if "status" in resources_df.columns:  #             resource["status"] = str(row["status"])  #         if "body" in resources_df.columns:  #             resource["body"] = row["body"]  #  #         raw_metadata = resource.get("metadata")  #         metadata = json.loads(raw_metadata) if isinstance(raw_metadata,  #                                                           str) else (  #             raw_metadata)  #  #         if isinstance(metadata.get("extra_fields"), str):  #             metadata["extra_fields"] = json.loads(metadata["extra_fields"])  #  #         extra_fields = metadata.get("extra_fields", {})  #         known_fields = {"resource_id", "title", "body"}  #         unexpected_columns = [col for col in resources_df.columns if  #                               col not in extra_fields and col not in known_fields]  #  #         if unexpected_columns:  #             warnings.warn(  #                 f"Unexpected columns in CSV not found in metadata["  #                 f"'extra_fields']: {unexpected_columns}")  #  #         for field in extra_fields:  #             if field in df.columns:  #                 value = row[field]  #                 if hasattr(value, 'item'):  #                     value = value.item()  #                 if value is None or (  #                         isinstance(value, float) and math.isnan(value)):  #                     value = ""  #                 metadata["extra_fields"][field]["value"] = str(value)  #                 print(f"Field '{field}' updated to: "  #                       f"{metadata['extra_fields'][field]['value']}")  #             else:  #                 print(f"Field '{field}' not found in CSV. Skipping.")  #  #         patch_response = new_resource.patch(endpoint_id=row['id'],  #                                             data=resource)  #  #         if patch_response.status_code == 200:  #             print(f"Patch of resource {row['id']} complete")  #         else:  #             print(f"Failed to patch resource {row['id']}.\n"  #                   f"Status code: {patch_response.status_code}\n",  #                   f"Response: {patch_response.text}")  #  #     return new_resources
