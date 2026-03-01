"""Loader for sqllogictest format (.test files)."""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from tidb_test.loader.base_loader import BaseLoader
from tidb_test.models.test_case import TestCase, TestType
from tidb_test.exceptions import TestCaseError
from tidb_test.utils import parse_sqllogic_test


class SqllogicLoader(BaseLoader):
    """Loader for sqllogictest format.
    
    This loader parses .test files which use the sqllogictest format:
    - query <col_types> [<sort_mode>]
    - statement ok
    - statement error <pattern>
    - ---- (separator for expected results)
    
    Reference: https://www.sqlite.org/sqllogictest/doc/trunk/about.wiki
    """
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def can_load(self, file_path: Path) -> bool:
        """Check if file is a sqllogictest file."""
        return file_path.suffix.lower() == '.test'
    
    def load(self, file_path: Path) -> List[TestCase]:
        """Load test cases from .test file."""
        self.validate_file(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse using utility function
            statements = parse_sqllogic_test(content)
            
            test_cases = []
            for i, stmt in enumerate(statements):
                test_case = self._convert_to_test_case(stmt, file_path, i)
                test_cases.append(test_case)
            
            self.logger.info(f"Loaded {len(test_cases)} test cases from {file_path}")
            return test_cases
            
        except Exception as e:
            raise TestCaseError(f"Failed to parse {file_path}: {e}") from e
    
    def _convert_to_test_case(self, stmt: Dict[str, Any], file_path: Path, index: int) -> TestCase:
        """Convert parsed statement to TestCase model."""
        
        # Basic common fields
        case_id = f"{file_path.stem}_{index+1:03d}"
        
        # Determine test type
        test_type = TestType.STATEMENT
        expected_result = None
        expected_error = None
        
        if stmt['type'] == 'query':
            test_type = TestType.QUERY
            # Parse expected results
            if 'expected' in stmt and stmt['expected']:
                # Convert expected lines to list of rows
                expected_result = []
                for line in stmt['expected']:
                    if line.strip():
                        # Split by whitespace and convert based on col_types
                        values = line.split()
                        if 'col_types' in stmt:
                            # TODO: Convert based on column types
                            pass
                        expected_result.append(tuple(values))
                    else:
                        expected_result.append(())
            
        elif stmt['type'] == 'statement_error':
            test_type = TestType.ERROR
            expected_error = stmt.get('error_pattern', '.*')
        
        # Extract metadata from comments (if any)
        tags = []
        description = None
        if '--' in stmt.get('sql', ''):
            # Parse comments for metadata
            # Example: -- @tag: ddl, basic
            #         -- @description: Create table test
            lines = stmt['sql'].split('\n')
            for line in lines:
                if line.strip().startswith('-- @'):
                    meta = line.strip()[4:].split(':')
                    if len(meta) == 2:
                        key, value = meta[0].strip(), meta[1].strip()
                        if key == 'tag':
                            tags = [t.strip() for t in value.split(',')]
                        elif key == 'description':
                            description = value
        
        # Create test case
        return self.create_test_case(
            id=case_id,
            name=f"{file_path.stem}_{index}",
            file_path=file_path,
            format='test',
            sql=stmt['sql'],
            test_type=test_type,
            expected_result=expected_result,
            expected_error=expected_error,
            tags=tags,
            description=description,
            # Default values for sqllogictest
            timeout=30,
            retry=0,
            parallel_safe=True
        )
    
    def load_directory(self, directory: Path, recursive: bool = True) -> List[TestCase]:
        """Load all .test files from directory."""
        if not directory.exists():
            raise TestCaseError(f"Directory not found: {directory}")
        
        pattern = "**/*.test" if recursive else "*.test"
        test_files = list(directory.glob(pattern))
        
        all_tests = []
        for test_file in test_files:
            try:
                tests = self.load(test_file)
                all_tests.extend(tests)
            except Exception as e:
                self.logger.error(f"Failed to load {test_file}: {e}")
        
        self.logger.info(f"Loaded total {len(all_tests)} test cases from {directory}")
        return all_tests