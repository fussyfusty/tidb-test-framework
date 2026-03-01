"""Custom exceptions for TiDB test framework."""

class TiDBTestError(Exception):
    """Base exception for all framework errors."""
    pass

class ConnectionError(TiDBTestError):
    """Raised when database connection fails."""
    pass

class VersionNotFoundError(TiDBTestError):
    """Raised when specified version is not configured."""
    pass

class TestCaseError(TiDBTestError):
    """Raised when test case loading or parsing fails."""
    pass

class ExecutionError(TiDBTestError):
    """Raised during test execution."""
    pass

class AITimeoutError(TiDBTestError):
    """Raised when AI analysis times out."""
    pass

class FormatNotSupportedError(TiDBTestError):
    """Raised when test file format is not supported."""
    pass