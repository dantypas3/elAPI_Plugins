from collections.abc import Callable

from ..services.exporters import ExperimentsExporter, ResourcesExporter
from ..services.exporters.base_exporter import BaseExporter


class ExporterFactory:
    """Factory for eLabFTW exporter classes."""

    _exporters: dict[str, Callable[..., BaseExporter]] = {
        "resources": ResourcesExporter,
        "experiments": ExperimentsExporter,
    }

    @classmethod
    def get_exporter(cls, name: str, obj_id: int | None = None) -> BaseExporter:
        """Call the needed exporter."""
        exporter_cls = cls._exporters.get(name)
        if exporter_cls is None:
            raise ValueError(f"No exporter configured for '{name}'")

        if name == "resources":
            if obj_id is None:
                raise ValueError("Must pass obj_id for 'resources'")
            return exporter_cls(obj_id)

        return exporter_cls()
