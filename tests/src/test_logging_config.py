from __future__ import annotations

import logging

from src.utils.logging_config import _coerce_level, setup_logging


def test_coerce_level_handles_strings_and_ints() -> None:
    assert _coerce_level("10") == 10
    assert _coerce_level("debug") == "DEBUG"
    assert _coerce_level(20) == 20
    assert _coerce_level(None) is None


def test_setup_logging_runs_idempotently() -> None:
    setup_logging(level="INFO", force=True)
    logger = logging.getLogger("test")
    logger.info("logging initialized")
    # Call again to ensure guard works without raising
    setup_logging(level="INFO", force=False)
