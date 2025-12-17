import json
import math
import time
from pathlib import Path
from typing import Any, Union, Dict, Callable, Sequence, Iterator, TypeVar

import pandas as pd
from bs4 import BeautifulSoup
from requests.exceptions import ReadTimeout, ConnectTimeout


def strip_html (html_str: str) -> str:
    """
    Convert HTML into plain text:
    """
    soup = BeautifulSoup(html_str or "", "html.parser")

    paragraphs = soup.find_all("p")
    if paragraphs:
        texts = [p.get_text(separator=" ", strip=True) for p in paragraphs]
        return "\n\n".join(texts)

    return soup.get_text(separator=" ", strip=True)


def canonicalize (name: str) -> str:
    return name.lower().replace(" ", "").replace("-", "_")


def ensure_series (row: pd.Series) -> Any:
    if isinstance(row, pd.Series):
        return row
    try:
        return pd.Series(row._asdict())
    except Exception:
        return None


def load_config (config_path: Union[str, Path]) -> Dict:
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_file: Dict = json.load(f)
            return config_file

    except FileNotFoundError:
        raise FileNotFoundError(
            f"Config file not found. Tried: {config_file}. " f"Set "
            f"RES_IMPORTER_CONFIG to override, "
            f"or ensure config/res_importer_config.json exists at repo root.")

    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding JSON from {config_file}: {e}")


T = TypeVar("T")
Timeouts = (ReadTimeout, ConnectTimeout)

def paged_fetch(
    get_page: Callable[[int, int], Sequence[T]],
    *,
    start_offset: int = 0,
    page_size: int = 30,
    max_retries: int = 3,
    min_limit: int = 5,
    backoff_s: Callable[[int], float] = lambda attempt: 1.5 * attempt,
    on_progress: Callable[[int, int, int], None] | None = None,
) -> Iterator[T]:
    """
    Generic paging loop with retry logic + adaptive limit + skip-on-timeout.
    get_page(limit, offset) -> sequence of items
    """
    offset = start_offset

    while True:
        attempt = 0
        current_limit = page_size

        while True:
            try:
                page = list(get_page(current_limit, offset))
                break
            except Timeouts:
                if attempt >= max_retries:
                    page = []
                    break
                attempt += 1
                time.sleep(backoff_s(attempt))
                current_limit = max(min_limit, math.ceil(current_limit / 2))

        if not page:
            # too many retries -> skip this window and continue; otherwise stop
            if attempt >= max_retries:
                if on_progress:
                    on_progress(0, offset, current_limit)
                offset += current_limit
                continue
            break

        if on_progress:
            on_progress(len(page), offset, current_limit)

        yield from page

        if len(page) < current_limit:
            break

        offset += current_limit