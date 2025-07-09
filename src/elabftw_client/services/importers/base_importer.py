from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Union


class BaseImporter(ABC):

	@abstractmethod
	def create_new(self, csv_path: Union[Path, str], category_id : int, encoding: str = 'utf-8',
	                     separator: str = ';') -> int:
		...

	@abstractmethod
	def update_existing(self, csv_path: Union[Path, str], category_id : int, encoding: str = 'utf-8',
	                    separator : str = ';') -> int:
		...