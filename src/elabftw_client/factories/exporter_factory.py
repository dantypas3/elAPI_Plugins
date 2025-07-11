from typing import Callable, Dict, Optional

from src.elabftw_client.services.exporters import ExperimentsExporter, ResourceExporter
from src.elabftw_client.services.exporters.base_exporter import BaseExporter


class ExporterFactory:
    _exporters: Dict[str, Callable[..., BaseExporter]] = {
        "resources": ResourceExporter,
        "experiments": ExperimentsExporter,
    }

    @classmethod
    def get_exporter(cls, name: str, obj_id: Optional[int] = None) -> BaseExporter:
        exporter_cls = cls._exporters.get(name)
        if exporter_cls is None:
            raise ValueError(f"No exporter configured for '{name}'")

        if name == "resources":
            if obj_id is None:
                raise ValueError("Must pass obj_id for 'resources'")
            return exporter_cls(obj_id)

        return exporter_cls()
