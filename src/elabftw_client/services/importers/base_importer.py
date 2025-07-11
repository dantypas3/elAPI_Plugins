from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union


class BaseImporter(ABC):
    """Abstract base class for resource and experiment importers."""

    @abstractmethod
    def create_new(
        self,
        csv_path: Union[Path, str],
        category_id: int,
    ) -> int:
        """Abstract method to create new resources
        or experiments(post) from a csv."""

    @abstractmethod
    def update_existing(
        self,
        csv_path: Union[Path, str],
        category_id: int,
        encoding: str = "utf-8",
        separator: str = ";",
    ) -> int:
        """Abstract method to update existing resources
        or experiments (patch) from a csv."""
