from __future__ import annotations

import json
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

import elapi.api
import pandas as pd

from src.utils.common import canonicalize as canonicalize_field
from src.utils.csv_tools import CsvTools
from src.utils.endpoints import get_fixed
from src.utils.logging_config import setup_logging
from src.utils.paths import RES_IMPORTER_CONFIG
from .base_importer import BaseImporter

logger = logging.getLogger(__name__)

try:
  with open(RES_IMPORTER_CONFIG, "r", encoding="utf-8") as config_file:
    CONFIG = json.load(config_file)
except FileNotFoundError:
  raise FileNotFoundError(
    f"Config file not found. Tried: {RES_IMPORTER_CONFIG}. "
    f"Set RES_IMPORTER_CONFIG to override, or ensure config/res_importer_config.json exists at repo root.")
except json.JSONDecodeError as e:
  raise ValueError(f"Error decoding JSON from {RES_IMPORTER_CONFIG}: {e}")


class ResourcesImporter(BaseImporter):
  """Importer for the ElabFTW ``resources`` endpoint."""

  _KNOWN_POST_FIELDS: set[str] = set(CONFIG["known_post_fields"])

  def __init__(
    self,
    csv_path: Union[Path, str],
    files_base_dir: Optional[Union[str, Path]] = None,
    template_id: Optional[Union[int, str]] = None
  ) -> None:

    setup_logging()
    self._endpoint: elapi.api.FixedEndpoint = get_fixed("resources")
    self._resources_df: pd.DataFrame = CsvTools.csv_to_df(csv_path)
    self._cols_canon: Dict[str, str] = self._canonicalize_column_indexes(self._resources_df.columns)
    self._template_id: Optional[Union[int, str]] = template_id
    self._category_col: Optional[str] = self.resolve_category_col()
    self._files_base_dir: Optional[Path] = Path(files_base_dir).expanduser() if files_base_dir else None
    self._new_resources_counter: int = 0
    self._patched_resources_counter: int = 0
    logger.info("Loaded resources CSV with %d rows", len(self._resources_df))

  # ------------------- base overrides -------------------
  @property
  def basic_df(self) -> pd.DataFrame:
    return self._resources_df

  @property
  def cols_canon(self) -> Dict[str, str]:
    return self._cols_canon

  @property
  def endpoint(self) -> elapi.api.FixedEndpoint:
    return self._endpoint

  @property
  def files_base_dir(self) -> Optional[Path]:
    return self._files_base_dir

  #
  # @property
  # def category_col(self) -> Optional[str]:
  #   return self._category_col

  # ------------------- files helpers -------------------

  def _resolve_folder(self, value: Union[str, Path]) -> Optional[Path]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
      return None
    s = str(value).replace("\u00a0", " ").strip()
    if not s:
      return None
    looks_like_path = (
      any(ch in s for ch in (os.sep, "/", "\\")) or os.path.isabs(
      s) or "." in os.path.basename(
      s) or self._files_base_dir is not None)
    if not looks_like_path:
      logger.info(
        "Skipping files upload: value does not look like a path: %r",
        s)
      return None
    p = Path(s).expanduser()
    if not p.is_absolute() and self._files_base_dir:
      p = (self._files_base_dir / p).resolve()
    return p

  def attach_single_file(
    self, resource_id: Union[int, str],
    file: Union[str, Path]
  ) -> None:
    """Upload a single file to the resource; try 'files[]' first then fallback to 'file'."""
    rid = str(resource_id)
    if not rid.isdigit():
      raise ValueError(
        f"Invalid resource ID for upload: {resource_id!r}")

    fp = Path(file)
    if not fp.exists() or not fp.is_file():
      raise FileNotFoundError(f"File not found or not a file: {fp}")

    mime = mimetypes.guess_type(fp.name)[0] or "application/octet-stream"

    try:
      logger.debug("Uploading single file %s to resource %s", fp, rid)
      with fp.open("rb") as fh:
        resp = self.endpoint.post(endpoint_id=rid,
                                  sub_endpoint_name="uploads", files=[
            ("files[]", (fp.name, fh, mime))], )
      try:
        resp.raise_for_status()
        return
      except Exception:
        with fp.open("rb") as fh2:
          resp2 = self.endpoint.post(endpoint_id=rid,
                                     sub_endpoint_name="uploads",
                                     files={
                                       "file": (fp.name, fh2, mime)
                                     }, )
        resp2.raise_for_status()
    except Exception as exc:
      logger.error("Failed to upload file %s to resource %s: %s", fp,
                   rid, exc)
      raise

  def attach_files(
    self, resource_id: Union[int, str],
    folder: Union[str, Path]
  ) -> None:
    chunk_size = CONFIG.get("upload_chunk_size", 10)
    self._attach_files(resource_id, folder, recursive=True,
                       chunk_size=chunk_size)

  # ------------------- extra fields -------------------
  def _collect_csv_extra_fields(
    self, row: pd.Series,
    known_columns: Optional[
      Iterable[str]] = None
  ) -> Dict[
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
  def _split_multi(raw: str) -> List[str]:
    raw = raw.replace("\u00a0", " ")
    parts: List[str] = []
    for chunk in raw.replace(";", ",").split(","):
      s = chunk.strip()
      if s:
        parts.append(s)
    return parts

  @staticmethod
  def _coerce_for_field(defn: dict, raw: str) -> Optional[Any]:
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

  def post_extra_fields_from_row(
    self, resource_id: Union[int, str],
    row: pd.Series, known_columns: Optional[
      Iterable[str]] = None
  ) -> None:
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
    logger.debug("Patching extra fields for resource %s: %s", rid, list(changed.keys()))

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

  def _extract_known_post_fields(
    self, row: pd.Series,
    template: Optional[Union[int, str]]
  ) -> Dict[str, Any]:
    """Build the POST payload from known columns (title, tags, category, body, template)."""

    data: Dict[str, Any] = {}

    effective_template = template if template is not None and str(
      template).strip() else self._template_id
    if effective_template is not None:
      data["template"] = effective_template

    if title := self._get_title(row):
      data["title"] = title

    if tags := self.get_tags(row):
      data["tags"] = tags

    if category_id := self.get_category_id(row):
      data["category"] = category_id

    body_col = self._find_col_like("body")

    if body_col and body_col in row:
      body_val = row[body_col]
      if not pd.isna(body_val) and str(body_val).strip():
        data["body"] = str(body_val)

    return data

  # ------------------- creation -------------------
  def create_new(self, row: pd.Series, template: Optional[Union[int, str]] = None) -> str:

    payload = self._extract_known_post_fields(row, template)
    logger.debug("Creating resource with payload fields: %s", list(payload.keys()))
    response = self.endpoint.post(data=payload)

    try:
      response.raise_for_status()
    except Exception as exc:
      title = payload.get("title", "<unknown title>")
      raise RuntimeError(
        f"Creation of {title!r} failed with status {response.status_code}: {response.text}") from exc

    resource_id = str(self.get_elab_id(response))
    logger.info("Created resource %s", resource_id)

    path_col = self._find_path_col()
    if path_col and path_col in row:
      folder_path = self._resolve_folder(row[path_col])

      if folder_path and folder_path.exists() and folder_path.is_dir():
        self.attach_files(resource_id, folder_path)
      elif folder_path and folder_path.exists() and folder_path.is_file():
        self.attach_single_file(resource_id, folder_path)
      elif folder_path:
        logger.warning("Files path does not exist: %s", folder_path)

    known = {canonicalize_field(name) for name in self._KNOWN_POST_FIELDS}
    if path_col:
      known.add(canonicalize_field(path_col))
    self.post_extra_fields_from_row(resource_id, row, known_columns=known)

    self._new_resources_counter += 1
    return resource_id

  # ------------------- patch existing -------------------
  def patch_existing(self, experiment_id: str, category: str, row: pd.Series) -> Any:

    payload: Dict[str, Any] = {"category": category}

    if tags := self.get_tags(row):
      payload["tags"] = tags

    if title := self._get_title(row):
      payload["title"] = title

    if date := self._normalize_date(row):
      payload["date"] = date

    existing_json = self.get_existing_json(experiment_id)
    raw_metadata = existing_json.get("metadata") or {}

    if isinstance(raw_metadata, str):
      try:
        metadata = json.loads(raw_metadata)
      except Exception:
        metadata = {}
    else:
      metadata = raw_metadata

    extra_fields = metadata.setdefault("extra_fields", {})
    metadata["extra_fields"] = {k.lower(): v for k, v in extra_fields.items()}

    metadata_str = json.dumps(metadata, ensure_ascii=False,
                              separators=(",", ":"))

    payload["metadata"] = metadata_str

    response = self.endpoint.patch(endpoint_id=experiment_id, data=payload)
    response.raise_for_status()

    logger.info("Patched resource %s", experiment_id)
    return response.status_code

  # ------------------- bulk -------------------
  def create_all_from_csv(
    self,
    template: Optional[Union[int, str]] = None
  ) -> \
    List[str]:
    """Create every resource from the CSV, optionally overriding template per call."""
    ids: List[str] = []
    for _, row in self.basic_df.iterrows():
      ids.append(self.create_new(row=row, template=template))
    return ids
