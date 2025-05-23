from utils import resource_utils
import json
import os
from typing import Union
from utils import paths

"""

Created for: Universität Heidelberg – BZH - SFB 1638
Author: Dionysios Antypas (dionysios.antypas@bzh.uni-heidelberg.de)
Status: Work in progress

"""

def json_export_resource(resource_id: Union[str, int], export_file =""):

    print(f"Validating resource ID: {resource_id}")
    resource_utils.ResourceIDValidator(resource_id).validate()

    print(f"Fetching resource {resource_id} from API...")
    session = resource_utils.FixedResourceEndpoint()
    resource = session.get(endpoint_id=526).json()
    resource_json = json.dumps(resource, indent=4)

    if export_file == "":
        export_file = paths.export_json(f"resouce_{resource_id}.json")
    else:
        export_file = paths.export_json(f"{export_file}.json")

    export_dir = os.path.dirname(export_file)
    os.makedirs(export_dir, exist_ok=True)

    with open(export_file, "w") as json_file:
        json_file.write(resource_json)



    if not resource_utils.is_file_created_and_not_empty(export_file):
        raise IOError("The output JSON file is empty or could not be written correctly.")

    print(f"Exported to: {export_file}")

    return resource_json