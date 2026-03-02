"""AI-powered test case fixer - generates corrected test cases."""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import difflib

from openai import OpenAI


class AIFixer:
    """Generate fixed versions of failed test cases."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat"):
        self.api_key = api_key or os.getenv("AI_API_KEY")
        self.model = model
        self.logger = logging.getLogger(__name__)
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com/v1",
            timeout=30.0
        )
    
    def generate_fix(self, test_case, error: Dict[str, Any], attempt_history: list) -> Dict[str, Any]:
        """Generate a fixed version of the test case.
        
        Returns:
            Dict with:
            - fixed_sql: 修正后的SQL
            - explanation: 修改说明
            - confidence: 置信度
            - new_file_path: 保存路径
            - diff: 与原文件的diff
        """
        sql = getattr(test_case, 'sql', 'Unknown SQL')
        test_id = getattr(test_case, 'id', 'unknown')
        file_path = getattr(test_case, 'file_path', 'unknown')
        
        prompt = f"""You are a TiDB database expert. Fix this failing test case.

Original Test:
- Test ID: {test_id}
- SQL: {sql}
- Error: {error.get('message', '')}
- Error Code: {error.get('code', 'unknown')}

Retry History:
{self._format_history(attempt_history)}

Please provide:
1. FIXED_SQL: The corrected SQL statement that should pass
2. EXPLANATION: What was wrong and how you fixed it (1-2 sentences)
3. CONFIDENCE: High/Medium/Low based on certainty

Format your response exactly as:

FIXED_SQL:
[the corrected SQL]

EXPLANATION:
[your explanation]

CONFIDENCE:
[High/Medium/Low]
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            result = self._parse_response(response.choices[0].message.content)
            
            # 生成diff
            diff = self._generate_diff(sql, result['fixed_sql'])
            
            # 生成新文件路径
            new_path = self._generate_file_path(file_path, test_id)
            
            return {
                'fixed_sql': result['fixed_sql'],
                'explanation': result['explanation'],
                'confidence': result['confidence'],
                'diff': diff,
                'new_file_path': str(new_path),
                'original_sql': sql,
                'test_id': test_id
            }
            
        except Exception as e:
            self.logger.error(f"AI fix generation failed: {e}")
            return None
    
    def _format_history(self, history: list) -> str:
        """Format attempt history for prompt."""
        if not history:
            return "No retry history"
        
        lines = []
        for h in history:
            status = h['status']
            if status == 'error' and h.get('error'):
                lines.append(f"Attempt {h['attempt']}: {status} - {h['error'].get('message', '')}")
            else:
                lines.append(f"Attempt {h['attempt']}: {status}")
        return "\n".join(lines)
    
    def _parse_response(self, content: str) -> Dict[str, str]:
        """Parse AI response."""
        result = {
            'fixed_sql': '',
            'explanation': '',
            'confidence': 'Low'  # 默认值
        }
        
        lines = content.split('\n')
        current_section = None
        sql_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('FIXED_SQL:'):
                current_section = 'sql'
                # 如果同一行有内容，提取出来
                if len(line) > 10:
                    sql_lines.append(line[10:].strip())
            elif line.startswith('EXPLANATION:'):
                if current_section == 'sql' and sql_lines:
                    result['fixed_sql'] = '\n'.join(sql_lines).strip()
                    sql_lines = []
                current_section = 'explanation'
                # 如果同一行有内容，提取出来
                if len(line) > 12:
                    result['explanation'] += line[12:].strip() + ' '
            elif line.startswith('CONFIDENCE:'):
                current_section = 'confidence'
                # 提取 confidence 值
                confidence_val = line[11:].strip()
                if confidence_val:
                    result['confidence'] = confidence_val
                else:
                    # 如果 confidence 在下一行，会在后面的循环中处理
                    pass
            elif current_section == 'sql':
                sql_lines.append(line)
            elif current_section == 'explanation':
                result['explanation'] += line + ' '
            elif current_section == 'confidence' and line:
                # 处理 confidence 值在下一行的情况
                result['confidence'] = line
        
        # 确保所有数据都被捕获
        if current_section == 'sql' and sql_lines:
            result['fixed_sql'] = '\n'.join(sql_lines).strip()
        
        result['explanation'] = result['explanation'].strip()
        
        return result
    
    def _generate_diff(self, original: str, fixed: str) -> str:
        """Generate unified diff between original and fixed SQL."""
        original_lines = original.splitlines(keepends=True)
        fixed_lines = fixed.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines, fixed_lines,
            fromfile='original.sql',
            tofile='fixed.sql',
            n=3
        )
        return ''.join(diff)
    
    def _generate_file_path(self, original_path: Path, test_id: str) -> Path:
        """Generate path for fixed test case."""
        # 创建 ai_generated 目录
        base_dir = Path('tests/ai_generated/basic')
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名：原文件名_fixed_时间戳.test
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_filename = f"{test_id}_fixed_{timestamp}.test"
        
        return base_dir / new_filename
    
    def save_fixed_test(self, fix_result: Dict[str, Any]) -> bool:
        """Save fixed test case to file."""
        try:
            file_path = Path(fix_result['new_file_path'])
            
            # 生成测试文件内容
            content = f"""# AI-Generated Fix for {fix_result['test_id']}
# Generated at: {datetime.now().isoformat()}
# Original SQL: {fix_result['original_sql']}
# Fix explanation: {fix_result['explanation']}
# AI Confidence: {fix_result['confidence']}

# Fixed test case
statement ok
{fix_result['fixed_sql']}

# Original failing test (commented out)
# statement error
# {fix_result['original_sql']}
"""
            
            file_path.write_text(content, encoding='utf-8')
            self.logger.info(f"✅ Fixed test saved to {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save fixed test: {e}")
            return False
    
    def get_run_command(self, file_path: Path) -> str:
        """Generate command to run the fixed test."""
        return f"python scripts/run_tests.py --file {file_path} --enable-ai"
