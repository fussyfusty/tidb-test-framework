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

    def analyze_with_retry_history(self, test_case, history: List[Dict]) -> str:
        """Analyze test failure based on retry history patterns.
        
        策略：
        1. 如果所有重试结果都一样 → 只分析一次（稳定失败）
        2. 如果重试结果不一样 → 分析变化模式（flaky）
        3. 如果部分成功部分失败 → 重点分析不稳定原因
        """
        
        sql = getattr(test_case, 'sql', 'Unknown SQL')
        test_id = getattr(test_case, 'id', 'unknown')
        
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
            attempts.append(attempt_info)
        
        # 判断错误模式
        unique_errors = set(errors)
        error_count = len(unique_errors)
        
        # 根据模式选择不同的prompt
        if error_count == 0:
            # 所有尝试都成功（不应该调用此函数）
            return "所有重试都成功了，无需分析"
            
        elif error_count == 1:
            # 所有错误都一样 - 稳定失败
            prompt = self._build_stable_failure_prompt(test_id, sql, attempts, list(unique_errors)[0])
            
        elif error_count > 1:
            # 错误在变化 - flaky test
            prompt = self._build_flaky_failure_prompt(test_id, sql, attempts, list(unique_errors))
        
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

    def _build_stable_failure_prompt(self, test_id, sql, attempts, error_pattern):
        """构建稳定失败的prompt - 只分析一次"""
        
        attempts_summary = "\n".join([
            f"尝试 {a['attempt']}: {a['status']} ({a['duration']})"
            for a in attempts
        ])
        
        return f"""You are a TiDB database expert. Analyze this stable test failure (same error in all retries).

    Test Information:
    - Test ID: {test_id}
    - SQL: {sql[:300]}
    - Retry attempts: {len(attempts)}

    Execution History:
    {attempts_summary}

    Error Pattern (consistent):
    {error_pattern}

    Please provide in Chinese:
    1. Root cause of this consistent failure
    2. Fix suggestion
    3. Prevention tip

    Keep response concise."""

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