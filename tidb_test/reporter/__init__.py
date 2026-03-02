# tidb_test/reporter/__init__.py
"""Reporter module for test results."""

from .console_reporter import ConsoleReporter
from .json_reporter import JSONReporter

__all__ = ['ConsoleReporter', 'JSONReporter']