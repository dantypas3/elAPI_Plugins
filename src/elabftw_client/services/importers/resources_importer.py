import pandas as pd
from typing import Union
from pathlib import Path

from src.elabftw_client.utils.endpoints import get_fixed
from src.elabftw_client.utils.validators import IDValidator
from .base_importer import BaseImporter


class ResourcesImporter(BaseImporter):

	def __init__(self) -> None:
		self._res_endpoint = get_fixed("resources")
		self._cat_endpoint = get_fixed("category")

	def create_new(self, csv_path: Union[Path, str], category_id : int, encoding: str = 'utf-8',
	                     separator: str = ';') -> int:

		new_resources = 0
		IDValidator("category", category_id).validate()


		df = pd.read_csv(csv_path, encoding=encoding, sep=separator)

		for index, row in df.iterrows():
			new_resource = self._res_endpoint

			data = {
				"title": row["title"],
				"template": category_id
			}

			post = new_resource.post(data=data)

			if post.status_code == 201:
				new_resources += 1

			id = post.headers.get("location").split("/")[-1]

		return new_resources

	def update_existing(self, csv_path: Union[Path, str], category_id : int, encoding: str = 'utf-8',
	                    separator : str = ';') -> int:
		pass

