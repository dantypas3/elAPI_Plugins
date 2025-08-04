import json
import math
import numpy as np
import warnings
from datetime import datetime
from pathlib import Path
from typing import Union, List, Dict, Any

from src.elabftw_client.utils.csv_tools import CsvTools
from src.elabftw_client.utils.endpoints import get_fixed
from src.elabftw_client.utils.validators import IDValidator
from .base_importer import BaseImporter


class ResourcesImporter(BaseImporter):

    def __init__ (self) -> None:
        self._endpoint = get_fixed("resources")

    def import_resources (self, csv_path: Union[Path, str],
                          category_id: int = None,
                          is_new: bool = True) -> int:

        new_resources = 0

        IDValidator("categories", category_id).validate()

        resources_df = CsvTools.csv_to_df(csv_path)

        for _, row in resources_df.iterrows():
            new_resource = self._endpoint

            resource :Dict[str, Any] = {}
            resource_id : int
            tags : List[str] = []

            if is_new:

                if "title" in resources_df.columns:
                    title = resources_df["title"]

                if "tags" in resources_df.columns:
                    tag_list = resources_df["tags"]
                    if isinstance(tag_list, np.ndarray):
                        tags.extend(tag_list.tolist())
                    elif isinstance(tag_list, list):
                        tags.extend(tag_list)

                data = {
                    "title"     : row["title"],
                    "template"  : category_id,
                    "tags"      : tags
                    }

                resp = new_resource.post(data=data)

                location = (resp.headers.get("Location", "") or
                            resp.headers.get("location", ""))

                new_resource_id = location.rstrip("/").split("/")[-1]

            else:
                resource_id = row["resource_id"]

                if "title" in resources_df.columns:
                    resource["title"] = row["title"]

            if "date" in resources_df.columns:
                date = row["date"]
                dt = datetime.strptime(date, "%d.%m.%Y")
                date = dt.date().isoformat()
                resource["date"] = date
            if "rating" in resources_df.columns:
                resource["rating"] = row["rating"]
            if "category" in resources_df.columns:
                resource["category"] = row["category"]
            if "locked" in resources_df.columns:
                if resources_df["locked"] == 0:
                    resource["locked"] = 0
                else:
                    resource["locked"] = 1
            if "userid" in resources_df.columns:
                resource["userid"] = row["userid"]
            if "is_bookable" in resources_df.columns:
                resource["is_bookable"] = row["is_bookable"]
            if "status" in resources_df.columns:
                resource["status"] = str(row["status"])
            if "body" in resources_df.columns:
                resource["body"] = row["body"]

            raw_metadata = resource.get("metadata")
            metadata = json.loads(raw_metadata) if isinstance(raw_metadata,
                                                              str) else (
                raw_metadata)

            if isinstance(metadata.get("extra_fields"), str):
                metadata["extra_fields"] = json.loads(metadata["extra_fields"])

            extra_fields = metadata.get("extra_fields", {})
            known_fields = {"resource_id", "title", "body"}
            unexpected_columns = [col for col in resources_df.columns if
                                  col not in extra_fields and col not in
                                  known_fields]

            if unexpected_columns:
                warnings.warn(
                    f"Unexpected columns in CSV not found in metadata["
                    f"'extra_fields']: {unexpected_columns}")

            for field in extra_fields:
                if field in df.columns:
                    value = row[field]
                    if hasattr(value, 'item'):
                        value = value.item()
                    if value is None or (
                            isinstance(value, float) and math.isnan(value)):
                        value = ""
                    metadata["extra_fields"][field]["value"] = str(value)
                    print(
                        f"Field '{field}' updated to: "
                        f"{metadata['extra_fields'][field]['value']}")
                else:
                    print(f"Field '{field}' not found in CSV. Skipping.")

            patch_response = new_resource.patch(endpoint_id=row['id'], data=resource)

            if patch_response.status_code == 200:
                print(f"Patch of resource {row['id']} complete")
            else:
                print(f"Failed to patch resource {row['id']}.\n"
                      f"Status code: {patch_response.status_code}\n",
                      f"Response: {patch_response.text}")

        return new_resources