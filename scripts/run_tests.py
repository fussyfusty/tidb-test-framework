#!/usr/bin/env python3
"""
TiDB Test Framework Executor
Run tests against TiDB with various options.
"""

import sys
import os
import argparse
import yaml
import logging
import time
from pathlib import Path
from typing import List, Dict, Optional

# Add project root to path
# sys.path.insert(0, str(Path(__file__).parent.parent))

from tidb_test.connector import TiDBConnection, ConnectionConfig
from tidb_test.loader.factory import LoaderFactory
from tidb_test.executor.sql_executor import SQLExecutor
from tidb_test.models.test_case import TestCase
from tidb_test.models.test_result import TestStatus
from tidb_test.utils import setup_logger, format_timestamp
from tidb_test.exceptions import TiDBTestError
from tidb_test.reporter import ConsoleReporter, JSONReporter


class TestRunner:
    """Main test runner orchestrating loading, execution, and reporting."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.logger = setup_logger("tidb-runner")
        self.loader_factory = LoaderFactory()
        self.console_reporter = ConsoleReporter()
        self.json_reporter = JSONReporter()
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file."""
        config_file = Path(config_path)
        if not config_file.exists():
            self.logger.warning(f"Config file {config_path} not found, using defaults")
            return {
                'versions': {
                    'v7.5.0': {'host': 'localhost', 'port': 4000, 'user': 'root'}
                }
            }
        
        with open(config_file) as f:
            return yaml.safe_load(f)
    
    def _get_version_config(self, version: str) -> Dict:
        """Get connection config for a version."""
        versions = self.config.get('versions', {})
        if version in versions:
            return versions[version]
        
        # Try to find by alias
        for v, config in versions.items():
            if version in config.get('aliases', []):
                return config
        
        self.logger.warning(f"Version {version} not found in config, using default")
        return {'host': 'localhost', 'port': 4000, 'user': 'root'}
    
    def _create_connection(self, version: str) -> TiDBConnection:
        """Create connection for a version."""
        config_dict = self._get_version_config(version)
        config = ConnectionConfig.from_dict(config_dict)
        return TiDBConnection(config)
    
    def load_tests(self, args) -> List[TestCase]:
        """Load tests based on command line arguments.
        
        支持分级过滤：
        1. 先按 --file/--type/--tag 确定测试源
        2. 再按 --test-id 精确过滤
        """
        tests = []
        
        # 第一级：确定测试源
        if args.file:
            # 从单个文件加载
            file_path = Path(args.file)
            if not file_path.exists():
                self.logger.error(f"File not found: {file_path}")
                return []
            tests = self.loader_factory.load_file(file_path)
            source_desc = f"file {args.file}"
            
        elif args.type:
            # 从类别目录加载
            test_dir = Path("tests") / args.type
            if not test_dir.exists():
                self.logger.error(f"Test category not found: {test_dir}")
                return []
            tests = self.loader_factory.load_directory(test_dir)
            source_desc = f"category '{args.type}'"
            
        # elif args.tag:
        #     # 按标签加载（跨文件）
        #     all_tests = self.loader_factory.load_directory(Path("tests"))
        #     tests = [t for t in all_tests if any(tag in t.tags for tag in args.tag)]
        #     source_desc = f"tags {args.tag}"
        elif args.tag:
            # 按标签加载（跨文件）
            self.logger.info(f"Loading tests with tags: {args.tag}")

            # TODO 对python格式的特殊处理简化版
            if args.tag == ['chaos']:  # 如果是 chaos 标签，直接用 pytest
                import pytest
                self.logger.info("Running chaos tests with pytest...")
                pytest.main(['tests/extensions/chaos/', '-v'])
                return []  # 返回空，因为 pytest 已经执行了
            
            # 只加载指定的测试目录，不递归
            test_dirs = [
                Path("tests/basic"),
                Path("tests/tidb_features"),
                Path("tests/regression"),
                Path("tests/extensions/chaos"),  # 直接加载 chaos 目录
            ]
            
            all_tests = []
            for test_dir in test_dirs:
                if test_dir.exists():
                    tests_in_dir = self.loader_factory.load_directory(test_dir, recursive=False)
                    self.logger.info(f"Loaded {len(tests_in_dir)} tests from {test_dir}")
                    all_tests.extend(tests_in_dir)
            
            # 过滤标签
            tests = []
            for t in all_tests:
                if t.tags:
                    # 将 tags 转换为集合便于比较
                    test_tags = set(t.tags) if not isinstance(t.tags, set) else t.tags
                    if any(tag in test_tags for tag in args.tag):
                        tests.append(t)
                        self.logger.debug(f"✅ Test {t.id} matched with tags {t.tags}")
            
            self.logger.info(f"Found {len(tests)} tests with tags {args.tag}")
            source_desc = f"tags {args.tag}"
            
        else:
            self.logger.error("No test source specified. Use --file, --type, or --tag")
            return []
        
        self.logger.info(f"Loaded {len(tests)} tests from {source_desc}")
        
        # 第二级：按 test_id 精确过滤（如果指定）
        if args.test_id:
            # 支持多个 test_id（逗号分隔）
            test_ids = [tid.strip() for tid in args.test_id.split(',')]
            
            filtered = [t for t in tests if t.id in test_ids]
            
            if not filtered:
                # 显示可用的 ID 样例
                sample_ids = [t.id for t in tests[:10]]
                self.logger.error(f"None of the specified test IDs {test_ids} found in {source_desc}")
                self.logger.info(f"Sample available IDs: {sample_ids}...")
                return []
            
            # 检查哪些 ID 没找到
            found_ids = [t.id for t in filtered]
            missing = set(test_ids) - set(found_ids)
            if missing:
                self.logger.warning(f"Test IDs not found: {missing}")
            
            tests = filtered
            self.logger.info(f"Filtered to {len(tests)} tests with IDs: {found_ids}")
        
        return tests
    
    def run_tests(self, tests: List[TestCase], versions: List[str], args) -> Dict:
        """Run tests against specified versions."""
        results = {}
        
        # 检查是否启用 AI
        enable_ai = getattr(args, 'enable_ai', False)
        
        for version in versions:
            self.logger.info(f"\n🚀 Testing against TiDB {version}")
            
            try:
                # Create connection
                conn = self._create_connection(version)
                conn.connect()
                self.logger.info(f"Connected to {conn.get_server_version()}")
                
                # Create AI analyzer if enabled
                ai_analyzer = None
                ai_fixer = None
                if enable_ai:
                    try:
                        from tidb_test.ai import AIFailureAnalyzer, AIFixer
                        api_key = os.getenv("AI_API_KEY")
                        if api_key:
                            ai_analyzer = AIFailureAnalyzer(api_key=api_key)
                            ai_fixer = AIFixer(api_key=api_key)
                            self.logger.info("🤖 AI analysis enabled")
                        else:
                            self.logger.warning("AI_API_KEY not set, AI analysis disabled")
                    except Exception as e:
                        self.logger.warning(f"Failed to initialize AI analyzer: {e}")
                
                # Create executor with AI analyzer
                executor = SQLExecutor(conn, ai_analyzer=ai_analyzer, ai_fixer=ai_fixer) 
                
                
                # Execute tests
                version_results = []
                for test in tests:
                    if test.should_skip_version(version):
                        self.logger.debug(f"Skipping {test.id} (incompatible with {version})")
                        continue
                    
                    result = executor.execute(test, version)
                    version_results.append(result)
                    
                    # Print progress
                    status = "✅" if result.status == TestStatus.PASSED else "❌"
                    self.logger.info(f"  {status} {test.id} ({result.duration:.2f}s)")
                    
                    if result.status != TestStatus.PASSED and result.ai_analysis:
                        self.logger.info(f"     🤖 AI: {result.ai_analysis}")
                
                results[version] = version_results
                conn.close()
                
            except Exception as e:
                self.logger.error(f"Failed to test version {version}: {e}")
                results[version] = []
        
        return results
    
    def generate_report(self, results: Dict, output_format: str = "console", report_file: Optional[str] = None):
        """Generate test report."""
        if output_format == "console":
            self.console_reporter.generate(results)
        elif output_format == "json":
            self.json_reporter.generate(results, report_file)
        else:
            self.logger.warning(f"Unsupported format: {output_format}")
    
    # def _console_report(self, results: Dict):
    #     """Generate console report with fix suggestions."""
    #     print("\n" + "="*80)
    #     print("📊 TEST EXECUTION REPORT")
    #     print("="*80)
        
    #     all_fixes = []  # 收集所有修复
        
    #     for version, version_results in results.items():
    #         print(f"\n📌 Version: {version}")
    #         print("-" * 40)
            
    #         passed = sum(1 for r in version_results if r.status == TestStatus.PASSED)
    #         failed = sum(1 for r in version_results if r.status == TestStatus.FAILED)
            
    #         print(f"  Passed: {passed}")
    #         print(f"  Failed: {failed}")
    #         print(f"  Total:  {len(version_results)}")
            
    #         # 显示失败详情和AI分析
    #         if failed > 0:
    #             print("\n  ❌ Failures with AI Analysis:")
    #             for r in version_results:
    #                 if r.status == TestStatus.FAILED:
    #                     print(f"    - {r.test_id}: {r.error_msg}")
    #                     if r.ai_analysis:
    #                         print(f"      🤖 AI: {r.ai_analysis}")
                        
    #                     # 显示生成的修复（单个Dict）
    #                     if hasattr(r, 'fix_generated') and r.fix_generated:
    #                         fix = r.fix_generated
    #                         print(f"      🔧 AI-generated fix:")
    #                         print(f"         Explanation: {fix['explanation']}")
    #                         print(f"         Confidence: {fix['confidence']}")
    #                         print(f"         Saved to: {fix['new_file_path']}")
    #                         if fix.get('run_command'):
    #                             print(f"         Run: {fix['run_command']}")
    #                         if fix.get('diff'):
    #                             print(f"         Diff:\n{fix['diff']}")
    #                         all_fixes.append(fix)
    #                     print()
        
    #     # 汇总所有生成的修复
    #     if all_fixes:
    #         print("\n" + "="*80)
    #         print("🔧 AI-GENERATED TEST FIXES SUMMARY")
    #         print("="*80)
    #         for fix in all_fixes:
    #             print(f"\n📝 {fix['test_id']} -> {Path(fix['new_file_path']).name}")
    #             print(f"   {fix['explanation']}")
    #             print(f"   Run: {fix.get('run_command', 'N/A')}")
        
    #     print("\n" + "="*80)
    #     total_passed = sum(r.status == TestStatus.PASSED for vr in results.values() for r in vr)
    #     total_tests = sum(len(vr) for vr in results.values())
    #     print(f"SUMMARY: {total_passed}/{total_tests} passed")
    #     if all_fixes:
    #         print(f"🔧 Generated {len(all_fixes)} fixed test cases")
    #     print("="*80)
    
    # def _json_report(self, results: Dict, report_file: Optional[str] = None):
    #     """Generate JSON report with fix information."""
    #     import json
    #     from datetime import datetime, date
    #     from pathlib import Path
        
    #     # 自定义 JSON 编码器
    #     class CustomJSONEncoder(json.JSONEncoder):
    #         def default(self, obj):
    #             if isinstance(obj, (date, datetime)):
    #                 return obj.isoformat()
    #             if isinstance(obj, TestStatus):
    #                 return obj.value
    #             try:
    #                 return super().default(obj)
    #             except TypeError:
    #                 return str(obj)
        
    #     # 构建报告数据
    #     report = {
    #         "timestamp": datetime.now().isoformat(),
    #         "summary": {
    #             "total": 0,
    #             "passed": 0,
    #             "failed": 0,
    #             "errors": 0
    #         },
    #         "results": {},
    #         "ai_analyses": [],
    #         "generated_fixes": []  # 新增：记录所有生成的修复
    #     }
        
    #     # 填充数据
    #     for version, version_results in results.items():
    #         report["results"][version] = []
    #         for r in version_results:
    #             result_dict = r.to_dict()
                
    #             # 确保 fix_generated 被包含在 result_dict 中
    #             if hasattr(r, 'fix_generated') and r.fix_generated:
    #                 result_dict['fix_generated'] = r.fix_generated
    #                 # 同时添加到总的 fixes 列表
    #                 report["generated_fixes"].append({
    #                     "test_id": r.test_id,
    #                     "version": version,
    #                     "fix": r.fix_generated
    #                 })
                
    #             report["results"][version].append(result_dict)
                
    #             # 收集AI分析
    #             if result_dict.get('ai_analysis'):
    #                 report["ai_analyses"].append({
    #                     "test_id": result_dict['test_id'],
    #                     "version": version,
    #                     "analysis": result_dict['ai_analysis']
    #                 })
            
    #         report["summary"]["total"] += len(version_results)
    #         report["summary"]["passed"] += sum(1 for r in version_results if r.status == TestStatus.PASSED)
    #         report["summary"]["failed"] += sum(1 for r in version_results if r.status == TestStatus.FAILED)
    #         report["summary"]["errors"] += sum(1 for r in version_results if r.status == TestStatus.ERROR)
        
    #     # 打印到控制台
    #     print("\n" + "="*80)
    #     print("📊 JSON REPORT")
    #     print("="*80)
    #     print(json.dumps(report, indent=2, ensure_ascii=False, cls=CustomJSONEncoder))
        
    #     # 写入文件
    #     if report_file:
    #         try:
    #             file_path = Path(report_file)
    #             file_path.parent.mkdir(parents=True, exist_ok=True)
                
    #             with open(file_path, 'w', encoding='utf-8') as f:
    #                 json.dump(report, f, indent=2, ensure_ascii=False, cls=CustomJSONEncoder)
    #             self.logger.info(f"✅ JSON report saved to {report_file}")
    #         except Exception as e:
    #             self.logger.error(f"❌ Failed to save report to {report_file}: {e}")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="TiDB Test Framework Executor")
    
    # Test selection (mutually exclusive)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--type", help="Test category (basic, tidb_features, regression)")
    group.add_argument("--file", help="Single test file to run")
    group.add_argument("--tag", action="append", help="Run tests with specific tags")
    # group.add_argument("--test-id", help="Run specific test by ID")
    
    # Version selection
    parser.add_argument("--version", action="append", help="TiDB version to test")
    parser.add_argument("--versions", help="Comma-separated versions")
    parser.add_argument("--all-versions", action="store_true", help="Test all configured versions")
    
    # Execution options
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--output", choices=["console", "json"], default="console", help="Output format")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--report-file", help="Output file for report (required for json output)")
    
    # Enable AI
    parser.add_argument("--enable-ai", action="store_true", help="Enable AI failure analysis")
    
    # Test ID selection
    parser.add_argument("--test-id", help="Run specific test by ID")

    return parser.parse_args()


def main():
    """Main entry point."""
    print("="*60)
    print("🚀 TiDB AI-Assisted Testing Framework (MVP)")
    print("="*60)
    print("✅ Core flow: Loader → Executor → AI → Reporter")
    print("⚠️  Placeholder modules: scheduler, parser, HTML/JUnit reporters")
    print("📌 For full implementation status, see README.md")
    print("="*60)

    args = parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    
    # Create runner
    runner = TestRunner(args.config)
    
    # Load tests
    tests = runner.load_tests(args)
    if not tests:
        print("❌ No tests loaded")
        return 1
    
    # Determine versions to test
    versions = []
    if args.version:
        versions = args.version
    elif args.versions:
        versions = args.versions.split(',')
    elif args.all_versions:
        versions = list(runner.config.get('versions', {}).keys())
    else:
        versions = ["v7.5.0"]  # Default
    
    # Run tests
    start_time = time.time()
    results = runner.run_tests(tests, versions, args)
    duration = time.time() - start_time
    
    # Generate report
    runner.generate_report(results, args.output, args.report_file)
    
    print(f"\n⏱️  Total execution time: {duration:.2f}s")
    
    # Return exit code
    total_failed = sum(
        sum(1 for r in version_results if r.status == TestStatus.FAILED)
        for version_results in results.values()
    )
    
    return 1 if total_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())