import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from werkzeug.utils import secure_filename

from elabftw_client.utils.content_extraction import strip_html
from elabftw_client.utils.endpoints import get_fixed
from elabftw_client.utils.validators import IDValidator

from .base_exporter import BaseExporter


class ResourceExporter(BaseExporter):
    def __init__(self, category_id: int) -> None:
        self._category_id = category_id
        self._endpoint = get_fixed("resources")

    def xlsx_export(self, export_file: Optional[str] = None) -> Path:
        IDValidator("categories", self._category_id).validate()

        resources = self._endpoint.get(query={"cat": self._category_id,
                                            "limit": 1000},
                                       ).json()
        df = pd.json_normalize(resources)

        cols_to_drop = [
            "team",
            "elabid",
            "category",
            "locked",
            "lockedby",
            "locked_at",
            "userid",
            "canread",
            "canwrite",
            "available",
            "lastchangeby",
            "state",
            "events_start",
            "content_type",
            "created_at",
            "access_key",
            "is_bookable",
            "canbook",
            "book_max_minutes",
            "book_max_slots",
            "book_can_overlap",
            "book_is_cancellable",
            "book_cancel_minutes",
            "status",
            "custom_id",
            "timestamped",
            "timestampedby",
            "timestamped_at",
            "book_users_can_in_past",
            "is_procurable",
            "proc_pack_qty",
            "proc_price_notax",
            "proc_price_tax",
            "proc_currency",
            "page",
            "type",
            "status_color",
            "category_color",
            "recent_comment",
            "has_comment",
            "tags_id",
            "events_start_itemid",
            "next_step",
            "firstname",
            "lastname",
            "orcid",
            "up_item_id",
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
            out_path = Path.cwd() / f"category_{self._category_id}_{ts}.xlsx"

        out_path.parent.mkdir(exist_ok=True, parents=True)
        df_final.to_excel(out_path, index=False)
        print(f"Exported {len(df_final)} resources to {out_path}")
        return out_path
