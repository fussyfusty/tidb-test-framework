"""Unified test case model for all formats."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pathlib import Path


class TestType(Enum):
    """Test case type."""
    QUERY = "query"          # SELECT statement with result check
    STATEMENT = "statement"   # DDL/DML without result check
    ERROR = "error"           # Statement that should fail


@dataclass
class TestCase:
    """Unified test case model.
    
    This model represents a test case regardless of its original format
    (.test, .yaml, or .py). All loaders should convert to this format.
    """
    # Basic information
    id: str
    name: str
    file_path: Path
    format: str  # original format: 'test', 'yaml', 'py'
    
    # SQL content
    sql: str
    expected_result: Optional[Any] = None
    expected_error: Optional[str] = None
    
    # Test type
    test_type: TestType = TestType.STATEMENT
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    description: Optional[str] = None
    
    # Version control
    min_version: Optional[str] = None
    max_version: Optional[str] = None
    skip_versions: List[str] = field(default_factory=list)
    version_specific_expected: Dict[str, Any] = field(default_factory=dict)
    
    # Execution control
    timeout: int = 300  # seconds
    retry: int = 0
    parallel_safe: bool = True
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)
    before_sql: List[str] = field(default_factory=list)
    after_sql: List[str] = field(default_factory=list)
    
    def get_expected_for_version(self, version: str) -> Any:
        """Get expected result for specific version."""
        if version in self.version_specific_expected:
            return self.version_specific_expected[version]
        return self.expected_result
    
    def should_skip_version(self, version: str) -> bool:
        """Check if test should be skipped for given version."""
        if self.min_version and version < self.min_version:
            return True
        if self.max_version and version > self.max_version:
            return True
        if version in self.skip_versions:
            return True
        return False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        # 处理日期类型
        expected_val = self.expected
        actual_val = self.actual
        
        # 转换日期对象为字符串
        if hasattr(expected_val, 'isoformat'):
            expected_val = expected_val.isoformat()
        if hasattr(actual_val, 'isoformat'):
            actual_val = actual_val.isoformat()
        
        # 递归处理列表中的日期
        if isinstance(expected_val, (list, tuple)):
            expected_val = self._convert_dates_in_list(expected_val)
        if isinstance(actual_val, (list, tuple)):
            actual_val = self._convert_dates_in_list(actual_val)
        
        return {
            "test_id": self.test_id,
            "status": self.status.value,
            "version": self.version,
            "duration": self.duration,
            "error_msg": self.error_msg,
            "expected": str(expected_val) if expected_val is not None else None,
            "actual": str(actual_val) if actual_val is not None else None,
            "ai_analysis": self.ai_analysis,
            "retry_count": self.retry_count,
            "attempt_history": self.attempt_history,
            "fix_by_ai": self.fix_generated
        }

    def _convert_dates_in_list(self, items):
        """递归转换列表中的日期对象"""
        result = []
        for item in items:
            if hasattr(item, 'isoformat'):
                result.append(item.isoformat())
            elif isinstance(item, (list, tuple)):
                result.append(self._convert_dates_in_list(item))
            else:
                result.append(item)
        return result