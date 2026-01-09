from typing import Dict, Type

from src.services.importers.base_importer import BaseImporter
from src.services.importers.experiments_importer import ExperimentsImporter
from src.services.importers.resources_importer import ResourcesImporter


class ImporterFactory:
    _importers: Dict[str, Type[BaseImporter]] = {
        "resources": ResourcesImporter,
        }

    @classmethod
    def get_importer (cls, name: str, *args, **kwargs) -> BaseImporter:
        importer_cls = cls._importers.get(name)
        if importer_cls is None:
            raise ValueError(f"No importer configured for '{name}'")
        return importer_cls(*args, **kwargs)
