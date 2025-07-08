from elapi.api import FixedEndpoint

_ENDPOINT_MAP = {
    "resource": "items",
    "category": "items_types",
    "experiment": "experiments",
}

def get_fixed(name: str) -> FixedEndpoint:
    """Return a FixedEndpoint for one of: resource, category, experiment."""
    try:
        path = _ENDPOINT_MAP[name]
    except KeyError:
        raise ValueError(f"No endpoint configured for '{name}'")
    return FixedEndpoint(path)
