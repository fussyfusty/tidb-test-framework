"""Base loader for all test case formats."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional
import logging

from tidb_test.models.test_case import TestCase
from tidb_test.exceptions import TestCaseError


class BaseLoader(ABC):
    """Base class for all test loaders."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def can_load(self, file_path: Path) -> bool:
        """Check if this loader can handle the file."""
        pass
    
    @abstractmethod
    def load(self, file_path: Path) -> List[TestCase]:
        """Load test cases from file.
        
        Args:
            file_path: Path to test file
            
        Returns:
            List of TestCase objects
            
        Raises:
            TestCaseError: If file cannot be parsed
        """
        pass
    
    def validate_file(self, file_path: Path) -> None:
        """Validate file exists and is readable."""
        if not file_path.exists():
            raise TestCaseError(f"File not found: {file_path}")
        
        if not file_path.is_file():
            raise TestCaseError(f"Not a file: {file_path}")
        
        if file_path.stat().st_size == 0:
            self.logger.warning(f"Empty test file: {file_path}")
    
    def create_test_case(self, **kwargs) -> TestCase:
        """Create a TestCase instance with defaults."""
        defaults = {
            "file_path": Path("unknown"),
            "format": "unknown",
            "tags": [],
            "timeout": 300,
            "retry": 0,
            "parallel_safe": True
        }
        defaults.update(kwargs)
        
        # Ensure id and name are set
        if "id" not in defaults:
            defaults["id"] = str(defaults["file_path"].stem)
        if "name" not in defaults:
            defaults["name"] = defaults["id"]
        
        return TestCase(**defaults)