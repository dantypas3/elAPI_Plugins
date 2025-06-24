from typing import Union
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename
from bs4 import BeautifulSoup

import json
import os
import logging
import pandas as pd
import openpyxl

import utils.resource_utils as resource_utils
from utils import paths

"""
Created for: Universität Heidelberg – BZH - SFB 1638
Author:    Dionysios Antypas (dionysios.antypas@bzh.uni-heidelberg.de)
Status:    Work in progress
"""


def strip_html(html_str: str) -> str:
    """
    Convert HTML into plain text:
     - each <p>…</p> becomes one paragraph (joined with double newlines)
     - inside a paragraph, tags are replaced by single spaces
    """
    soup = BeautifulSoup(html_str or "", "html.parser")

    paragraphs = soup.find_all("p")
    if paragraphs:
        texts = [
            p.get_text(separator=" ", strip=True)
            for p in paragraphs
        ]
        return "\n\n".join(texts)

    return soup.get_text(separator=" ", strip=True)



def json_export_resource(resource_id: Union[str, int], export_file: str = "") -> str:
    print(f"Validating resource ID: {resource_id}")
    resource_utils.ResourceIDValidator(resource_id).validate()

    print(f"Fetching resource {resource_id} from API...")
    session = resource_utils.FixedResourceEndpoint()
    resource = session.get(endpoint_id=resource_id).json()
    resource_json = json.dumps(resource, indent=4)

    if not export_file:
        export_file = paths.export_json(f"resource_{resource_id}.json")
    else:
        safe_name = secure_filename(export_file)
        export_file = paths.export_json(f"{safe_name}.json")

    export_dir = os.path.dirname(export_file)
    os.makedirs(export_dir, exist_ok=True)

    with open(export_file, "w") as f:
        f.write(resource_json)

    if not resource_utils.is_file_created_and_not_empty(export_file):
        raise IOError("The output JSON file is empty or could not be written correctly.")

    print(f"Exported to: {export_file}")
    return resource_json


def export_category_to_xlsx(
    category_id: int,
    export_file: Union[str, None] = None
) -> Path:
    """
    Export all resources of a category to an XLSX file.
    Returns the absolute Path to the created file.
    """
    resources = resource_utils.FixedResourceEndpoint()\
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

def export_xlsx(export_file: Union[str, None] = None) -> Path:
    """CLI helper: let the user pick a category and then call export_category_to_xlsx."""
    categories = resource_utils.FixedResourceEndpoint().get().json()
    df_categories = pd.json_normalize(categories)

    print("ID  Title")
    for cat_id, title in zip(df_categories['id'], df_categories['title']):
        print(f"{cat_id:<4} {title}")

    valid_ids = set(df_categories['id'])
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            choice = int(input("\nSelect a category id: ").strip())
            if choice in valid_ids:
                break
            logging.warning("Invalid category id: %s", choice)
        except ValueError:
            logging.warning("Non-integer input received.")
        if attempt == max_attempts:
            raise SystemExit("Too many invalid attempts. Exiting.")

    return export_category_to_xlsx(choice, export_file)
