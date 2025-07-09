from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

class BaseExporter(ABC):

	@abstractmethod
	def xlsx_export(self,  export_file: Optional[str] = None) -> Path:
		...