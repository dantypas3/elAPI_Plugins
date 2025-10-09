"""
Resource importer implementation leveraging :class:`BaseImporter`.

This module defines :class:`ResourcesImporter`, a concrete subclass of
:class:`base_importer.BaseImporter`. It reads resources from a CSV file into
a :class:`pandas.DataFrame`, constructs robust lookup dictionaries for
column resolution and handles creation of resources via the ElabFTW API. All
columns except ``title``, ``tags``, ``category``, ``template`` and ``body``
are interpreted as extra fields and their values are patched into the
resource's metadata if matching extra field definitions exist.

In addition, the importer supports attaching files from a directory specified
in a ``files_path`` column (or aliases), with support for a base directory
to resolve relative paths.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union

import pandas as pd  # type: ignore

# Import the base importer from the current package or module
try:
    from base_importer import BaseImporter, canonicalize  # type: ignore
except Exception:
    # Fallback relative import if used as a package
    from .base_importer import BaseImporter, canonicalize  # type: ignore

try:
    from src.utils.content_extraction import \
        canonicalize as canonicalize_field  # type: ignore
except Exception:
    try:
        from utils.content_extraction import \
            canonicalize as canonicalize_field  # type: ignore
    except Exception:
        canonicalize_field = canonicalize  # type: ignore

logger = logging.getLogger(__name__)

# Late imports for third-party modules to avoid import cycles
try:
    from utils.csv_tools import CsvTools  # type: ignore
    from utils.endpoints import get_fixed  # type: ignore
except Exception:
    CsvTools = None  # type: ignore
    get_fixed = None  # type: ignore


class ResourcesImporter(BaseImporter):
    """Importer for the ElabFTW ``resources`` endpoint."""

    _KNOWN_POST_FIELDS: Iterable[str] = {"title", "tags", "category",
                                         "template", "body"}

    def __init__ (self, csv_path: Union[Path, str],
                  files_base_dir: Optional[Union[str, Path]] = None,
                  template: Union[int, str] = None) -> None:
        if get_fixed is None or CsvTools is None:
            raise RuntimeError(
                "Required modules 'utils.endpoints' and 'utils.csv_tools' are not available")
        self._endpoint = get_fixed("resources")
        self._resources_df: pd.DataFrame = CsvTools.csv_to_df(csv_path)
        self._cols_lower, self._cols_canon = self._build_column_indexes(
            self._resources_df.columns)

        self._template = template

        self._category_col: Optional[str] = self._find_col_like("category_id")
        self._files_base_dir: Optional[Path] = Path(
            files_base_dir).expanduser() if files_base_dir else None
        self._new_resources_counter: int = 0
        self._patched_resources_counter: int = 0

    # ------------------- column helpers -------------------
    @classmethod
    def _build_column_indexes (cls, columns: pd.Index) -> Tuple[
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
        for canon_key, original in self._cols_canon.items():
            if key in canon_key:
                return original
        return None

    # ------------------- base overrides -------------------
    @property
    def df (self) -> pd.DataFrame:
        return self._resources_df

    @property
    def cols_lower (self) -> Mapping[str, str]:
        return self._cols_lower

    @property
    def endpoint (self):
        return self._endpoint

    @property
    def category_col (self) -> Optional[str]:
        return self._category_col

    # ------------------- files helpers -------------------
    def _iter_files_in_dir (self, folder: Union[str, Path]) -> List[Path]:
        path = Path(str(folder)).expanduser()

        if not path.exists() or not path.is_dir():
            logger.warning(
                "Files folder does not exist or is not a directory: %s", path)
            return []

        files = list(path.rglob("*"))
        files = [f for f in files if f.is_file()]

        if not files:
            logger.warning("No files found in folder: %s",
                           path)

        return files

    def _find_path_col (self) -> Optional[str]:
        aliases = {"files_path", "file_path", "attachments_path",
                   "attachments", "Folder with map and sequencing results",
                   "Folder with attachments", }
        canon_aliases = {canonicalize_field(a) for a in aliases}
        for col in self._resources_df.columns:
            if isinstance(col, str) and canonicalize_field(
                    col) in canon_aliases:
                return col
        return None

    def _resolve_folder (self, value: Union[str, Path]) -> Optional[Path]:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        s = str(value).replace("\u00a0", " ").strip()
        if not s:
            return None
        looks_like_path = any(
            ch in s for ch in (os.sep, "/", "\\")) or os.path.isabs(
            s) or "." in os.path.basename(
            s) or self._files_base_dir is not None
        if not looks_like_path:
            logger.info(
                "Skipping files upload: value does not look like a path: %r",
                s)
            return None
        p = Path(s).expanduser()
        if not p.is_absolute() and self._files_base_dir:
            p = (self._files_base_dir / p).resolve()
        return p

    def attach_files (self, resource_id: Union[int, str],
                      folder: Union[str, Path],
                      chunk_size: int = 10) -> None:
        rid = str(resource_id)
        if not rid.isdigit():
            raise ValueError(
                f"Invalid resource ID for upload: {resource_id!r}")

        files = self._iter_files_in_dir(folder)
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
                    resp = self.endpoint.post(endpoint_id=rid,
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
                    resp = self.endpoint.post(endpoint_id=rid,
                                              sub_endpoint_name="uploads",
                                              files=[("files[]", (fp.name, fh,
                                                                  _mime_or_default(
                                                                      fp)))])
                try:
                    resp.raise_for_status()
                    continue
                except Exception:
                    with fp.open("rb") as fh2:
                        resp2 = self.endpoint.post(endpoint_id=rid,
                                                   sub_endpoint_name="uploads",
                                                   files={
                                                       "file": (fp.name, fh2,
                                                                _mime_or_default(
                                                                    fp))
                                                       })
                    resp2.raise_for_status()
            except Exception as exc:
                logger.error("Failed to upload file %s to resource %s: %s", fp,
                             rid, exc)
                errors.append(f"{fp}: {exc}")

        if errors:
            raise RuntimeError(
                "One or more uploads failed:\n- " + "\n- ".join(errors))

    # ------------------- extra fields -------------------
    def _collect_csv_extra_fields (self, row: pd.Series,
                                   known_columns: Optional[
                                       Iterable[str]] = None) -> Dict[
        str, Any]:
        known_canon = {canonicalize_field(x) for x in self._KNOWN_POST_FIELDS}
        if known_columns:
            known_canon |= {canonicalize_field(x) for x in known_columns}
        extras: Dict[str, Any] = {}
        for col, val in row.items():
            if not isinstance(col, str):
                continue
            ckey = canonicalize_field(col)
            if ckey in known_canon:
                continue
            if val is None or (isinstance(val, float) and pd.isna(val)):
                continue
            sval = str(val).replace("\u00a0", " ").strip()
            if not sval:
                continue
            extras[ckey] = sval
        return extras

    @staticmethod
    def _split_multi (raw: str) -> List[str]:
        raw = raw.replace("\u00a0", " ")
        parts: List[str] = []
        for chunk in raw.replace(";", ",").split(","):
            s = chunk.strip()
            if s:
                parts.append(s)
        return parts

    @staticmethod
    def _coerce_for_field (defn: dict, raw: str) -> Optional[Any]:
        ftype = (defn or {}).get("type")
        allow_multi = bool((defn or {}).get("allow_multi_values"))
        options = (defn or {}).get("options") or []
        options_set = {str(o).strip() for o in options}

        if ftype == "select":
            vals = ResourcesImporter._split_multi(raw)
            if allow_multi:
                picked = [v for v in vals if v in options_set]
                if not picked and vals:
                    lower_map = {o.lower(): o for o in options_set}
                    for v in vals:
                        m = lower_map.get(v.lower())
                        if m and m not in picked:
                            picked.append(m)
                return picked
            else:
                for v in vals:
                    if v in options_set:
                        return v
                lower_map = {o.lower(): o for o in options_set}
                for v in vals:
                    m = lower_map.get(v.lower())
                    if m:
                        return m
                return None
        else:
            return raw

    def post_extra_fields_from_row (self, resource_id: Union[int, str],
                                    row: pd.Series, known_columns: Optional[
                Iterable[str]] = None) -> None:
        """Intersect CSV extras with template fields, coerce types, and PATCH metadata (as JSON string)."""
        rid = str(resource_id)
        existing_json = self.get_existing_json(rid)

        raw_metadata = existing_json.get("metadata") or {}
        if isinstance(raw_metadata, str):
            try:
                metadata = json.loads(raw_metadata)
            except Exception:
                metadata = {}
        else:
            metadata = raw_metadata

        elab_extra_fields: Dict[str, dict] = metadata.setdefault(
            "extra_fields", {})

        defs_by_canon: Dict[str, str] = {}
        for orig_key in list(elab_extra_fields.keys()):
            c = canonicalize_field(orig_key)
            if c not in defs_by_canon:
                defs_by_canon[c] = orig_key

        csv_extras = self._collect_csv_extra_fields(row,
                                                    known_columns=known_columns)

        changed: Dict[str, Any] = {}
        for ckey, raw_val in csv_extras.items():
            if ckey not in defs_by_canon:
                continue
            real_key = defs_by_canon[ckey]
            defn = elab_extra_fields.get(real_key) or {}
            coerced = self._coerce_for_field(defn, raw_val)
            if coerced is None:
                logger.info(
                    "Skipping field %r: value %r not valid for options.",
                    real_key, raw_val)
                continue
            slot = elab_extra_fields.get(real_key)
            if not isinstance(slot, dict):
                elab_extra_fields[real_key] = {
                    "value": coerced
                    }
            else:
                slot["value"] = coerced
            changed[real_key] = coerced

        if not changed:
            logger.info("No matching extra fields to upload for resource %s.",
                        rid)
            return

        # IMPORTANT: send metadata as a JSON STRING (not an object)
        metadata_str = json.dumps(metadata, ensure_ascii=False,
                                  separators=(",", ":"))
        payload = {
            "metadata": metadata_str
            }
        resp = self.endpoint.patch(endpoint_id=rid, data=payload)
        try:
            resp.raise_for_status()
        except Exception as exc:
            raise RuntimeError(
                f"Failed to patch extra fields for resource {rid}: "
                f"{getattr(resp, 'status_code', '?')} {getattr(resp, 'text', '')}") from exc

    # ------------------- payload construction -------------------
    def _extract_known_post_fields (self, row: pd.Series, template: str) -> \
            Dict[str, Any]:
        data: Dict[str, Any] = {}
        title = self.get_title(row)
        if title:
            data["title"] = title
        tags = self.get_tags(row)
        if tags:
            data["tags"] = tags

        data["template"] = self._template

        body_col = self._find_col_like("body")
        if body_col and body_col in row:
            body_val = row[body_col]
            if not pd.isna(body_val) and str(body_val).strip():
                data["body"] = str(body_val)
        return data

    # ------------------- creation -------------------
    def create_new (self, row: pd.Series, template: str = "") -> str:
        payload = self._extract_known_post_fields(row, template)
        response = self.endpoint.post(data=payload)
        try:
            response.raise_for_status()
        except Exception as exc:
            title = payload.get("title", "<unknown title>")
            raise RuntimeError(
                f"Creation of {title!r} failed with status {response.status_code}: {response.text}") from exc

        resource_id = str(self.get_elab_id(response))

        path_col = self._find_path_col()
        if path_col and path_col in row:
            folder_path = self._resolve_folder(row[path_col])
            if folder_path and folder_path.exists() and folder_path.is_dir():
                self.attach_files(resource_id, folder_path,
                                  chunk_size=10)
            elif folder_path:
                logger.warning(
                    "Files folder does not exist or is not a directory: %s",
                    folder_path)

        known = {canonicalize_field(name) for name in self._KNOWN_POST_FIELDS}
        if path_col:
            known.add(canonicalize_field(path_col))
        self.post_extra_fields_from_row(resource_id, row, known_columns=known)

        self._new_resources_counter += 1
        return resource_id

    # ------------------- patch existing -------------------
    def patch_existing (self, experiment_id: Union[int, str], title: str,
                        category: str, body: str,
                        tags: Optional[List[str]] = None) -> int:
        if tags is None:
            tags = []

        rid = str(experiment_id)
        existing_json = self.get_existing_json(rid)
        raw_metadata = existing_json.get("metadata") or {}
        if isinstance(raw_metadata, str):
            try:
                metadata = json.loads(raw_metadata)
            except Exception:
                metadata = {}
        else:
            metadata = raw_metadata

        elab_extra_fields = metadata.setdefault("extra_fields", {})
        for k in list(elab_extra_fields.keys()):
            lk = k.lower()
            if lk != k:
                elab_extra_fields[lk] = elab_extra_fields.pop(k)

        # IMPORTANT: send metadata as JSON STRING
        metadata_str = json.dumps(metadata, ensure_ascii=False,
                                  separators=(",", ":"))
        payload = {
            "title"   : title,
            "tags"    : tags,
            "category": category,
            "body"    : body,
            "metadata": metadata_str
            }
        patch = self.endpoint.patch(endpoint_id=rid, data=payload)
        patch.raise_for_status()
        return patch.status_code

    # ------------------- bulk -------------------
    def create_all_from_csv (self, template: str = "") -> List[str]:
        ids: List[str] = []
        for _, row in self.df.iterrows():
            ids.append(self.create_new(row=row, template=template))
        return ids
