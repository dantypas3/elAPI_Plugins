import csv
import pandas as pd

from io import StringIO
from pathlib import Path
from typing import Union

import chardet


class CsvTools:
    @staticmethod
    def detect_file_encoding (path: Union[Path, str],
                              read_bytes: int = 100_000) -> str:
        with open(path, "rb") as f:
            raw = f.read(read_bytes)
        result = chardet.detect(raw)
        return result.get("encoding") or "utf-8"

    @staticmethod
    def _normalize_text (text: str) -> str:
        # Normalize pesky characters/newlines that often confuse csv.Sniffer/pandas
        return (text.replace("\ufeff", "")  # BOM
        .replace("\u00a0", " ")  # NBSP -> space
        .replace("\r\n", "\n").replace("\r", "\n"))

    @staticmethod
    def detect_delimiter (path: Union[Path, str], encoding: str) -> str:
        with open(path, "r", encoding=encoding, errors="ignore") as f:
            sample = f.read(8192)  # larger sample helps sniffing
        sample = CsvTools._normalize_text(sample)

        try:
            sniff = csv.Sniffer().sniff(sample,
                                        delimiters=[",", ";", "\t", "|"])
            return sniff.delimiter
        except csv.Error:
            # Heuristic fallback: inspect the first non-empty line (likely the header)
            header = next((ln for ln in sample.splitlines() if ln.strip()), "")
            candidates = [";", "\t", "|", ","]
            counts = {d: header.count(d) for d in candidates}
            best = max(counts, key=counts.get)
            # Require at least two occurrences; otherwise default to semicolon
            return best if counts[best] >= 2 else ";"

    @staticmethod
    def csv_to_df (csv_path: Union[Path, str]) -> pd.DataFrame:
        enc = CsvTools.detect_file_encoding(path=csv_path)
        delimiter = CsvTools.detect_delimiter(path=csv_path, encoding=enc)

        with open(csv_path, "r", encoding=enc, errors="ignore") as f:
            raw = f.read()
        raw = CsvTools._normalize_text(raw)

        # Use engine="python" for slightly more forgiving parsing on oddities.
        # If your data may contain delimiter characters inside quoted fields,
        # pandas will handle them by default with quotechar='"'.
        df = pd.read_csv(StringIO(raw), sep=delimiter, engine="python", )
        return df
