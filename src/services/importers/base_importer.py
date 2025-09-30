"""
This module defines :class:`BaseImporter`, an abstract base class for
importing data into ElabFTW endpoints.  It provides shared helpers for
normalising identifiers, resolving category columns, extracting titles,
parsing tag lists and updating ``metadata.extra_fields`` on existing
resources or experiments.

Concrete importers should subclass :class:`BaseImporter` and implement
the :attr:`df`, :attr:`cols_lower` and :attr:`endpoint` properties.
"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import pandas as pd  # type: ignore
from elapi.api import FixedEndpoint  # type: ignore
from responses import Response  # type: ignore

try:
    # Prefer the canonicalise function from our project if available
    from src.utils.content_extraction import canonicalize  # type: ignore
except Exception:  # pragma: no cover
    try:
        from utils.content_extraction import canonicalize  # type: ignore
    except Exception:
        def canonicalize (s: str) -> str:  # type: ignore
            """Fallback canonicalise implementation: lower‑case and strip non‑alphanumerics."""
            return "".join(c for c in str(s).lower() if c.isalnum())

logger = logging.getLogger(__name__)


class BaseImporter(ABC):
    """Abstract base class for resource and experiment importers.

    Subclasses must expose three properties:

    * :attr:`df`: The underlying :class:`pandas.DataFrame` of CSV data.
    * :attr:`cols_lower`: A mapping from lower‑case column names to their
      original names.  This facilitates case‑insensitive lookup.
    * :attr:`endpoint`: A :class:`FixedEndpoint` instance exposing
      ``get``, ``post`` and ``patch`` methods.

    This base class implements generic helpers such as normalising ids,
    extracting category ids, titles and tags, and updating extra fields in
    metadata.  Concrete importers can build upon these to provide more
    specialised behaviour.
    """

    # --- Required API ---
    @property
    @abstractmethod
    def df (self) -> pd.DataFrame:
        """Return the DataFrame backing the importer."""
        raise NotImplementedError

    @property
    @abstractmethod
    def cols_lower (self) -> Mapping[str, str]:
        """Return a mapping from lower‑case column names to the original names."""
        raise NotImplementedError

    @property
    @abstractmethod
    def endpoint (self) -> FixedEndpoint:
        """Return the endpoint used to interact with ElabFTW."""
        raise NotImplementedError

    # --- Category handling ---
    def validate_category_id (self, cid: str) -> None:
        """Validate that a category ID is numeric.

        :param cid: The category identifier to validate.
        :raises ValueError: If the identifier is not composed solely of digits.
        """
        if not str(cid).isdigit():
            raise ValueError("Category ID must be numeric.")

    def resolve_category_col (self) -> Optional[str]:
        """Try to identify the column storing category ids from the DataFrame.

        A canonicalised match on the string ``"category_id"`` is used.  If
        no such column exists ``None`` is returned.  Concrete subclasses may
        override this method to enforce a specific column name.
        """
        for c in self.df.columns:
            if canonicalize(c).startswith(
                    "categoryid") or "categoryid" in canonicalize(c):
                return c
        return None

    def normalize_id (self, value: Any) -> Optional[str]:
        """Return a normalised identifier or ``None`` if the value is empty.

        * ``None`` and NaN values yield ``None``.
        * Float integers (e.g. ``5.0``) are coerced to ``5``.
        * Strings are stripped of leading/trailing whitespace.
        * Common null representations (``"nan"``, ``"none"``, etc.) yield ``None``.

        :param value: The raw value from a CSV cell.
        :returns: A cleaned string or ``None`` if empty.
        """
        if value is None:
            return None
        if isinstance(value, float) and math.isnan(value):
            return None
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        s = str(value).strip()
        if s.lower() in {"", "nan", "none", "null"}:
            return None
        return s

    def get_category_id (self, row: pd.Series) -> Optional[str]:
        """Extract and validate the category id from a row.

        If the category column is missing or the value is empty, ``None`` is
        returned.  Otherwise the id is normalised and validated as numeric.

        :param row: A row from the CSV as a Series.
        :returns: The category id or ``None`` if unavailable.
        :raises ValueError: If the id is non‑numeric.
        """
        if row is None or not isinstance(row, pd.Series):
            return None
        col = self.resolve_category_col()
        if col is None or col not in row:
            return None
        cid = self.normalize_id(row[col])
        if cid is None:
            return None
        self.validate_category_id(cid)
        return cid

    # --- HTTP helpers ---
    def get_elab_id (self, response: Response) -> str:
        """Extract the numeric identifier from a ``Location`` header.

        :param response: The HTTP response from a POST request.
        :returns: A numeric identifier as a string.
        :raises RuntimeError: If the id cannot be parsed.
        """
        location = str(response.headers.get("Location"))
        exp_id = location.rstrip("/").split("/")[-1]
        if not exp_id.isdigit():
            raise RuntimeError(f"Could not parse experiment ID: {exp_id!r}")
        return exp_id

    # --- Column extraction ---
    def get_title (self, row: pd.Series) -> Optional[str]:
        """Return the title value from a row.

        Column lookup is case‑insensitive via :attr:`cols_lower`.  Empty or
        missing titles return ``None``.

        :param row: A row from the CSV.
        :returns: The stripped title or ``None``.
        """
        if row is None:
            return None
        if not isinstance(row, pd.Series):
            try:
                # Attempt to coerce to Series (e.g. from a namedtuple)
                row = pd.Series(row._asdict())  # type: ignore[attr-defined]
            except Exception:
                return None
        title_col = self.cols_lower.get("title")
        if not title_col or title_col not in row:
            return None
        title_val = row[title_col]
        if title_val is None or str(title_val).strip() == "":
            return None
        return str(title_val).strip()

    def get_tags (self, row: pd.Series) -> List[str]:
        """Parse the tags column from a row into a list.

        Tags may be stored as a list/tuple/set, a pipe/semicolon/comma separated
        string or any scalar value.  Empty or missing tags return an empty
        list.

        :param row: A row from the CSV.
        :returns: A list of tags.
        """
        if row is None:
            return []
        tags_col = self.cols_lower.get("tags")
        if not tags_col or tags_col not in row:
            return []
        val = row[tags_col]
        if pd.isna(val):
            return []
        if isinstance(val, (list, tuple, set)):
            return [str(x).strip() for x in val if str(x).strip()]
        if isinstance(val, str):
            # Split on common delimiters
            for delim in [";", ",", "|"]:
                if delim in val:
                    parts = val.split(delim)
                    break
            else:
                parts = [val]
            return [p.strip() for p in parts if p.strip()]
        s = str(val).strip()
        if not s or s.lower() in {"nan", "none", "null"}:
            return []
        return [s]

    # --- Existing record helpers ---
    def get_existing_json (self, elab_id: str) -> Dict[str, Any]:
        """Retrieve the existing JSON representation for an id.

        :param elab_id: The identifier of the resource or experiment.
        :returns: A dictionary representing the JSON record; empty if an
          error occurs or no JSON is returned.
        """
        try:
            response = self.endpoint.get(endpoint_id=elab_id)
            response_json = response.json()
            if isinstance(response_json, dict):
                return response_json
        except Exception as exc:
            logger.warning("Failed to fetch existing JSON for id %s: %s",
                           elab_id, exc)
        return {}

    def fetch_extra_fields_mapping (self, elab_json: Dict[str, Any]) -> Dict[
        str, Dict[str, Any]]:
        """Return a mapping from canonicalised extra field titles to their definitions.

        :param elab_json: The existing JSON record containing ``metadata_decoded``.
        :returns: A mapping keyed by canonical titles.
        """
        metadata_decoded = elab_json.get("metadata_decoded", {})
        extra_fields = metadata_decoded.get("extra_fields", [])
        mapping: Dict[str, Dict[str, Any]] = {}
        if isinstance(extra_fields, list):
            for field in extra_fields:
                if not isinstance(field, dict):
                    continue
                title = field.get("title") or field.get("slug") or field.get(
                    "name")
                if title:
                    mapping[canonicalize(title)] = field
        return mapping

    def update_extra_fields_from_row (self, elab_id: str, row: pd.Series,
                                      known_columns: Iterable[str]) -> None:
        """Patch extra fields on the existing record using values from the CSV row.

        Any CSV column whose canonicalised name matches an existing extra field
        title (and is not listed in ``known_columns``) will be used to update
        that field's ``value``.  Missing values are converted to the empty
        string.

        :param elab_id: The identifier of the resource/experiment to update.
        :param row: A CSV row as a Series.
        :param known_columns: A collection of canonicalised names to skip (e.g.
          ``"title"``, ``"tags"``).
        """
        existing = self.get_existing_json(elab_id)
        if not existing:
            return
        extra_map = self.fetch_extra_fields_mapping(existing)
        if not extra_map:
            return
        for column in row.index:
            canon_col = canonicalize(column)
            if canon_col in extra_map and canon_col not in known_columns:
                value = row[column]
                if pd.isna(value):
                    val_str = ""
                else:
                    if hasattr(value, "item") and not isinstance(value,
                                                                 str):  # type: ignore[attr-defined]
                        try:
                            value = value.item()  # type: ignore[attr-defined]
                        except Exception:
                            pass
                    val_str = str(value)
                extra_map[canon_col]["value"] = val_str
        patch_data = {
            "metadata": {
                "extra_fields": list(extra_map.values())
                }
            }
        try:
            response = self.endpoint.patch(endpoint_id=elab_id,
                                           data=patch_data)
            response.raise_for_status()
        except Exception as exc:
            logger.error("Failed to patch extra fields for id %s: %s", elab_id,
                         exc)
