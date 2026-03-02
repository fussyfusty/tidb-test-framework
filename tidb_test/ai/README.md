# AI 模块说明

## 已实现功能 

### AIFailureAnalyzer (`analyzer.py`)
- 失败原因分析
- 结果不匹配分析
- 重试历史分析

### AIFixer (`fixer.py`)
- 修复用例生成
- Diff 对比生成
- 修复文件保存

## 待完善功能 

### 短期计划
- 批量分析相似错误
- 缓存相似错误减少 API 调用

### 长期规划
- 多模型支持（OpenAI/Claude）
- 提示词模板化配置
- 历史数据分析