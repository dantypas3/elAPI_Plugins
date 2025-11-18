from pathlib import Path
from typing import Any, Union, Dict

import pandas as pd
import json
from bs4 import BeautifulSoup


def strip_html(html_str: str) -> str:
  """
  Convert HTML into plain text:
  """
  soup = BeautifulSoup(html_str or "", "html.parser")

  paragraphs = soup.find_all("p")
  if paragraphs:
    texts = [p.get_text(separator=" ", strip=True) for p in paragraphs]
    return "\n\n".join(texts)

  return soup.get_text(separator=" ", strip=True)


def canonicalize(name: str) -> str:
  return name.lower().replace(" ", "").replace("-", "_")


def ensure_series(row: pd.Series) -> Any:
  if isinstance(row, pd.Series):
    return row
  try:
    return pd.Series(row._asdict())
  except Exception:
    return None


def load_config(config_path: Union[str, Path]) -> Dict:
  try:
    with open(config_path, "r", encoding="utf-8") as f:
      config_file: Dict = json.load(f)
      return config_file

  except FileNotFoundError:
    raise FileNotFoundError(
      f"Config file not found. Tried: {config_file}. " f"Set RES_IMPORTER_CONFIG to override, "
      f"or ensure config/res_importer_config.json exists at repo root.")

  except json.JSONDecodeError as e:
    raise ValueError(f"Error decoding JSON from {config_file}: {e}")
