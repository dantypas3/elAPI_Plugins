from pathlib import Path
from typing import Union, Optional

import pandas as pd

from src.elabftw_client.utils.csv_tools import CsvTools
from src.elabftw_client.utils.endpoints import get_fixed
from src.elabftw_client.utils.validators import IDValidator

from .base_importer import BaseImporter


class ResourcesImporter(BaseImporter):

    def __init__(self) -> None:
        self._res_endpoint = get_fixed("resources")
        self._cat_endpoint = get_fixed("categories")

    def create_new(self, category_id : int = None, csv_path: Optional[Union[Path, str]] = None) -> int:

        new_resources = 0
        IDValidator("categories", category_id).validate()

        resources_df = CsvTools.csv_to_df(csv_path)

        for index, row in resources_df.iterrows():
            new_resource = self._res_endpoint

            data = {"title": row["title"], "template": category_id}

            post = new_resource.post(data=data)

            if post.status_code == 201:
                new_resources += 1
                id = post.headers.get("location").split("/")[-1]
            else:
                id = None


        return new_resources

    def update_existing(
        self,
        csv_path: Union[Path, str],
        category_id: int,
        encoding: str = "utf-8",
        separator: str = ";",
    ) -> int:
        pass
