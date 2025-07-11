import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from werkzeug.utils import secure_filename

from src.elabftw_client.utils.content_extraction import strip_html
from src.elabftw_client.utils.endpoints import get_fixed

from .base_exporter import BaseExporter


class ExperimentsExporter(BaseExporter):
    def __init__(self) -> None:
        self._endpoint = get_fixed("experiments")

    def xlsx_export(self, export_file: Optional[str] = None) -> Path:
        experiments = self._endpoint.get().json()
        df = pd.json_normalize(experiments)

        cols_to_drop = [
            "userid",
            "created_at",
            "state",
            "content_type",
            "access_key",
            "custom_id",
            "page",
            "type",
            "status_color",
            "category",
            "category_color",
            "has_comment",
            "tags_id",
            "events_start",
            "events_start_itemid",
            "firstname",
            "lastname",
            "orcid",
            "up_item_id",
            "status",
            "locked_at",
            "locked",
            "timestamped",
            "team",
        ]
        df_clean = df.drop(columns=cols_to_drop + ["metadata"], errors="ignore")

        extra = []
        for meta_str in df.get("metadata", []):
            data = json.loads(meta_str or "{}")
            fields = data.get("extra_fields", {})
            flat = {k: v.get("value") for k, v in fields.items() if isinstance(v, dict)}
            extra.append(flat)
        df_extra = pd.DataFrame(extra, index=df_clean.index)
        df_final = pd.concat([df_clean, df_extra], axis=1)

        if "body" in df_final.columns:
            df_final["body"] = df_final["body"].fillna("").apply(strip_html)

        if export_file:
            fn = secure_filename(export_file)
            if not fn.lower().endswith(".xlsx"):
                fn += ".xlsx"
            out_path = Path.cwd() / fn
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = Path.cwd() / f"experiments_export_{ts}.xlsx"

        out_path.parent.mkdir(exist_ok=True, parents=True)
        df_final.to_excel(out_path, index=False)
        print(f"Exported {len(df_final)} experiments to {out_path}")
        return out_path
