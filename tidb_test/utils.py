"""Utility functions for TiDB test framework."""

import re
import yaml
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime


def setup_logger(name: str, level=logging.INFO) -> logging.Logger:
    """Setup logger with consistent format."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


def normalize_sql(sql: str) -> str:
    """Normalize SQL string for comparison."""
    # Remove extra whitespace
    sql = ' '.join(sql.split())
    # Remove comments
    sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    return sql.strip()


def compare_results(expected: Any, actual: Any, strict: bool = False) -> bool:
    """Compare expected and actual results.
    
    Args:
        expected: Expected result
        actual: Actual result
        strict: If True, use strict type comparison
        
    Returns:
        True if results match
    """
    if strict:
        return expected == actual
    
    # Non-strict: try to convert types
    try:
        if isinstance(expected, (list, tuple)) and isinstance(actual, (list, tuple)):
            if len(expected) != len(actual):
                return False
            return all(compare_results(e, a, strict) for e, a in zip(expected, actual))
        
        # Try to convert both to strings for comparison
        return str(expected).strip() == str(actual).strip()
    except:
        return False


def load_yaml_with_includes(file_path: Path) -> Dict:
    """Load YAML file with support for !include directive."""
    def yaml_include(loader, node):
        """Custom YAML tag to include other files."""
        filename = Path(loader.name).parent / node.value
        with open(filename) as f:
            return yaml.safe_load(f)
    
    # Register custom tag
    yaml.add_constructor('!include', yaml_include)
    
    with open(file_path) as f:
        return yaml.safe_load(f)


def format_timestamp() -> str:
    """Get current timestamp for reporting."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_directory(path: Path) -> Path:
    """Ensure directory exists and return path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_sqllogic_test(content: str) -> List[Dict]:
    """Parse sqllogictest format content.
    
    Args:
        content: Raw test file content
        
    Returns:
        List of test statements with their expected results
    """
    lines = content.split('\n')
    tests = []
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines and comments
        if not line or line.startswith('#'):
            i += 1
            continue
        
        # Parse statement ok
        if line.startswith('statement ok'):
            # Collect SQL lines until next directive or end
            sql_lines = []
            i += 1
            while i < len(lines):
                current = lines[i].strip()
                if not current or current.startswith('statement') or current.startswith('query') or current.startswith('#'):
                    break
                if current and not current.startswith('----'):
                    sql_lines.append(current)
                i += 1
            
            if sql_lines:
                tests.append({
                    'type': 'statement_ok',
                    'sql': ' '.join(sql_lines)
                })
            continue
            
        # Parse statement error
        elif line.startswith('statement error'):
            # Extract error pattern if present
            error_pattern = line[15:].strip() or '.*'
            
            # Collect SQL lines
            sql_lines = []
            i += 1
            while i < len(lines):
                current = lines[i].strip()
                if not current or current.startswith('statement') or current.startswith('query') or current.startswith('#'):
                    break
                if current and not current.startswith('----'):
                    sql_lines.append(current)
                i += 1
            
            if sql_lines:
                tests.append({
                    'type': 'statement_error',
                    'error_pattern': error_pattern,
                    'sql': ' '.join(sql_lines)
                })
            continue
            
        # Parse query
        elif line.startswith('query'):
            # Parse query header
            parts = line.split()
            col_types = parts[1] if len(parts) > 1 else 'T'
            sort_mode = parts[2] if len(parts) > 2 else None
            
            # Collect SQL lines
            sql_lines = []
            i += 1
            while i < len(lines):
                current = lines[i].strip()
                if current == '----':
                    i += 1
                    break
                if current and not current.startswith('query') and not current.startswith('statement') and not current.startswith('#'):
                    sql_lines.append(current)
                i += 1
            
            sql = ' '.join(sql_lines)
            
            # Collect expected results
            expected_lines = []
            while i < len(lines):
                current = lines[i].rstrip()
                # Stop if next directive or empty line after results
                if not current or current.startswith('query') or current.startswith('statement') or current.startswith('#'):
                    break
                expected_lines.append(current)
                i += 1
            
            tests.append({
                'type': 'query',
                'col_types': col_types,
                'sort_mode': sort_mode,
                'sql': sql,
                'expected': expected_lines
            })
            continue
        
        else:
            # Skip unrecognized lines
            i += 1
    
    return tests