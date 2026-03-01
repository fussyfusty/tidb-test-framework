"""Unified test case model for all formats."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pathlib import Path


class TestStatus(Enum):
    """Test execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    """Test execution result."""
    test_id: str
    status: TestStatus
    version: str
    duration: float = 0.0
    error_msg: Optional[str] = None
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    ai_analysis: Optional[str] = None
    retry_count: int = 0
    attempt_history: List[Dict] = field(default_factory=list)
    fix_generated: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "test_id": self.test_id,
            "status": self.status.value,
            "version": self.version,
            "duration": self.duration,
            "error_msg": self.error_msg,
            "expected": str(self.expected) if self.expected else None,
            "actual": str(self.actual) if self.actual else None,
            "ai_analysis": self.ai_analysis,
            "retry_count": self.retry_count,
            "attempt_history": self.attempt_history,
            "fix_generated": self.fix_generated
        }
