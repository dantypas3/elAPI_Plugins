import csv
from pathlib import Path
from typing import Union

import chardet


class CsvTools:

    @staticmethod
    def detect_file_encoding(path: Union[Path, str], read_bytes: int = 100_000) -> str:
        with open(path, "rb") as f:
            raw = f.read(read_bytes)
        result = chardet.detect(raw)
        return result["encoding"] or "utf-8"

    @staticmethod
    def detect_delimiter(path: Union[Path, str], encoding: str) -> str:
        with open(path, "r", encoding=encoding, errors="ignore") as f:
            sample = f.read(2048)
        sniff = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        return sniff.delimiter
