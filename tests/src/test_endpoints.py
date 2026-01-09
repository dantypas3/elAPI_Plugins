from __future__ import annotations

import pytest

from src.utils import endpoints


def test_get_fixed_known_endpoint() -> None:
    ep = endpoints.get_fixed("resources")
    # Ensure FixedEndpoint exposes endpoint name attribute
    assert hasattr(ep, "endpoint_name")


def test_get_fixed_unknown_raises() -> None:
    with pytest.raises(ValueError):
        endpoints.get_fixed("unknown")
