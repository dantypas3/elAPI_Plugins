from typing import Any

import pandas as pd
from bs4 import BeautifulSoup


def strip_html (html_str: str) -> str:
    """
    Convert HTML into plain text:
     - each <p>…</p> becomes one paragraph (joined with double newlines)
     - inside a paragraph, tags are replaced by single spaces
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
