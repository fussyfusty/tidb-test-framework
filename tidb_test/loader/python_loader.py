"""Python loader for complex test scenarios."""

import importlib.util
import inspect
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from tidb_test.loader.base_loader import BaseLoader
from tidb_test.models.test_case import TestCase, TestType
from tidb_test.exceptions import TestCaseError


class PythonLoader(BaseLoader):
    """Loader for Python test files.
    
    Python tests allow complex scenarios like:
    - Chaos engineering tests
    - Flaky test detection
    - Distributed system tests
    - Custom test logic
    """
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def can_load(self, file_path: Path) -> bool:
        """Check if file is a Python test file."""
        return file_path.suffix.lower() == '.py'
    
    def load(self, file_path: Path) -> List[TestCase]:
        """Load test cases from Python file.
        
        Python test files should define functions with naming:
        - test_* : individual test cases
        - setup_module/teardown_module: module level setup
        - setup_function/teardown_function: test level setup
        """
        self.validate_file(file_path)
        
        try:
            # Load module dynamically
            module_name = file_path.stem
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                raise TestCaseError(f"Failed to load module: {file_path}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            test_cases = []
            
            # Find all test functions
            for name, obj in inspect.getmembers(module):
                if name.startswith('test_') and callable(obj):
                    # Get docstring as description
                    description = inspect.getdoc(obj) or ''
                    
                    # Get test metadata from function attributes
                    tags = getattr(obj, '__test_tags__', [])
                    timeout = getattr(obj, '__test_timeout__', 300)
                    
                    # Create test case
                    test_case = self.create_test_case(
                        id=f"{file_path.stem}_{name}",
                        name=name,
                        file_path=file_path,
                        format='python',
                        sql=f"PYTHON_TEST:{name}",  # Special marker for Python tests
                        test_type=TestType.STATEMENT,
                        description=description,
                        tags=tags,
                        timeout=timeout,
                        # Store the function for execution
                        # _test_func=obj
                    )
                    test_cases.append(test_case)
            
            self.logger.info(f"Loaded {len(test_cases)} Python tests from {file_path}")
            return test_cases
            
        except Exception as e:
            raise TestCaseError(f"Failed to load Python file {file_path}: {e}") from e


def mark_tag(*tags):
    """Decorator to add tags to test functions."""
    def decorator(func):
        func.__test_tags__ = tags
        return func
    return decorator


def mark_timeout(timeout: int):
    """Decorator to set timeout for test functions."""
    def decorator(func):
        func.__test_timeout__ = timeout
        return func
    return decorator