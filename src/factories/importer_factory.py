from typing import Callable, Dict

from labfolder_migration.coordinator import MigrationCoordinator

from services.importers import BaseImporter, ResourcesImporter, \
    ExperimentsImporter


class ImporterFactory:
    _importers: Dict[str, Callable[..., BaseImporter]] = {
        "resources"  : ResourcesImporter,
        "experiments": ExperimentsImporter,
        "labfolder"  : MigrationCoordinator
        }

    @classmethod
    def get_importer (cls, name: str) -> BaseImporter:
        importer_cls = cls._importers.get(name)
        if importer_cls is None:
            raise ValueError(f"No importer configured for '{name}'")
        return importer_cls()
