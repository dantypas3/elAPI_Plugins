import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from httpx import ReadTimeout, ConnectTimeout
from requests import ReadTimeout, ConnectTimeout
from werkzeug.utils import secure_filename

from src.utils.content_extraction import strip_html
from src.utils.endpoints import get_fixed
from .base_exporter import BaseExporter


class ExperimentsExporter(BaseExporter):
    def __init__ (self) -> None:
        self._endpoint = get_fixed("experiments")

    def fetch_data (self, start_offset: int = 0, page_size: int = 30,
                    max_retries: int = 3) -> pd.DataFrame:
        offset = start_offset
        rows = []

        while True:
            attempt = 0
            current_limit = page_size

            while True:
                try:
                    response = self._endpoint.get(query={
                        "limit" : current_limit,
                        "offset": offset
                        })

                    response.raise_for_status()
                    data = response.json()
                    page = data["data"] if (isinstance(data,
                                                       dict) and "data" in data) else data
                    break
                except(ReadTimeout, ConnectTimeout):
                    if attempt >= max_retries:
                        print(
                            f"Timeout on offset {offset}. Skipping after {max_retries} retries.")
                        page = []
                        break
                    attempt += 1
                    sleep_s = 1.5 * attempt
                    current_limit = max(5, math.ceil(current_limit / 2))
                    print(f"Timeout on offset {offset}. Retry"
                          f" {attempt}/{max_retries} after {sleep_s:.1f}s"
                          f" with limit={current_limit}…")
                    time.sleep(sleep_s)

            if not page:
                if attempt >= max_retries:
                    offset += current_limit
                    continue
                break

            rows.extend(page)
            print(f"Fetched total{len(page)} rows")

            if len(page) < current_limit:
                break

            offset += current_limit

        return pd.DataFrame(rows)

    def process_data (self) -> pd.DataFrame:
        df = self.fetch_data()

        if df.empty:
            print("No experiments to export")
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
        print(f"Exported {len(export_data)} experiments to {out_path}")
        return out_path
