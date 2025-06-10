import pandas as pd
import json
import math
import warnings
from utils import resource_utils as utils
from datetime import datetime
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

    df.columns = df.columns.str.strip()
    df.fillna("", inplace=True)

    if len(df) < 1:
        raise ValueError("CSV must contain at least one data row.")
    if "id" not in df.columns:
        raise ValueError("Expected column 'id' not found in CSV file.")


    df = df.map(lambda x: x.item() if hasattr(x, 'item') else x)

    for index, row in df.iterrows():
        print(f"\nProcessing row {index} - Validating resource ID: {row['id']}")
        utils.ResourceIDValidator(row['id']).validate()
        session = utils.FixedResourceEndpoint()

        print(f"Fetching resource {row['id']} from API...")
        resource = session.get(endpoint_id=row['id']).json()

        if "title" in df.columns:
            print(f"Updating title to: {row['title']}")
            resource["title"] = row["title"]
        if "date" in df.columns:
            print(f"Updating date to: {row['date']}")
            date = row["date"]
            dt = datetime.strptime(date, "%d.%m.%Y")
            date = dt.date().isoformat()
            resource["date"] = date
        if "rating" in df.columns:
            print(f"Updating rating to: {row['rating']}")
            resource["rating"] = row["rating"]
        if "category" in df.columns:
            print(f"Updating category to: {row['category']}")
            resource["category"] = row["category"]
        if "userid" in df.columns:
            print(f"Updating userid to: {row['userid']}")
            resource["userid"] = row["userid"]
        if "is_bookable" in df.columns:
            print(f"Updating is_bookable to: {row['is_bookable']}")
            resource["is_bookable"] = row["is_bookable"]
#        if "status" in df.columns:
#            print(f"Updating status to: {row['status']}")
#            resource["status"] = str(row["status"])
        if "body" in df.columns:
            print(f"Updating body to: {row['body']}")
            resource["body"] = row["body"]

        raw_metadata = resource.get("metadata")
        metadata = json.loads(raw_metadata) if isinstance(raw_metadata, str) else raw_metadata

        if isinstance(metadata.get("extra_fields"), str):
            metadata["extra_fields"] = json.loads(metadata["extra_fields"])

        extra_fields = metadata.get("extra_fields", {})
        unexpected = [c for c in df.columns if c not in extra_fields and c not in {"resource_id","title","body"}]
        if unexpected:
            warnings.warn(f"Unexpected columns: {unexpected}")
        for field in extra_fields:
            if field in df.columns:
                v = row[field]
                if hasattr(v, 'item'):
                    v = v.item()
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    v = ""
                metadata["extra_fields"][field]["value"] = str(v)

        payload = {
            "title":        resource.get("title"),
            "body":         resource.get("body"),
            "date":         resource.get("date"),
            "rating":       resource.get("rating"),
            "category":     resource.get("category"),
            "action":       "lock",
            "locked":       resource.get("locked"),
            "userid":       int(resource.get("userid")),
            "is_bookable":  resource.get("is_bookable"),
            "metadata":     json.dumps(metadata)
        }

        resp = session.patch(endpoint_id=row['id'], data=payload)
        if resp.status_code == 200:
            print(f"Patched resource {row['id']}")
        else:
            print(f"Failed {row['id']}: {resp.status_code} {resp.text}")
