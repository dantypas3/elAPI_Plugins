from typing import Tuple

from .labfolder_client import LabfolderClient

class LabFolderExtractor:
    """
    Wraps your Labfolder client to fetch raw entries.
    """

    def __init__(
        self,
        email: str,
        password: str,
        base_url: str,
    ) -> None:
        self._client = LabfolderClient(email, password, base_url)
        self._client.login()


    def get_raw_entries(self) -> Tuple[list, list, list]:

        client = self._client
        print("raw_experiments")
        raw_experiments = self._client.get_projects(limit=100)
        print("raw_experiment_entries")
        raw_experiment_entries = self._client.get_project_data()
        print("raw_experiments_content")
        raw_experiments_content = self._client.get_notebook_entries_content()

        return raw_experiments, raw_experiment_entries, raw_experiments_content
