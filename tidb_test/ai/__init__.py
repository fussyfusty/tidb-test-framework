"""
AI 模块 - 提供测试失败分析和自动修复功能

已实现功能:
- analyzer.AIFailureAnalyzer: 失败原因分析
- fixer.AIFixer: 修复用例生成

🚧 待完善:
- 批量分析
- 缓存机制
- 多模型支持
"""

from .analyzer import AIFailureAnalyzer
from .fixer import AIFixer

__all__ = ['AIFailureAnalyzer', 'AIFixer']