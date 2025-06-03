import re
from elapi.api import FixedEndpoint
from elapi.validators import ValidationError, Validator
from typing import Union
from pathlib import Path


"""
Created for: Universität Heidelberg – BZH - SFB 1638
Author: Dionysios Antypas (dionysios.antypas@bzh.uni-heidelberg.de)
Status: Work in progress
"""

class FixedResourceEndpoint:
    def __new__(cls, *args, **kwargs):
        return FixedEndpoint("items")

class FixedCategoryEndpoint:
    def __new__(cls, *args, **kwargs):
        return FixedCategoryEndpoint("items_types")

class ResourceIDValidator(Validator):
    def __init__(self, ressource_id: Union[str, int]):
        self.resource_id = ressource_id
        self._resource_endpoint = FixedResourceEndpoint()

    @property
    def resource_id(self):
        return self._resource_id

    @resource_id.setter
    def resource_id(self, value):
        if value is None:
            raise ValidationError("Resource_id cannot be None.")
        if not hasattr(value, "__str__"):
            raise ValidationError("Resource ID must be convertible to string.")
        self._resource_id = str(value)

    def validate(self):
        if re.match(r"^\d+$|^me$", self.resource_id, re.IGNORECASE):
            try:
                return self._resource_endpoint.get(endpoint_id=self._resource_id).json()["id"]
            except KeyError:
                self._resource_endpoint.close()
                raise
        raise ValidationError("Invalid resource_id format.")

def is_file_created_and_not_empty(file_path: str) -> bool:
    file = Path(file_path)
    return file.exists() and file.stat().st_size > 0