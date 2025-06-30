from pathlib import Path
from typing import Union
from utils import endpoints
from plugins.resources.patch import patch_resources_from_csv
import pandas as pd


"""
This script creates resources using a fixed API endpoint.
Created for: Universität Heidelberg – BZH - SFB 1638  
Author: Dionysios Antypas (dionysios.antypas@bzh.uni-heidelberg.de)  
Status: Work in progress

Description:
    - Displays available resource categories
    - Creates a new resource by selecting a category
    - Patches the created resource using data from a CSV file
"""

#TODO restructure & make sure it creates everything without patching

def create_resources(csv_path: Union[Path, str], encoding: str = 'utf-8', separator: str = ';'):
    """
    Create and patch one resource per row in the CSV file.
    If a row already has a 'resource_id', it will be skipped.
    The user selects the category once and it's applied to all new resources.
    """

    session = endpoints.FixedCategoryEndpoint()
    categories = session.get().json()
    df_categories = pd.json_normalize(categories)


    print("ID  Title")
    for category in categories:
        print(f"{category['id']}: {category['title']}")

    answer = int(input("Please enter the ID of the resource category to be used: "))
    category_df = df_categories[df_categories["id"] == answer]
    resource_category_id = int(category_df["id"])

    df = pd.read_csv(csv_path, encoding=encoding, sep=separator)

    if "id" not in df.columns:
        df["id"] = ""

    for index, row in df.iterrows():
        if not row.get("id"):
            print(f"\n Creating resource for row {index}...")

            new_resource = endpoints.FixedResourceEndpoint()
            post = new_resource.post(data={"id": resource_category_id})
            new_resource_url = post.headers.get("Location")
            new_resource_id = new_resource_url.rstrip("/").split("/")[-1]

            df.at[index, "id"] = new_resource_id
            print(f" Resource created with ID {new_resource_id}")

            df.to_csv(csv_path, encoding=encoding, sep=separator, index=False)

            patch_resources_from_csv(csv_path, encoding, separator)

        else:
            print(f"Row {index} already has a resource_id ({row['id']}). Skipping.")

    print(f"\n All missing resources created and patched. Final CSV saved to: {csv_path}")