import json
import math
import warnings
from datetime import datetime
from pathlib import Path
from typing import Union, Optional

from src.elabftw_client.utils.csv_tools import CsvTools
from src.elabftw_client.utils.endpoints import get_fixed
from src.elabftw_client.utils.validators import IDValidator
from .base_importer import BaseImporter


class ResourcesImporter(BaseImporter):

    def __init__ (self) -> None:
        self._endpoint = get_fixed("resources")

    def create_new (self, category_id: int = None,
                    csv_path: Optional[Union[Path, str]] = None) -> int:

        new_resources = 0
        IDValidator("categories", category_id).validate()

        resources_df = CsvTools.csv_to_df(csv_path)

        for index, row in resources_df.iterrows():
            new_resource = self._endpoint

            data = {
                "title"   : row["title"],
                "template": category_id
                }

            post = new_resource.post(data=data)

            # print(
            #     f"\nProcessing row {index} - Validating resource ID: {row['id']}")
            #
            # utils.ResourceIDValidator(row['id']).validate()

            if "title" in resources_df.columns:
                print(f"Updating title to: {row['title']}")
                resource["title"] = row["title"]
            if "date" in resources_df.columns:
                print(f"Updating date to: {row['date']}")
                date = row["date"]
                dt = datetime.strptime(date, "%d.%m.%Y")
                date = dt.date().isoformat()
                resource["date"] = date
            if "rating" in resources_df.columns:
                print(f"Updating rating to: {row['rating']}")
                resource["rating"] = row["rating"]
            if "category" in resources_df.columns:
                print(f"Updating category to: {row['category']}")
                resource["category"] = row["category"]
            # if "locked" in df.columns:
            #     print(f"Updating locked to: {row['locked']}")
            #     resource["locked"] = row["locked"]
            if "userid" in resources_df.columns:
                print(f"Updating userid to: {row['userid']}")
                resource["userid"] = row["userid"]
            # if "lastchangeby" in df.columns:
            #     print(f"Updating lastchangeby to: {row['lastchangeby']}")
            #     resource["lastchangeby"] = row["lastchangeby"]
            if "is_bookable" in resources_df.columns:
                print(f"Updating is_bookable to: {row['is_bookable']}")
                resource["is_bookable"] = row["is_bookable"]
            if "status" in resources_df.columns:
                print(f"Updating status to: {row['status']}")
                resource["status"] = str(row["status"])
            if "body" in resources_df.columns:
                print(f"Updating body to: {row['body']}")
                resource["body"] = row["body"]
            # TODO locked

            raw_metadata = resource.get("metadata")
            metadata = json.loads(raw_metadata) if isinstance(raw_metadata,
                                                              str) else raw_metadata

            if isinstance(metadata.get("extra_fields"), str):
                metadata["extra_fields"] = json.loads(metadata["extra_fields"])

            extra_fields = metadata.get("extra_fields", {})
            known_fields = {"resource_id", "title", "body"}
            unexpected_columns = [col for col in resources_df.columns if
                                  col not in extra_fields and col not in known_fields]

            if unexpected_columns:
                warnings.warn(
                    f"Unexpected columns in CSV not found in metadata['extra_fields']: {unexpected_columns}")

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
                        f"Field '{field}' updated to: {metadata['extra_fields'][field]['value']}")
                else:
                    print(f"Field '{field}' not found in CSV. Skipping.")

            payload = {
                "title"       : resource.get("title"),
                "body"        : resource.get("body"),
                "date"        : resource.get("date"),
                "rating"      : resource.get("rating"),
                "category"    : resource.get("category"),
                #    "locked": resource.get("locked"),
                "userid"      : int(resource.get("userid")),
                # "lastchangeby": resource.get("lastchangeby"),
                "is_bookable" : resource.get("is_bookable"),
                "status_title": resource.get("status"),
                "metadata"    : json.dumps(metadata)
                }

            print("Sending PATCH request...")
            patch_response = session.patch(endpoint_id=row['id'], data=payload)

            if patch_response.status_code == 200:
                print(f"Patch of resource {row['id']} complete")
            else:
                print(f"Failed to patch resource {row['id']}.\n"
                      f"Status code: {patch_response.status_code}\n",
                      f"Response: {patch_response.text}")

        return new_resources

    def update_existing (self, csv_path: Union[Path, str], category_id: int,
                         encoding: str = "utf-8",
                         separator: str = ";", ) -> int:
        pass
