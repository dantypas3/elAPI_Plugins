from typing import Callable, Dict, Optional

from src.elabftw_client.services.importers import BaseImporter, ResourcesImporter

class ImporterFactory:
	_importers: Dict[str, Callable[..., BaseImporter]] = {
		"resources": ResourcesImporter,
	}

	@classmethod
	def get_importer(cls, name: str) -> BaseImporter:
		importer_cls = cls._importers.get(name)
		if importer_cls is None:
			raise ValueError(f"No importer configured for '{name}'")
		return importer_cls()