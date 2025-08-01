from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union, Optional, List

import pandas as pd


class BaseImporter(ABC):
    """Abstract base class for resource and experiment importers."""

    @abstractmethod
    def create_new(
        self,
        category_id: Optional[int] = None,
        csv_path: Optional[Union[Path, str]] = None,
    ) -> int:
        """Abstract method to create new resources
        or experiments(post) from a csv."""

    @abstractmethod
    def update_existing(
        self,
        csv_path: Union[Path, str],
        category_id: Optional[int],
        encoding: str = "utf-8",
        separator: str = ";",
    ) -> int:
        """Abstract method to update existing resources
        or experiments (patch) from a csv."""

    def collect_tags(self, pd: pd.DataFrame) -> List[str]:

        title = project[0].get("project_title", "")

        tags: List[str] = []
        for entry in project:
            tag_list = entry.get("tags")
            if isinstance(tag_list, np.ndarray):
                tags.extend(tag_list.tolist())
            elif isinstance(tag_list, list):
                tags.extend(tag_list)
        return tags