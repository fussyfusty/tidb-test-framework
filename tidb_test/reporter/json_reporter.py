# tidb_test/reporter/json_reporter.py
"""
JSON reporter for structured test results.
"""

import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Optional
from tidb_test.models.test_result import TestStatus


class JSONReporter:
    """Generate JSON test reports."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate(self, results: Dict, report_file: Optional[str] = None):
        """Generate JSON report."""
        
        class CustomJSONEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, (date, datetime)):
                    return obj.isoformat()
                if isinstance(obj, TestStatus):
                    return obj.value
                try:
                    return super().default(obj)
                except TypeError:
                    return str(obj)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0
            },
            "results": {},
            "ai_analyses": [],
            "generated_fixes": []
        }
        
        for version, version_results in results.items():
            report["results"][version] = []
            for r in version_results:
                result_dict = r.to_dict()
                
                if hasattr(r, 'fix_generated') and r.fix_generated:
                    result_dict['fix_generated'] = r.fix_generated
                    report["generated_fixes"].append({
                        "test_id": r.test_id,
                        "version": version,
                        "fix": r.fix_generated
                    })
                
                report["results"][version].append(result_dict)
                
                if result_dict.get('ai_analysis'):
                    report["ai_analyses"].append({
                        "test_id": result_dict['test_id'],
                        "version": version,
                        "analysis": result_dict['ai_analysis']
                    })
            
            report["summary"]["total"] += len(version_results)
            report["summary"]["passed"] += sum(1 for r in version_results if r.status == TestStatus.PASSED)
            report["summary"]["failed"] += sum(1 for r in version_results if r.status == TestStatus.FAILED)
            report["summary"]["errors"] += sum(1 for r in version_results if r.status == TestStatus.ERROR)
        
        # 打印到控制台
        print("\n" + "="*80)
        print("📊 JSON REPORT")
        print("="*80)
        print(json.dumps(report, indent=2, ensure_ascii=False, cls=CustomJSONEncoder))
        
        # 写入文件
        if report_file:
            try:
                file_path = Path(report_file)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, ensure_ascii=False, cls=CustomJSONEncoder)
                self.logger.info(f"✅ JSON report saved to {report_file}")
            except Exception as e:
                self.logger.error(f"❌ Failed to save report to {report_file}: {e}")
