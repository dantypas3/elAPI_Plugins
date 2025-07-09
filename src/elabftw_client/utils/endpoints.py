from elapi.api import FixedEndpoint

_ENDPOINT_MAP = {
    "resources": "items",
    "category": "items_types",
    "experiments": "experiments",
}

def get_fixed(name: str) -> FixedEndpoint:
    """Return a FixedEndpoint for one of: resource, category, experiments."""
    try:
        path = _ENDPOINT_MAP[name]
    except KeyError:
        raise ValueError(f"No endpoint configured for '{name}'")
    return FixedEndpoint(path)
