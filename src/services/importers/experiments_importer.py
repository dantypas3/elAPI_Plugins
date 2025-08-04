from pathlib import Path
from typing import Union, Optional

from utils.csv_tools import CsvTools
from utils.endpoints import get_fixed
from utils.validators import IDValidator
from .base_importer import BaseImporter


class ExperimentsImporter(BaseImporter):

    def __init__ (self) -> None:
        self._endpoint = get_fixed("experiments")

    def create_new (self, category_id: int = None,
                    csv_path: Optional[Union[Path, str]] = None) -> int:

        new_experiments = 0

        if category_id:
            IDValidator("categories", category_id).validate()
        if csv_path:
            categories_df = CsvTools.csv_to_df(csv_path)

        for index, row in categories_df.iterrows():
            new_experiment = self._endpoint

            data = {
                "title": row["title"]
                }
            post = new_experiment.post(data=data)

            if post.status_code == 201:
                id = post.headers.get("location").split("/")[-1]
                new_experiments += 1
            else:
                id = None

        return new_experiment
