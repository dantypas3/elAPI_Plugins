import pandas as pd
import json
from typing import Union
from pathlib import Path
from datetime import datetime


from werkzeug.utils import secure_filename

from utils.content_extraction import strip_html
import utils.endpoints as endpoints


def export_resources_to_xlsx(category_id: int, export_file: Union[str, None] = None) -> Path:
    """
    Export all resources of a category to an XLSX file.
    Returns the absolute Path to the created file.
    """
    endpoints.CategoryIDValidator(category_id).validate()
    resources = endpoints.FixedResourceEndpoint()\
                              .get(query={"cat": category_id})\
                              .json()
    df = pd.json_normalize(resources)

    cols_to_drop = [
        "team", "elabid", "category", "locked", "lockedby", "locked_at",
        "userid", "canread", "canwrite", "available", "lastchangeby", "state",
        "events_start", "content_type", "created_at", "access_key",
        "is_bookable", "canbook", "book_max_minutes", "book_max_slots",
        "book_can_overlap", "book_is_cancellable", "book_cancel_minutes",
        "status", "custom_id", "timestamped", "timestampedby", "timestamped_at",
        "book_users_can_in_past", "is_procurable", "proc_pack_qty",
        "proc_price_notax", "proc_price_tax", "proc_currency", "page", "type",
        "status_color", "category_color", "recent_comment", "has_comment",
        "tags_id", "events_start_itemid", "next_step", "firstname", "lastname",
        "orcid", "up_item_id"
    ]
    df_clean = df.drop(columns=cols_to_drop + ["metadata"], errors='ignore')

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
        out_path = Path.cwd() / f"category_{category_id}_{ts}.xlsx"

    out_path.parent.mkdir(exist_ok=True, parents=True)
    df_final.to_excel(out_path, index=False)
    print(f"Exported {len(df_final)} rows to {out_path}")
    return out_path