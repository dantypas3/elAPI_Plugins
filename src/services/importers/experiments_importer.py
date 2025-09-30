from pathlib import Path
from typing import Any, Union, Optional, Dict, List

import pandas as pd
import json

from elapi.api import FixedEndpoint

from utils.content_extraction import canonicalize
from utils.csv_tools import CsvTools
from utils.endpoints import get_fixed
from .base_importer import BaseImporter


class ExperimentsImporter(BaseImporter):

    def __init__ (self, csv_path: Union[Path, str]) -> None:
        self._endpoint = get_fixed("experiments")
        self._experiments_df: pd.DataFrame = CsvTools.csv_to_df(csv_path)

        self._experiments_counter = 0
        self._cols_lower = {col.lower(): col for col in
                            self._experiments_df.columns}
        self._cols_canon: Dict[str, Any] = {}

        for col in self._experiments_df.columns:
            key = canonicalize(col)
            self._cols_canon.setdefault(key, col)

        self._category_col: Optional[str] = next(
            (orig for key, orig in self._cols_canon.items() if
             "category_id" in key), None)

    # ---- Hooks required by BaseImporter ----

    @property
    def df (self) -> pd.DataFrame:
        return self._experiments_df

    @property
    def cols_lower (self) -> pd.DataFrame:
        return self._cols_lower

    @property
    def endpoint (self) -> FixedEndpoint:
        return self._endpoint

    # --- Helpers ---

    #    def

    # --- Experiment-specific logic ----
    def create_new (self, title: Optional[str], tags: List[str],
                    template: str = "") -> str:

        new_experiment = self.endpoint.post(data={
            "title"   : title,
            "tags"    : tags,
            "template": template
            })
        try:
            new_experiment.raise_for_status()
        except Exception as e:
            raise RuntimeError(
                f"Experiment creation failed with status {new_experiment.status_code}: "
                f"{new_experiment.text}") from e

        return str(self.get_elab_id(new_experiment)) or ""

    def patch_existing (self, experiment_id, title, category, body, tags=None):

        # TODO ask user for extra fields rename

        if tags is None:
            tags = []
        existing_json = self.get_existing_json(experiment_id)
        raw_metadata = existing_json.get("metadata") or {}

        if isinstance(raw_metadata, str):
            try:
                metadata = json.loads(raw_metadata)
            except Exception:
                metadata = {}
        else:
            metadata = raw_metadata

        # TODO upload json file with new extra fields & replace the existing one

        elab_extra_fields = metadata.setdefault("extra_fields", {})

        for k in list(elab_extra_fields.keys()):
            lk = k.lower()
            if lk != k:
                elab_extra_fields[lk] = elab_extra_fields.pop(k)

        # TODO add $delete_v & $delete_f
        for csv_idx, csv_value in self.cols_lower.items():
            if csv_idx in existing_json:
                existing_json[
                    csv_idx] = "" if csv_value == "$delete" else csv_value
            else:
                elab_extra_fields[csv_idx] = {
                    "value": csv_value
                    }

        existing_json["title"] = title
        existing_json["category"] = category
        existing_json["body"] = body

        existing_json["metadata"] = metadata

        payload = {
            "title"   : existing_json["title"],
            "tags"    : tags,
            "category": existing_json["category"],
            "body"    : existing_json["body"],
            "metadata": existing_json["metadata"],
            }
        patch = self.endpoint.patch(endpoint_id=experiment_id, data=payload)

        return patch.status_code

    def experiment_import (self) -> None:
        for _, row in self._experiments_df.iterrows():
            raw_id = row.get("id")
            title = row.get("title")
            body = row.get("body")
            tags = self.get_tags(row)
            template = str(28)

            if (not pd.notna(raw_id)) or (str(raw_id).strip() == ""):
                experiment_id = self.create_new(title, tags, template)
                self.patch_existing(experiment_id, title, "45", body, )
            else:
                try:
                    experiment_id = int(str(raw_id).strip().split(".")[0])
                except Exception:
                    raise ValueError(
                        f"Invalid experiment id in row: {raw_id!r}")
                self.patch_existing(experiment_id, title, "45", body, tags)

# TODO use category 45 for patch existing

# TODO how to recognise extra fields, how to recognise group of extra fields
#  and type of fields

# TODO cannot patch tags
