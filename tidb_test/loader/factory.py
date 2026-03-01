"""Factory for creating appropriate loaders based on file extension."""

from pathlib import Path
from typing import Dict, Type, List, Optional
import logging

from tidb_test.loader.base_loader import BaseLoader
from tidb_test.loader.sqllogic_loader import SqllogicLoader
from tidb_test.loader.yaml_loader import YAMLLoader
from tidb_test.loader.python_loader import PythonLoader
from tidb_test.exceptions import FormatNotSupportedError


class LoaderFactory:
    """Factory that returns appropriate loader for a file."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._loaders: Dict[str, BaseLoader] = {}
        self._register_default_loaders()
    
    def _register_default_loaders(self) -> None:
        """Register built-in loaders."""
        self.register_loader('.test', SqllogicLoader())
        self.register_loader('.yaml', YAMLLoader())
        self.register_loader('.yml', YAMLLoader())
        self.register_loader('.py', PythonLoader())
    
    def register_loader(self, extension: str, loader: BaseLoader) -> None:
        """Register a loader for a file extension."""
        self._loaders[extension.lower()] = loader
        self.logger.debug(f"Registered loader for {extension}: {loader.__class__.__name__}")
    
    def get_loader(self, file_path: Path) -> Optional[BaseLoader]:
        """Get appropriate loader for file based on extension."""
        if not file_path.exists():
            return None
        
        extension = file_path.suffix.lower()
        
        # First try exact extension match
        if extension in self._loaders:
            loader = self._loaders[extension]
            if loader.can_load(file_path):
                return loader
        
        # Then ask each loader if they can handle it
        for loader in self._loaders.values():
            if loader.can_load(file_path):
                return loader
        
        return None
    
    def load_file(self, file_path: Path) -> List:
        """Load test cases from file using appropriate loader."""
        loader = self.get_loader(file_path)
        if not loader:
            raise FormatNotSupportedError(
                f"No loader found for file: {file_path} "
                f"(supported: {list(self._loaders.keys())})"
            )
        
        self.logger.info(f"Loading {file_path} with {loader.__class__.__name__}")
        return loader.load(file_path)
    
    # def load_directory(self, directory: Path, pattern: str = "*") -> List:
    #     """Load all test files from directory."""
    #     if not directory.exists() or not directory.is_dir():
    #         raise FormatNotSupportedError(f"Directory not found: {directory}")
        
    #     all_tests = []
    #     for file_path in directory.glob(pattern):
    #         if file_path.is_file() and file_path.name != '__init__.py':
    #             try:
    #                 tests = self.load_file(file_path)
    #                 all_tests.extend(tests)
    #             except Exception as e:
    #                 self.logger.error(f"Failed to load {file_path}: {e}")
        
    #     return all_tests
    def load_directory(self, directory: Path, pattern: str = "*", recursive: bool = False) -> List:
        """Load all test files from directory, excluding __init__.py.
        
        Args:
            directory: Directory to load tests from
            pattern: File pattern to match (default: "*")
            recursive: Whether to recursively load subdirectories (default: False)
        """
        if not directory.exists() or not directory.is_dir():
            self.logger.error(f"Directory not found: {directory}")
            return []
        
        all_tests = []
        
        # 根据是否递归选择不同的 glob 模式
        if recursive:
            files = directory.glob(f"**/{pattern}")
        else:
            files = directory.glob(pattern)
        
        for file_path in files:
            # 跳过 __init__.py 和其他非测试文件
            if not file_path.is_file() or file_path.name == '__init__.py':
                continue
                
            # 根据扩展名判断是否应该加载
            if file_path.suffix in self.supported_extensions or any(
                loader.can_load(file_path) for loader in self._loaders.values()
            ):
                try:
                    tests = self.load_file(file_path)
                    all_tests.extend(tests)
                    self.logger.debug(f"Loaded {len(tests)} tests from {file_path}")
                except Exception as e:
                    self.logger.error(f"Failed to load {file_path}: {e}")
        
        self.logger.info(f"Loaded total {len(all_tests)} tests from {directory}")
        return all_tests
    
    @property
    def supported_extensions(self) -> List[str]:
        """Get list of supported file extensions."""
        return list(self._loaders.keys())