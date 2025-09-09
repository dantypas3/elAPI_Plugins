from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import pandas as pd


class BaseExporter(ABC):

    @abstractmethod
    def xlsx_export (self, export_file: Optional[str] = None) -> Optional[
        Path]: ...

    def fetch_data (self, start_offset: int = 0, page_size: int = 30,
                    max_retries: int = 3) -> pd.DataFrame: ...
