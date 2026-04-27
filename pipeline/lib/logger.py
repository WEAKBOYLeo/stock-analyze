"""
Task-level logging for pipeline operations.

Usage:
    from lib.logger import TaskLogger
    log = TaskLogger("task_name")
    log.info("Starting search for AAPL 10-K")
    log.warn("Rate limit hit, waiting 5s")
    log.error("API returned 403")
"""

import logging
import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")


class TaskLogger:
    """Creates a logger that writes to both stdout and a task-specific log file."""

    def __init__(self, task_name: str):
        os.makedirs(LOG_DIR, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_path = os.path.join(LOG_DIR, f"{task_name}_{timestamp}.log")

        self.logger = logging.getLogger(f"pipeline.{task_name}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        # File handler — full detail
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)-5s] %(message)s", "%H:%M:%S"
        ))
        self.logger.addHandler(fh)

        # Console handler — info and above
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("[%(levelname)-5s] %(message)s"))
        self.logger.addHandler(ch)

        self.log_path = log_path

    def debug(self, msg):   self.logger.debug(msg)
    def info(self, msg):    self.logger.info(msg)
    def warn(self, msg):    self.logger.warning(msg)
    def error(self, msg):   self.logger.error(msg)

    def section(self, title: str):
        """Log a visible section header."""
        self.logger.info("─" * 50)
        self.logger.info(f"  {title}")
        self.logger.info("─" * 50)

    def summary(self, items: dict):
        """Log a key-value summary block."""
        self.logger.info("")
        for k, v in items.items():
            self.logger.info(f"  {k}: {v}")
        self.logger.info("")
