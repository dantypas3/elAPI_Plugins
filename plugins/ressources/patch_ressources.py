import re
import pandas as pd
import json
import math
from pathlib import Path
from typing import Union, Optional
from elapi.api import FixedEndpoint
from elapi.validators import ValidationError, Validator

"""
This script validates and patches resources from a CSV file via a fixed API endpoint.
Created for: Universität Heidelberg – BZH - SFB 1638
Author: Dionysios Antypas (dionysios.antypas@bzh.uni-heidelberg.de)
Status: Work in progress

Description:
    - Validates the resource ID
    - Reads a CSV file with exactly one row of update data
    - Updates title, body, and metadata.extra_fields via API PATCH(elAPI) request

Dependencies:
    - pandas
    - elapi
    - Python 3.7+
"""

class FixedRessourceEndpoint:
    def __new__(cls, *args, **kwargs):
        return FixedEndpoint("items")

class RessourceIDValidator(Validator):
    def __init__(self, ressource_id: Union[str, int]):
        self.ressource_id = ressource_id
        self._ressource_endpoint = FixedRessourceEndpoint()

    @property
    def ressource_id(self):
        return self._ressource_id

    @ressource_id.setter
    def ressource_id(self, value):
        if value is None:
            raise ValidationError("Ressource_id cannot be None.")
        if not hasattr(value, "__str__"):
            raise ValidationError("Ressource ID must be convertible to string.")
        self._ressource_id = str(value)

    def validate(self):
        if re.match(r"^\d+$|^me$", self.ressource_id, re.IGNORECASE):
            try:
                return self._ressource_endpoint.get(endpoint_id=self._ressource_id).json()["id"]
            except KeyError:
                self._ressource_endpoint.close()
                raise
        raise ValidationError("Invalid ressource_id format.")


def patch_single_resource_from_csv(
    ressource_id: Union[str, int],
    input_csv: Union[Path, str],
    encoding: str = 'utf-8',
    separator: str = ';'
):
    from elapi.api.endpoint import FixedEndpoint

    print(f"Validating resource ID: {ressource_id}")
    RessourceIDValidator(ressource_id).validate()

    print(f"Reading CSV: {input_csv}")
    df = pd.read_csv(input_csv, encoding=encoding, sep=separator)
    df.columns = df.columns.str.strip()

    if len(df) != 1:
        raise ValueError("CSV must contain exactly one data row.")

    df = df.applymap(lambda x: x.item() if hasattr(x, 'item') else x)
    row = df.iloc[0]

    session = FixedEndpoint("items")
    print(f"Fetching resource {ressource_id} from API...")
    ressource = session.get(endpoint_id=ressource_id).json()

    if "title" in df.columns:
        print(f"Updating title to: {row['title']}")
        ressource["title"] = row["title"]
    if "body" in df.columns:
        print(f"Updating body to: {row['body']}")
        ressource["body"] = row["body"]

    raw_metadata = ressource.get("metadata")
    metadata = json.loads(raw_metadata) if isinstance(raw_metadata, str) else raw_metadata

    if isinstance(metadata.get("extra_fields"), str):
        metadata["extra_fields"] = json.loads(metadata["extra_fields"])

    for field in metadata.get("extra_fields", {}):
        if field in df.columns:
            value = row[field]
            if hasattr(value, 'item'):
                value = value.item()
            if value is None or (isinstance(value, float) and math.isnan(value)):
                continue
            metadata["extra_fields"][field]["value"] = str(value)
            print(f"Field '{field}' updated to: {metadata['extra_fields'][field]['value']}")
        else:
            print(f"Field '{field}' not found in CSV. Skipping.")

    payload = {
        "title": ressource.get("title"),
        "body": ressource.get("body"),
        "metadata": json.dumps(metadata)
    }

    print("Sending PATCH request...")
    patch_response = session.patch(endpoint_id=ressource_id, data=payload)

    print("Patch complete")
    if patch_response.status_code == 200:
        print("Patch complete")
    else:
        print(f"Failed to patch ressource {ressource_id}."
              f"Status code:", patch_response.status_code)