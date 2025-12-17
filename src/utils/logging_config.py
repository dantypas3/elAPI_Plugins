from __future__ import annotations

import logging
import logging.config

from src.utils.common import load_config
from src.utils.paths import LOGGING_CONFIG, BASE_DIR


def setup_logging() -> None:
  """
  Load logging configuration from JSON file.
  """
  if getattr(setup_logging, "_configured", False):
    return

  logging_config = load_config(LOGGING_CONFIG)

  for handler in logging_config.get("handlers", {}).values():
    filename = handler.get("filename")
    if filename:
      log_path = BASE_DIR / "logs" / filename
      log_path.parent.mkdir(parents=True, exist_ok=True)

      handler["filename"] = str(log_path)

  logging.config.dictConfig(logging_config)
  setup_logging._configured = True  # type: ignore[attr-defined]
