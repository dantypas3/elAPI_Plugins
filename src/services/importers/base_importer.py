"""
This module defines: class:`BaseImporter`, an abstract base class for
importing data into ElabFTW endpoints.  It provides shared helpers for
normalizing identifiers, resolving category columns, extracting titles,
parsing tag lists, and updating ``metadata.extra_fields`` on existing
resources or experiments.

Concrete importers should subclass: class:`BaseImporter` and implement
the :attr:`df`, :attr:`cols_lower` and :attr:`endpoint` properties.
"""

from __future__ import annotations

import logging
import math
import os
import mimetypes

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union

import pandas as pd
from elapi.api import FixedEndpoint
from responses import Response
from pathlib import Path

try:
    from src.utils.content_extraction import canonicalize as canonicalize_field
except ImportError:
    try:
        from utils.content_extraction import \
            canonicalize as canonicalize_field  # type: ignore
    except ImportError:
        def canonicalize_field (s: str) -> str:  # type: ignore
            """Fallback canonicalize: lower-case and strip non-alphanumerics."""
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
    extracting category ids, titles, and tags, and updating extra fields in
    metadata.  Concrete importers can build upon these to provide more
    specialised behaviour.
    """

    @staticmethod
    def _build_column_indexes (columns: pd.Index) -> Tuple[
        Dict[str, str], Dict[str, str]]:
        lower_map: Dict[str, str] = {}
        canon_map: Dict[str, str] = {}

        for original in columns:
            if not isinstance(original, str):
                continue
            lower_key = original.lower()
            canon_key = canonicalize_field(original)

            if lower_key not in lower_map:
                lower_map[lower_key] = original
            elif lower_map[lower_key] != original:
                logger.debug("Lowercase column collision: %r vs %r for key %r",
                             lower_map[lower_key], original, lower_key)

            if canon_key not in canon_map:
                canon_map[canon_key] = original
            elif canon_map[canon_key] != original:
                logger.warning(
                    "Canonical column collision: %r vs %r for key %r",
                    canon_map[canon_key], original, canon_key)

        return lower_map, canon_map

    def _find_col_like (self, target: str) -> Optional[str]:
        key = canonicalize_field(target)
        for canon_key, original in self.cols_canon.items():
            if key in canon_key:
                return original
        return None

    def _find_path_col (self) -> Optional[str]:
        aliases = {"files_path", "file_path", "attachments_path",
                   "attachments"}
        canon_aliases = {canonicalize_field(a) for a in aliases}
        for col in self.basic_df.columns:
            if isinstance(col, str) and canonicalize_field(
                    col) in canon_aliases:
                return col
        return None

    # --- Required API ---
    @property
    @abstractmethod
    def basic_df (self) -> pd.DataFrame:
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

    # ----
    def _iter_files_in_dir (self, folder: Union[str, Path]) -> List[Path]:

        path = Path(str(folder)).expanduser()

        if not path.exists() or not path.is_dir():
            logger.warning(
                "Files folder does not exist or is not a directory: %s", path)
            return []

        files = [f for f in path.rglob("*") if f.is_file()]

        if not files:
            logger.warning("No files found in folder: %s", path)

        return files

    def _resolve_folder (self, raw_value: Union[str, Path]) -> Optional[Path]:
        """
        Convert a CSV cell into a Path if it looks like a valid file/folder path.
        Returns None if the value is empty, invalid, or clearly not a path.
        """
        if raw_value is None or (
                isinstance(raw_value, float) and pd.isna(raw_value)):
            return None

        # Convert to string, normalize whitespace and non-breaking spaces
        path_str = str(raw_value).replace("\u00a0", " ").strip()
        if not path_str:
            return None

        looks_like_path = (any(
            ch in path_str for ch in (os.sep, "/", "\\")) or os.path.isabs(
            path_str) or "." in os.path.basename(
            path_str) or self.files_base_dir is not None)

        if not looks_like_path:
            logger.info(
                "Skipping files upload: value does not look like a path: %r",
                path_str)
            return None

        resolved_path = Path(path_str).expanduser()

        if not resolved_path.is_absolute() and self.files_base_dir:
            resolved_path = (self.files_base_dir / resolved_path).resolve()

        return resolved_path

    def _attach_files (self, resource_id: Union[int, str],
                       folder: Union[str, Path], recursive: bool = True,
                       chunk_size: int = 10) -> None:

        res_id = str(resource_id)
        if not res_id.isdigit():
            raise ValueError(
                f"Invalid resource ID for upload: {resource_id!r}")

        files = self._iter_files_in_dir(folder, recursive=recursive)
        if not files:
            logger.warning("No files to upload from: %s", folder)
            return

        def _mime_or_default (p: Path) -> str:
            return mimetypes.guess_type(p.name)[
                0] or "application/octet-stream"

        def _send_batch (batch: List[Path]) -> bool:
            payload = []
            handles = []
            try:
                for fp in batch:
                    fh = fp.open("rb")
                    handles.append(fh)
                    payload.append(
                        ("files[]", (fp.name, fh, _mime_or_default(fp))))
                try:
                    resp = self.endpoint.post(endpoint_id=res_id,
                                              sub_endpoint_name="uploads",
                                              files=payload)
                    resp.raise_for_status()
                    return True
                except Exception as exc:
                    logger.info("Batched upload (%d files) failed: %s",
                                len(batch), exc)
                    return False
            finally:
                for h in handles:
                    try:
                        h.close()
                    except Exception:
                        pass

        if chunk_size and chunk_size > 1:
            i = 0
            all_batches_ok = True
            while i < len(files):
                batch = files[i: i + chunk_size]
                ok = _send_batch(batch)
                if not ok:
                    all_batches_ok = False
                    break
                i += chunk_size
            if all_batches_ok:
                logger.info("Uploaded %d files in %d batch(es).", len(files),
                            (len(files) + chunk_size - 1) // chunk_size)
                return

        errors: List[str] = []
        for fp in files:
            try:
                with fp.open("rb") as fh:
                    resp = self.endpoint.post(endpoint_id=res_id,
                                              sub_endpoint_name="uploads",
                                              files=[("files[]", (fp.name, fh,
                                                                  _mime_or_default(
                                                                      fp)))])
                try:
                    resp.raise_for_status()
                    continue
                except Exception:
                    with fp.open("rb") as fh2:
                        resp2 = self.endpoint.post(endpoint_id=res_id,
                                                   sub_endpoint_name="uploads",
                                                   files={
                                                       "file": (fp.name, fh2,
                                                                _mime_or_default(
                                                                    fp))
                                                       })
                    resp2.raise_for_status()
            except Exception as exc:
                logger.error("Failed to upload file %s to resource %s: %s", fp,
                             res_id, exc)
                errors.append(f"{fp}: {exc}")

        if errors:
            raise RuntimeError(
                "One or more uploads failed:\n- " + "\n- ".join(errors))

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
        for c in self.basic_df.columns:
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
                row = pd.Series(row._asdict())
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
        string, or any scalar value.  Empty or missing tags return an empty
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
                    if hasattr(value, "item") and not isinstance(value, str):
                        try:
                            value = value.item()
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
