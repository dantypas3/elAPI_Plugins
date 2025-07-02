from pathlib import Path
from typing import Union, IO
import pandas as pd
from utils import endpoints

def create_resources(csv_path: Union[Path, str], category_id : int, encoding: str = 'utf-8',
                     separator: str = ';'):
    """
    Create and patch one resource per row in the CSV file.
    If a row already has a 'resource_id', it will be skipped.
    The user selects the category once and it's applied to all new resources.
    """

    new_resources = 0

    endpoints.CategoryIDValidator(category_id).validate()

    df = pd.read_csv(csv_path, encoding=encoding, sep=separator)

    df['tags'] = df['tags'].apply(lambda x: x.split('|') if x else [])

    for index, row in df.iterrows():
        new_resource = endpoints.FixedResourceEndpoint()

        data = {
            "title": row["title"],
            "template": category_id
        }

        if row["tags"]:
            data["tags"] = row["tags"]

        post = new_resource.post(data=data)
        if post.status_code == 201:
            new_resources += 1

    return new_resources
