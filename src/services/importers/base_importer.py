import math
from abc import ABC, abstractmethod
from typing import Optional, Any, List, Dict

import pandas as pd
from elapi.api import FixedEndpoint
from responses import Response

from utils.content_extraction import ensure_series


class BaseImporter(ABC):
    """Abstract base class for resource and experiment importers."""

    @property
    @abstractmethod
    def df (self) -> pd.DataFrame:
        raise NotImplementedError()

    @property
    @abstractmethod
    def cols_lower (self) -> pd.DataFrame:
        raise NotImplementedError()

    @property
    @abstractmethod
    def endpoint (self) -> FixedEndpoint:
        raise NotImplementedError()

    def validate_category_id (self, cid: str) -> None:
        if not str(cid).isdigit():
            raise ValueError("Category ID must be numeric.")

    def resolve_category_col (self) -> Optional[str]:
        """
        Hook to resolve the category column name.
        Default: try to auto-detect from self.df columns.
        """
        for c in self.df.columns:
            key = str(c).lower().replace(" ", "").replace("-", "_")
            if "category_id" in key:
                return c
        return None

    # ---- Shared helpers ----
    def normalize_id (self, value: Any) -> Optional[str]:
        """Return a clean string id or None for empty/NaN values."""
        if value is None:
            return None

        if isinstance(value, float) and math.isnan(value):
            return None

        if isinstance(value, float) and value.is_integer():
            value = int(value)

        s = str(value).strip()

        if s in ("", "nan", "None", "none", "NaN"):
            return None

        return s

    def get_category_id (self, row: pd.Series) -> Optional[str]:
        """Extract and validate the category id from a single CSV row."""

        if row is None or not isinstance(row, pd.Series):
            return None

        col = self.resolve_category_col()

        if col is None or col not in row.index:
            return None

        cid = self.normalize_id(row[col])
        if cid is None:
            return None

        try:
            self.validate_category_id(cid)
        except ValueError as e:
            raise ValueError(f"Invalid Category ID: {cid}") from e

        return cid

    def get_elab_id (self, experiment: Response) -> Optional[str]:

        location = str(experiment.headers.get("Location"))  # type: ignore
        exp_id = location.rstrip("/").split("/")[-1]

        if not exp_id.isdigit():
            raise RuntimeError(f"Could not parse experiment ID: {exp_id!r}")

        return exp_id

    def get_title (self, row: pd.Series) -> Optional[str]:

        row = ensure_series(row)
        if row is None:
            return ""

        if not isinstance(row, pd.Series):
            try:
                row = pd.Series(row._asdict())
            except Exception:
                return None

        if "title" not in self.cols_lower:
            return ""

        title_val = row[self.cols_lower["title"]]

        if title_val is None or str(title_val).strip() == "":
            return ""

        return str(title_val).strip()

    def get_tags (self, row: pd.Series) -> List[str]:
        row = ensure_series(row)

        if "tags" not in self.cols_lower:
            return []

        val = row[self.cols_lower["tags"]]

        if pd.isna(val):
            return []

        if isinstance(val, (list, tuple, set)):
            return [str(x).strip() for x in val if str(x).strip()]

        if isinstance(val, str):
            return val.strip().split("|")

        s = str(val).strip()

        if not s or s.lower() in {"nan", "none", "null"}:
            return []

    def get_existing_json (self, elab_id: str) -> Optional[Dict]:
        response_json = self.endpoint.get(endpoint_id=elab_id).json()

        if isinstance(response_json, dict):
            return response_json

        return {}

    # TODO check if method works for resources as well
    def fetch_extra_fields (self, elab_json: Dict) -> Optional[pd.DataFrame]:
        metadata_decoded = elab_json.get("metadata_decoded", {})
        extra_fields = pd.DataFrame(metadata_decoded.get("extra_fields", []))
        if not isinstance(extra_fields, pd.DataFrame) or extra_fields.empty:
            return None

        filtered = extra_fields.loc["value"]
        result = filtered.T.reset_index()
        result.columns = ["title", "value"]
        result = result.rename(columns={
            "title": "extra_field_title",
            "value": "extra_field_value"
            })

        return result

    # def match_extra_fields (self, extra_fields_df : pd.DataFrame):

    # def update_elab_extra_fields (self, row):
    #     elab_id = row["id"]
    #     elab_title =
    #
    #     for col in row.index:
    #
    #
    #     elab_json = self.get_existing_json(id)
    #     if elab_json is None:
    #         return None
    #
    #     elab_extra_fields = self.fetch_extra_fields(elab_json)
    #     if elab_extra_fields is None:
    #         return None
    #
    #     for col in row.index:
    #         if col in

    # TODO compare extra fields from json with the csv
    # TODO user should be able to choose metadata.elabftw.display_main_text
    #  True or false

    # ----Shared Post request----
    def create_new (self, template: str) -> str:
        """Send a POST request for the creation of a new experiment or
        resource and add it to the collection."""
