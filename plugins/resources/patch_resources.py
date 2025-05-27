import pandas as pd
import json
import math
from utils import resource_utils as utils
from pathlib import Path
from typing import Union

"""

This script validates and patches resources from a CSV file via a fixed API endpoint.
Created for: Universität Heidelberg – BZH - SFB 1638
Author: Dionysios Antypas (dionysios.antypas@bzh.uni-heidelberg.de)
Status: Work in progress

Description:
    - Validates the resource ID
    - Reads a CSV file with exactly one row of update data
    - Updates title, body, and metadata.extra_fields via API PATCH (elAPI) request
    
"""

def patch_resources_from_csv(csv_path: Union[Path, str], encoding: str = 'utf-8', separator: str = ';'):
    """
    Patch existing resources from a CSV file.
    The CSV must contain a column named "resource_id" with the ID of each resource (one per row).
    """

    print(f"Reading CSV: {csv_path}")
    try:
        df = pd.read_csv(csv_path, encoding=encoding, sep=separator)
    except Exception as e:
        raise ValueError(f"Failed to read CSV: {csv_path}: {e}")

    df.columns = df.columns.str.strip().str.lower()

    if len(df) < 1:
        raise ValueError("CSV must contain at least one data row.")
    if "resource_id" not in df.columns:
        raise ValueError("Expected column 'resource_id' not found in CSV file.")


    df = df.applymap(lambda x: x.item() if hasattr(x, 'item') else x)

    for index, row in df.iterrows():
        print(f"\nProcessing row {index} - Validating resource ID: {row['resource_id']}")
        utils.ResourceIDValidator(row['resource_id']).validate()
        session = utils.FixedResourceEndpoint()

        print(f"Fetching resource {row['resource_id']} from API...")
        resource = session.get(endpoint_id=row['resource_id']).json()

        if "title" in df.columns:
            print(f"Updating title to: {row['title']}")
            resource["title"] = row["title"]
        if "body" in df.columns:
            print(f"Updating body to: {row['body']}")
            resource["body"] = row["body"]

        raw_metadata = resource.get("metadata")
        metadata = json.loads(raw_metadata) if isinstance(raw_metadata, str) else raw_metadata

        if isinstance(metadata.get("extra_fields"), str):
            metadata["extra_fields"] = json.loads(metadata["extra_fields"])

        extra_fields = metadata.get("extra_fields", {})
        known_fields = {"resource_id", "title", "body"}
        unexpected_columns = [col for col in df.columns if col not in extra_fields and col not in known_fields]

        if unexpected_columns:
            raise KeyError(f"Unexpected columns in CSV not found in metadata['extra_fields']: {unexpected_columns}")

        for field in extra_fields:
            if field in df.columns:
                value = row[field]
                if hasattr(value, 'item'):
                    value = value.item()
                if value is None or (isinstance(value, float) and math.isnan(value)):
                    value = ""
                metadata["extra_fields"][field]["value"] = str(value)
                print(f"Field '{field}' updated to: {metadata['extra_fields'][field]['value']}")
            else:
                print(f"Field '{field}' not found in CSV. Skipping.")

        payload = {
            "title": resource.get("title"),
            "body": resource.get("body"),
            "metadata": json.dumps(metadata)
        }

        print("Sending PATCH request...")
        patch_response = session.patch(endpoint_id=row['resource_id'], data=payload)

        if patch_response.status_code == 200:
            print(f"Patch of resource {row['resource_id']} complete")
        else:
            print(f"Failed to patch resource {row['resource_id']}.\n"
                  f"Status code: {patch_response.status_code}\n",
                  f"Response: {patch_response.text}")