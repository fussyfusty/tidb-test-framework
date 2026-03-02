# tidb_test/reporter/console_reporter.py
"""
Console reporter for real-time test output.
"""

from pathlib import Path
from typing import Dict
from tidb_test.models.test_result import TestStatus


class ConsoleReporter:
    """Generate console test reports."""
    
    def generate(self, results: Dict):
        """Generate console report."""
        print("\n" + "="*80)
        print("📊 TEST EXECUTION REPORT")
        print("="*80)
        
        all_fixes = []
        
        for version, version_results in results.items():
            print(f"\n📌 Version: {version}")
            print("-" * 40)
            
            passed = sum(1 for r in version_results if r.status == TestStatus.PASSED)
            failed = sum(1 for r in version_results if r.status == TestStatus.FAILED)
            
            print(f"  Passed: {passed}")
            print(f"  Failed: {failed}")
            print(f"  Total:  {len(version_results)}")
            
            if failed > 0:
                print("\n  ❌ Failures with AI Analysis:")
                for r in version_results:
                    if r.status == TestStatus.FAILED:
                        print(f"    - {r.test_id}: {r.error_msg}")
                        if r.ai_analysis:
                            print(f"      🤖 AI: {r.ai_analysis}")
                        
                        if hasattr(r, 'fix_generated') and r.fix_generated:
                            fix = r.fix_generated
                            print(f"      🔧 AI-generated fix:")
                            print(f"         Explanation: {fix['explanation']}")
                            print(f"         Confidence: {fix['confidence']}")
                            print(f"         Saved to: {fix['new_file_path']}")
                            if fix.get('run_command'):
                                print(f"         Run: {fix['run_command']}")
                            if fix.get('diff'):
                                print(f"         Diff:\n{fix['diff']}")
                            all_fixes.append(fix)
                        print()
        
        if all_fixes:
            print("\n" + "="*80)
            print("🔧 AI-GENERATED TEST FIXES SUMMARY")
            print("="*80)
            for fix in all_fixes:
                print(f"\n📝 {fix['test_id']} -> {Path(fix['new_file_path']).name}")
                print(f"   {fix['explanation']}")
                print(f"   Run: {fix.get('run_command', 'N/A')}")
        
        print("\n" + "="*80)
        total_passed = sum(r.status == TestStatus.PASSED for vr in results.values() for r in vr)
        total_tests = sum(len(vr) for vr in results.values())
        print(f"SUMMARY: {total_passed}/{total_tests} passed")
        if all_fixes:
            print(f"🔧 Generated {len(all_fixes)} fixed test cases")
        print("="*80)
        