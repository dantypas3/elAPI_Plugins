from pathlib import Path
from typing import Union
from elapi.api import FixedEndpoint
from utils import resource_utils
import patch_resources
import pandas as pd

"""

Created for: Universität Heidelberg – BZH - SFB 1638
Author: Dionysios Antypas (dionysios.antypas@bzh.uni-heidelberg.de)
Status: Work in progress

"""

def create_resource():
    """
    Create resources by using existing categories.
    The available categories will be displayed and
    the category number will be given as input by the user.
    """

    session = FixedEndpoint("items_types")
    categories = session.get().json()
    df_categories = pd.json_normalize(categories)

    print("ID  Title")
    for category in categories:
        print(f"{category["id"]}: {category['title']}")

    answer = int(input("Please enter id of the resource category to be used: "))
    category_df = df_categories[df_categories["id"] == answer]
    print(category_df)

    RESOURCE_CATEGORY_ID = int(category_df["id"])
    new_resource = resource_utils.FixedResourceEndpoint()

    new_resource.post(
        data = {"category_id": RESOURCE_CATEGORY_ID}
    )
    new_resource_id = new_resource.get().json()[0]["id"]

    print(f"Patching resource {new_resource_id}")
    patch_resources.patch_single_resource_from_csv(new_resource_id, "test_datei.csv", encoding="utf-8",
                                                   separator=";")