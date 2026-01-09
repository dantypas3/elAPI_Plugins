import logging
from pathlib import Path
from typing import Any, Union, Optional, Dict, List

import pandas as pd

from elapi.api import FixedEndpoint

from src.utils.common import canonicalize
from src.utils.logging_config import setup_logging
from src.utils.csv_tools import CsvTools
from src.utils.endpoints import get_fixed
from .base_importer import BaseImporter

logger = logging.getLogger(__name__)


class ExperimentsImporter(BaseImporter):

  def __init__(self, csv_path: Union[Path, str]) -> None:
    setup_logging()
    self._endpoint = get_fixed("experiments")
    self._experiments_df: pd.DataFrame = CsvTools.csv_to_df(csv_path)

    self._experiments_counter = 0
    self._cols_canon: Dict[str, str] = {}
    for col in self._experiments_df.columns:
      self._cols_canon.setdefault(canonicalize(col), col)

    self._category_col: Optional[str] = self.resolve_category_col()
    logger.info("Loaded experiments CSV with %d rows", len(self._experiments_df))

  @property
  def basic_df(self) -> pd.DataFrame:
    return self._experiments_df

  @property
  def cols_canon(self) -> Dict[str, str]:
    return self._cols_canon

  @property
  def endpoint(self) -> FixedEndpoint:
    return self._endpoint

  def _get_body(self, row: pd.Series) -> Optional[str]:
    body_col = self._find_col_like("body")
    if not body_col or body_col not in row:
      return None
    body_val = row[body_col]
    if pd.isna(body_val):
      return None
    body_str = str(body_val).strip()
    return body_str if body_str else None

  def create_new(
    self, title: Optional[str], tags: List[str],
    template: str = ""
  ) -> str:

    new_experiment = self.endpoint.post(data={
      "title": title,
      "tags": tags,
      "template": template
    })
    try:
      new_experiment.raise_for_status()
    except Exception as e:
      raise RuntimeError(
        f"Experiment creation failed with status {new_experiment.status_code}: "
        f"{new_experiment.text}") from e

    experiment_id = str(self.get_elab_id(new_experiment)) or ""
    logger.info("Created new experiment %s", experiment_id)
    return experiment_id

  def patch_existing(
    self, experiment_id: Union[int, str],
    row: pd.Series,
    category: Optional[str] = None
  ) -> int:

    payload: Dict[str, Any] = {}

    if title := self._get_title(row):
      payload["title"] = title
    if tags := self.get_tags(row):
      payload["tags"] = tags
    if body := self._get_body(row):
      payload["body"] = body
    if category:
      payload["category"] = category

    if payload:
      logger.debug("Patching experiment %s with %s", experiment_id, list(payload.keys()))
      patch = self.endpoint.patch(endpoint_id=experiment_id, data=payload)
      patch.raise_for_status()

    known_columns = {"id", "title", "tags", "category", "body", "date", "template"}
    self.update_extra_fields_from_row(str(experiment_id), row,
                                      known_columns=known_columns)

    logger.info("Patched experiment %s", experiment_id)
    return 200

  def experiment_import(self) -> None:
    id_col = self._find_col_like("id") or "id"
    logger.info("Starting experiments import with id column %r", id_col)
    for _, row in self.basic_df.iterrows():
      raw_id = row.get(id_col)
      title = self._get_title(row)
      tags = self.get_tags(row)
      template = str(28)

      if (not pd.notna(raw_id)) or (str(raw_id).strip() == ""):
        experiment_id = self.create_new(title, tags, template)
        self.patch_existing(experiment_id, row, category="45")
      else:
        try:
          experiment_id = int(str(raw_id).strip().split(".")[0])
        except Exception:
          raise ValueError(
            f"Invalid experiment id in row: {raw_id!r}")
        self.patch_existing(experiment_id, row, category="45")
    logger.info("Finished experiments import")

# TODO use category 45 for patch existing

# TODO how to recognise extra fields, how to recognise group of extra fields
#  and type of fields

# TODO cannot patch tags
