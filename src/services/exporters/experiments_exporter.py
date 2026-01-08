import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from werkzeug.utils import secure_filename

from src.utils.common import strip_html, paged_fetch
from src.utils.endpoints import get_fixed
from src.utils.logging_config import setup_logging
from .base_exporter import BaseExporter

logger = logging.getLogger(__name__)


class ExperimentsExporter(BaseExporter):
    def __init__ (self) -> None:
        setup_logging()
        self._endpoint = get_fixed("experiments")

    def fetch_data (self, start_offset=0, page_size=30,
                    max_retries=3) -> pd.DataFrame:
        logger.info("Fetching experiments with page_size=%d start_offset=%d", page_size, start_offset)
        def get_page (limit: int, offset: int) -> list[dict]:
            resp = self._endpoint.get(query={
                "limit": limit,
                "offset": offset
                })
            resp.raise_for_status()
            data = resp.json()
            return data["data"] if isinstance(data,
                                              dict) and "data" in data else data

        rows = list(
            paged_fetch(
                get_page,
                start_offset=start_offset,
                page_size=page_size,
                max_retries=max_retries,
                )
            )
        logger.info("Fetched %d experiments", len(rows))
        return pd.DataFrame(rows)

    def process_data (self) -> pd.DataFrame:
        df = self.fetch_data()

        if df.empty:
            logger.info("No experiments to export")
            return pd.DataFrame()

        cols_to_drop = ["userid", "created_at", "state", "content_type",
                        "access_key", "custom_id", "page", "type",
                        "status_color", "category", "category_color",
                        "has_comment", "tags_id", "events_start",
                        "events_start_itemid", "firstname", "lastname",
                        "orcid", "up_item_id", "status", "locked_at", "locked",
                        "timestamped", "team", ]

        df_clean = df.drop(columns=cols_to_drop + ["metadata"],
                           errors="ignore")

        extra = []

        for meta_str in df.get("metadata", []):
            data = json.loads(meta_str or "{}")
            fields = data.get("extra_fields", {})
            flat = {k: v.get("value") for k, v in fields.items() if
                    isinstance(v, dict)}
            extra.append(flat)

        df_extra = pd.DataFrame(extra, index=df_clean.index)
        df_final = pd.concat([df_clean, df_extra], axis=1)

        if "body" in df_final.columns:
            df_final["body"] = df_final["body"].fillna("").apply(strip_html)

        return df_final

    def xlsx_export (self, export_file: Optional[str] = None) -> Optional[
        Path]:

        export_data = self.process_data()

        if export_file:
            fn = secure_filename(export_file)
            if not fn.lower().endswith(".xlsx"):
                fn += ".xlsx"
            out_path = Path.cwd() / fn
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = Path.cwd() / f"experiments_export_{ts}.xlsx"

        out_path.parent.mkdir(exist_ok=True, parents=True)
        export_data.to_excel(out_path, index=False)
        logger.info("Exported %d experiments to %s", len(export_data), out_path)
        return out_path
