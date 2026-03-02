"""AI-powered failure analysis for test results."""

import os
import logging
from typing import Dict, Any, Optional, List
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential


class AIFailureAnalyzer:
    """Analyze test failures using DeepSeek API (OpenAI-compatible)."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat"):
        """Initialize AI analyzer for DeepSeek.
        
        Args:
            model: DeepSeek model to use (default: deepseek-chat)
        """
        self.api_key = api_key or os.getenv("AI_API_KEY")
        if not self.api_key:
            raise ValueError("DeepSeek API key required. Set DEEPSEEK_API_KEY environment variable.")
        
        self.model = model
        self.logger = logging.getLogger(__name__)
        
        # DeepSeek API 配置
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com/v1",  # DeepSeek API 地址
            timeout=30.0  # 设置总超时30秒
        )
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=8))
    def analyze_failure(self, test_case, error: Dict[str, Any]) -> str:
        """Analyze test failure and provide insights."""
        # 获取 test_case 属性
        sql = getattr(test_case, 'sql', 'Unknown SQL')
        test_id = getattr(test_case, 'id', 'unknown')
        
        prompt = f"""You are a TiDB database expert. Analyze this test failure and provide concise, actionable fixes.

Test Information:
- Test ID: {test_id}
- SQL: {sql[:300]}
- Error Code: {error.get('code', 'unknown')}
- Error Message: {error.get('message', 'N/A')}

Please provide in Chinese:
1. Root cause (1 sentence)
2. Fix suggestion (1-2 sentences)
3. Prevention tip (1 sentence)

Keep response concise and actionable."""
        
        try:
            self.logger.info(f"Sending request to DeepSeek for {test_id}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # DeepSeek 推荐使用较低温度
                max_tokens=500
            )
            
            analysis = response.choices[0].message.content
            self.logger.info(f"AI analysis generated for {test_id}")
            return analysis
            
        except Exception as e:
            self.logger.error(f"AI analysis failed: {e}")
            return f"AI分析暂时不可用: {str(e)}"
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=8))
    def analyze_mismatch(self, test_case, expected, actual) -> str:
        """Analyze result mismatch."""
        sql = getattr(test_case, 'sql', 'Unknown SQL')
        test_id = getattr(test_case, 'id', 'unknown')
        
        prompt = f"""You are a TiDB expert analyzing test result mismatches.

Test ID: {test_id}
SQL: {sql[:300]}
Expected: {expected}
Actual: {actual}

Please explain in Chinese:
1. Why the results differ
2. How to fix the test or query
3. If this is a TiDB-specific behavior

Keep response concise."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=400
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"AI mismatch analysis failed: {e}")
            return f"AI分析暂时不可用: {str(e)}"

    # def analyze_with_retry_history(self, test_case, history: List[Dict]) -> str:
    #     """Analyze test failure based on retry history patterns.
        
    #     策略：
    #     1. 如果所有重试结果都一样 → 只分析一次（稳定失败）
    #     2. 如果重试结果不一样 → 分析变化模式（flaky）
    #     3. 如果部分成功部分失败 → 重点分析不稳定原因
    #     """
        
    #     sql = getattr(test_case, 'sql', 'Unknown SQL')
    #     test_id = getattr(test_case, 'id', 'unknown')
        
    #     # 提取每次尝试的关键信息
    #     attempts = []
    #     errors = []
    #     for h in history:
    #         attempt_info = {
    #             'attempt': h['attempt'],
    #             'status': h['status'],
    #             'duration': f"{h['duration']:.2f}s"
    #         }
    #         if h['status'] == 'error' and h.get('error'):
    #             error_msg = h['error'].get('message', '')
    #             error_code = h['error'].get('code', '')
    #             attempt_info['error'] = f"({error_code}) {error_msg[:100]}"
    #             errors.append(attempt_info['error'])
    #         attempts.append(attempt_info)
        
    #     # 判断错误模式
    #     unique_errors = set(errors)
    #     error_count = len(unique_errors)
        
    #     # 根据模式选择不同的prompt
    #     if error_count == 0:
    #         # 所有尝试都成功（不应该调用此函数）
    #         return "所有重试都成功了，无需分析"
            
    #     elif error_count == 1:
    #         # 所有错误都一样 - 稳定失败
    #         prompt = self._build_stable_failure_prompt(test_id, sql, attempts, list(unique_errors)[0])
            
    #     elif error_count > 1:
    #         # 错误在变化 - flaky test
    #         prompt = self._build_flaky_failure_prompt(test_id, sql, attempts, list(unique_errors))
        
    #     try:
    #         response = self.client.chat.completions.create(
    #             model=self.model,
    #             messages=[{"role": "user", "content": prompt}],
    #             temperature=0.1,
    #             max_tokens=500
    #         )
    #         return response.choices[0].message.content
    #     except Exception as e:
    #         self.logger.error(f"AI analysis failed: {e}")
    #         return f"AI分析暂时不可用: {str(e)}"

    # def _build_stable_failure_prompt(self, test_id, sql, attempts, error_pattern):
    #     """构建稳定失败的prompt - 只分析一次"""
        
    #     attempts_summary = "\n".join([
    #         f"尝试 {a['attempt']}: {a['status']} ({a['duration']})"
    #         for a in attempts
    #     ])
        
    #     return f"""You are a TiDB database expert. Analyze this stable test failure (same error in all retries).

    # Test Information:
    # - Test ID: {test_id}
    # - SQL: {sql[:300]}
    # - Retry attempts: {len(attempts)}

    # Execution History:
    # {attempts_summary}

    # Error Pattern (consistent):
    # {error_pattern}

    # Please provide in Chinese:
    # 1. Root cause of this consistent failure
    # 2. Fix suggestion
    # 3. Prevention tip

    # Keep response concise."""
    def analyze_with_retry_history(self, test_case, history: List[Dict]) -> str:
        """Analyze test failure based on retry history patterns."""
        
        sql = getattr(test_case, 'sql', 'Unknown SQL')
        test_id = getattr(test_case, 'id', 'unknown')
        
        # 获取测试类型和期望值
        test_type = getattr(test_case, 'test_type', None)
        expected = getattr(test_case, 'expected', None)
        expected_error = getattr(test_case, 'expected_error', None)
        
        # 提取每次尝试的关键信息
        attempts = []
        errors = []
        for h in history:
            attempt_info = {
                'attempt': h['attempt'],
                'status': h['status'],
                'duration': f"{h['duration']:.2f}s"
            }
            if h['status'] == 'error' and h.get('error'):
                error_msg = h['error'].get('message', '')
                error_code = h['error'].get('code', '')
                attempt_info['error'] = f"({error_code}) {error_msg[:100]}"
                errors.append(attempt_info['error'])
            elif h['status'] == 'success' and h.get('data') is not None:
                attempt_info['data'] = str(h['data'])
            attempts.append(attempt_info)
        
        # 判断错误模式
        unique_errors = set(errors)
        error_count = len(unique_errors)
        
        # 判断是否是结果不匹配
        is_mismatch = False
        if error_count == 0:
            # 检查 test_type 是否是 QUERY 类型
            if test_type is not None:
                # 处理枚举类型
                if hasattr(test_type, 'value'):
                    test_type_value = test_type.value
                else:
                    test_type_value = str(test_type).lower()
                
                if test_type_value in ['query', 'QUERY']:
                    is_mismatch = True
                else:
                    # 如果不是 QUERY 类型但有期望值，也可能是 mismatch
                    if expected is not None:
                        is_mismatch = True
        
        if is_mismatch:
            # 结果不匹配的情况
            prompt = self._build_mismatch_prompt(test_id, sql, attempts, expected)
            
        elif error_count == 1:
            # 所有错误都一样 - 稳定失败
            prompt = self._build_stable_failure_prompt(test_id, sql, attempts, list(unique_errors)[0])
            
        elif error_count > 1:
            # 错误在变化 - flaky test
            prompt = self._build_flaky_failure_prompt(test_id, sql, attempts, list(unique_errors))
        
        else:
            # 其他情况
            return "无法分析测试失败原因"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"AI analysis failed: {e}")
            return f"AI分析暂时不可用: {str(e)}"

    def _build_mismatch_prompt(self, test_id, sql, attempts, expected):
        """构建结果不匹配的分析提示"""
        
        attempts_summary = "\n".join([
            f"尝试 {a['attempt']}: {a['status']} ({a['duration']}) - 返回: {a.get('data', 'N/A')}"
            for a in attempts
        ])
        
        prompt = f"""You are a TiDB database expert. Analyze this test result mismatch.

    Test Information:
    - Test ID: {test_id}
    - SQL: {sql[:300]}
    - Expected Result: {expected}

    Execution History:
    {attempts_summary}

    The SQL executed successfully but returned a different result than expected.
    Please analyze:
    1. Why the actual result differs from expected
    2. Common causes (data type issues, TiDB-specific behavior, query logic errors)
    3. How to fix the test or query

    Provide concise, actionable analysis in Chinese.
    """
        return prompt

    def _build_flaky_failure_prompt(self, test_id, sql, attempts, error_patterns):
        """构建flaky测试的prompt - 分析变化模式"""
        
        attempts_summary = "\n".join([
            f"尝试 {a['attempt']}: {a['status']} ({a['duration']}) - {a.get('error', 'success')}"
            for a in attempts
        ])
        
        patterns_summary = "\n".join([f"- {e}" for e in error_patterns])
        
        return f"""You are a TiDB database expert analyzing a flaky test (inconsistent results).

    Test Information:
    - Test ID: {test_id}
    - SQL: {sql[:300]}
    - Retry attempts: {len(attempts)}

    Execution History:
    {attempts_summary}

    Different Error Patterns Observed:
    {patterns_summary}

    Please provide in Chinese:
    1. Why this test is flaky (different results across retries)
    2. Possible causes (timing, concurrency, data state, etc.)
    3. Suggestions to stabilize the test
    4. If this indicates a real bug in TiDB

    Keep response focused on flaky test analysis."""

    def _build_stable_failure_prompt(self, test_id, sql, attempts, error):
        """构建稳定失败的prompt - 分析一致性错误"""
        
        attempts_summary = "\n".join([
            f"尝试 {a['attempt']}: {a['status']} ({a['duration']}) - {a.get('error', 'success')}"
            for a in attempts
        ])
        
        prompt = f"""You are a TiDB database expert. Analyze this stable test failure (same error in all retries).

    Test Information:
    - Test ID: {test_id}
    - SQL: {sql[:300]}
    - Retry attempts: {len(attempts)}

    Execution History:
    {attempts_summary}

    Error Pattern (consistent):
    {error}

    Please provide in Chinese:
    1. Root cause of this consistent failure
    2. Fix suggestion
    3. Prevention tip

    Keep response concise and actionable.
    """
        return prompt
