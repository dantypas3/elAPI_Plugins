import re
from typing import Union
from elapi.validators import Validator, ValidationError
from src.elabftw_client.utils.endpoints import get_fixed

_ID_PATTERN = re.compile(r"^\d+$|^me$", re.IGNORECASE)

class IDValidator(Validator):
    """Generic validator for any single-id endpoint."""
    def __init__(self, name: str, value: Union[str, int]):
        """
        name: one of “resource”, “category”, “experiment”… 
        value: the id to validate (string or int)
        """
        self.name = name
        self._value = str(value)
        self._endpoint = get_fixed(name)

    @property
    def value(self) -> str:
        return self.value

    @value.setter
    def value(self, v: Union[str, int]) -> None:
        if v is None:
            raise ValidationError(f"{self.name}_id cannot be None.")
        if not hasattr(v, "__str__"):
            raise ValidationError(f"{self.name}_id must be convertible to string.")
        self._value = str(v)

    def validate(self) -> int:
        if not _ID_PATTERN.match(self._value):
            raise ValidationError(f"Invalid {self.name}_id format.")
        try:
            data = self._endpoint.get(endpoint_id=self._value).json()
            return int(data["id"])
        except KeyError:
            self._endpoint.close()
            raise
