#ressource_utils.py
import re
from elapi.api import FixedEndpoint
from elapi.validators import ValidationError, Validator
from typing import Union, Optional


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