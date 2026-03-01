"""YAML format loader for TiDB feature tests."""

import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from tidb_test.loader.base_loader import BaseLoader
from tidb_test.models.test_case import TestCase, TestType
from tidb_test.exceptions import TestCaseError


class YAMLLoader(BaseLoader):
    """Loader for YAML format test files.
    
    YAML format supports rich metadata:
    - id: unique test identifier
    - name: test name
    - sql: SQL to execute
    - expected: expected result
    - tags: list of tags
    - description: test description
    - expected_per_version: version-specific expectations
    - timeout: test timeout
    - retry: retry count
    """
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def can_load(self, file_path: Path) -> bool:
        """Check if file is a YAML test file."""
        return file_path.suffix.lower() in ['.yaml', '.yml']
    
    def load(self, file_path: Path) -> List[TestCase]:
        """Load test cases from YAML file."""
        self.validate_file(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, list):
                data = [data]
            
            test_cases = []
            for i, item in enumerate(data):
                test_case = self._convert_to_test_case(item, file_path, i)
                test_cases.append(test_case)
            
            self.logger.info(f"Loaded {len(test_cases)} test cases from {file_path}")
            return test_cases
            
        except Exception as e:
            raise TestCaseError(f"Failed to parse YAML {file_path}: {e}") from e
    
    def _convert_to_test_case(self, item: Dict[str, Any], file_path: Path, index: int) -> TestCase:
        """Convert YAML item to TestCase model."""
        
        # Determine test type
        test_type = TestType.STATEMENT
        if 'expected_error' in item:
            test_type = TestType.ERROR
        elif 'expected' in item and item['expected'] is not None:
            test_type = TestType.QUERY
        
        # Handle version-specific expectations
        version_specific = {}
        if 'expected_per_version' in item:
            version_specific = item['expected_per_version']
        
        # Get expected result
        expected_result = item.get('expected')
        expected_error = item.get('expected_error')
        
        # Use version-specific if available
        if version_specific:
            expected_result = None  # Will be resolved at execution time
        
        return self.create_test_case(
            id=item.get('id', f"{file_path.stem}_{index:03d}"),
            name=item.get('name', item.get('id', f"test_{index}")),
            file_path=file_path,
            format='yaml',
            sql=item['sql'],
            test_type=test_type,
            expected_result=expected_result,
            expected_error=expected_error,
            tags=item.get('tags', []),
            description=item.get('description'),
            version_specific_expected=version_specific,
            timeout=item.get('timeout', 300),
            retry=item.get('retry', 0),
            parallel_safe=item.get('parallel_safe', True),
            depends_on=item.get('depends_on', [])
        )