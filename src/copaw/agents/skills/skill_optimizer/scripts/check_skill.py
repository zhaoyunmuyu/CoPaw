#!/usr/bin/env python3
"""Skill规范检查工具。

检查SKILL.md文件是否符合规范，生成优化建议。

用法:
    python check_skill.py --skill batch_api
    python check_skill.py --all
    python check_skill.py --skill pdf --report
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CheckResult:
    """检查结果。"""
    passed: bool
    message: str
    severity: str  # "error", "warning", "info"
    suggestion: str = ""


@dataclass
class SkillReport:
    """Skill检查报告。"""
    skill_name: str
    skill_path: str
    results: List[CheckResult] = field(default_factory=list)
    score: int = 0
    max_score: int = 100

    @property
    def passed(self) -> bool:
        return all(r.passed or r.severity != "error" for r in self.results)

    @property
    def errors(self) -> List[CheckResult]:
        return [r for r in self.results if r.severity == "error"]

    @property
    def warnings(self) -> List[CheckResult]:
        return [r for r in self.results if r.severity == "warning"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "skill_path": self.skill_path,
            "passed": self.passed,
            "score": self.score,
            "max_score": self.max_score,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "results": [
                {
                    "passed": r.passed,
                    "message": r.message,
                    "severity": r.severity,
                    "suggestion": r.suggestion,
                }
                for r in self.results
            ],
        }


def parse_frontmatter(content: str) -> tuple:
    """解析YAML Front Matter（简单实现）。"""
    fm = {}
    body = content

    # 匹配 --- 包裹的YAML front matter
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if match:
        yaml_str = match.group(1)
        body = match.group(2)

        # 简单解析YAML字段
        for line in yaml_str.split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                # 去除引号
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                fm[key] = value

    return fm, body


class SkillChecker:
    """Skill规范检查器。"""

    # 检查项权重
    WEIGHTS = {
        "yaml_name": 15,
        "yaml_description": 15,
        "description_triggers": 10,
        "section_overview": 10,
        "section_scenarios": 10,
        "section_quickstart": 10,
        "code_examples": 10,
        "section_faq": 5,
        "language_consistent": 5,
        "structure_clear": 10,
    }

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir

    def check_all(self) -> List[SkillReport]:
        """检查所有skill。"""
        reports = []
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    report = self.check_skill(skill_file)
                    reports.append(report)
        return reports

    def check_skill(self, skill_path: Path) -> SkillReport:
        """检查单个skill。"""
        skill_name = skill_path.parent.name
        report = SkillReport(skill_name=skill_name, skill_path=str(skill_path))

        try:
            with open(skill_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析frontmatter
            try:
                fm, body = parse_frontmatter(content)
            except Exception as e:
                report.results.append(CheckResult(
                    passed=False,
                    message=f"YAML Front Matter解析失败: {e}",
                    severity="error",
                    suggestion="检查YAML格式是否正确",
                ))
                return report

            # 1. 检查name字段
            report.results.append(self._check_name(fm))

            # 2. 检查description字段
            report.results.append(self._check_description(fm))

            # 3. 检查触发条件
            report.results.append(self._check_triggers(fm))

            # 4. 检查概述章节
            report.results.append(self._check_section(body, "概述", ["overview", "简介", "介绍"]))

            # 5. 检查适用场景章节
            report.results.append(self._check_section(body, "适用场景", ["场景", "使用场景", "when to use"]))

            # 6. 检查快速开始章节
            report.results.append(self._check_section(body, "快速开始", ["quick start", "快速入门", "开始使用"]))

            # 7. 检查代码示例
            report.results.append(self._check_code_examples(body))

            # 8. 检查常见问题
            report.results.append(self._check_section(body, "常见问题", ["faq", "问题", "troubleshooting"]))

            # 9. 检查语言一致性
            report.results.append(self._check_language(body))

            # 10. 检查结构清晰度
            report.results.append(self._check_structure(body))

            # 计算分数
            report.score = sum(
                self.WEIGHTS.get(r.message.split(":")[0].strip(), 0)
                for r in report.results
                if r.passed
            )

        except Exception as e:
            report.results.append(CheckResult(
                passed=False,
                message=f"检查失败: {e}",
                severity="error",
            ))

        return report

    def _check_name(self, fm: Dict[str, Any]) -> CheckResult:
        """检查name字段。"""
        if "name" not in fm:
            return CheckResult(
                passed=False,
                message="yaml_name: 缺少name字段",
                severity="error",
                suggestion="在YAML Front Matter中添加name字段",
            )
        name = fm["name"]
        if not name or not isinstance(name, str):
            return CheckResult(
                passed=False,
                message="yaml_name: name字段为空或格式错误",
                severity="error",
                suggestion="name应该是非空字符串",
            )
        return CheckResult(passed=True, message="yaml_name: OK", severity="info")

    def _check_description(self, fm: Dict[str, Any]) -> CheckResult:
        """检查description字段。"""
        if "description" not in fm:
            return CheckResult(
                passed=False,
                message="yaml_description: 缺少description字段",
                severity="error",
                suggestion="在YAML Front Matter中添加description字段",
            )
        desc = fm["description"]
        if not desc or not isinstance(desc, str):
            return CheckResult(
                passed=False,
                message="yaml_description: description字段为空或格式错误",
                severity="error",
                suggestion="description应该是非空字符串",
            )
        if len(desc) < 20:
            return CheckResult(
                passed=False,
                message="yaml_description: description太短",
                severity="warning",
                suggestion="description应该详细说明功能和触发条件",
            )
        return CheckResult(passed=True, message="yaml_description: OK", severity="info")

    def _check_triggers(self, fm: Dict[str, Any]) -> CheckResult:
        """检查触发条件。"""
        desc = fm.get("description", "")
        trigger_keywords = ["触发", "trigger", "当用户", "用户说", "用户提到"]

        has_triggers = any(kw in desc.lower() for kw in trigger_keywords)
        if not has_triggers:
            return CheckResult(
                passed=False,
                message="description_triggers: description缺少触发条件",
                severity="warning",
                suggestion="在description末尾添加'触发条件：用户提到...'",
            )
        return CheckResult(passed=True, message="description_triggers: OK", severity="info")

    def _check_section(self, body: str, section_name: str, aliases: List[str]) -> CheckResult:
        """检查章节是否存在。"""
        all_names = [section_name] + aliases
        pattern = r"^##\s+(" + "|".join(re.escape(n) for n in all_names) + r")"
        if re.search(pattern, body, re.MULTILINE | re.IGNORECASE):
            return CheckResult(
                passed=True,
                message=f"section_{section_name}: OK",
                severity="info",
            )
        return CheckResult(
            passed=False,
            message=f"section_{section_name}: 缺少'{section_name}'章节",
            severity="warning",
            suggestion=f"添加'## {section_name}'章节",
        )

    def _check_code_examples(self, body: str) -> CheckResult:
        """检查代码示例。"""
        # 检查代码块
        code_blocks = re.findall(r"```", body)
        if len(code_blocks) >= 2:  # 至少有一个完整的代码块
            return CheckResult(
                passed=True,
                message="code_examples: OK",
                severity="info",
            )
        return CheckResult(
            passed=False,
            message="code_examples: 缺少代码或命令示例",
            severity="warning",
            suggestion="添加代码块或命令示例，使用```包裹",
        )

    def _check_language(self, body: str) -> CheckResult:
        """检查语言一致性。"""
        # 简单的中英文检测
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", body))
        english_words = len(re.findall(r"[a-zA-Z]+", body))

        if chinese_chars > 0 and english_words > chinese_chars * 2:
            return CheckResult(
                passed=False,
                message="language_consistent: 语言可能不一致",
                severity="info",
                suggestion="建议统一使用中文或英文",
            )
        return CheckResult(passed=True, message="language_consistent: OK", severity="info")

    def _check_structure(self, body: str) -> CheckResult:
        """检查结构清晰度。"""
        headers = re.findall(r"^##\s+", body, re.MULTILINE)
        if len(headers) >= 3:
            return CheckResult(
                passed=True,
                message="structure_clear: OK",
                severity="info",
            )
        return CheckResult(
            passed=False,
            message="structure_clear: 结构不够清晰",
            severity="warning",
            suggestion="建议添加更多章节，如'概述'、'适用场景'、'快速开始'等",
        )


def print_report(report: SkillReport, detailed: bool = False):
    """打印报告。"""
    print(f"\n{'='*60}")
    print(f"Skill: {report.skill_name}")
    print(f"路径: {report.skill_path}")
    print(f"分数: {report.score}/{report.max_score}")
    print(f"状态: {'✅ 通过' if report.passed else '❌ 不通过'}")
    print(f"{'='*60}")

    if report.errors:
        print("\n❌ 错误:")
        for r in report.errors:
            print(f"  - {r.message}")
            if r.suggestion:
                print(f"    💡 {r.suggestion}")

    if report.warnings:
        print("\n⚠️ 警告:")
        for r in report.warnings:
            print(f"  - {r.message}")
            if r.suggestion:
                print(f"    💡 {r.suggestion}")

    if detailed:
        print("\n📋 详细检查结果:")
        for r in report.results:
            status = "✅" if r.passed else "❌"
            print(f"  {status} {r.message}")


def main():
    parser = argparse.ArgumentParser(
        description="Skill规范检查工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--skill", "-s",
        help="指定要检查的skill名称",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="检查所有skill",
    )
    parser.add_argument(
        "--report", "-r",
        action="store_true",
        help="生成详细报告",
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="输出JSON格式",
    )
    parser.add_argument(
        "--skills-dir",
        default=None,
        help="Skills目录路径（默认自动检测）",
    )

    args = parser.parse_args()

    # 确定skills目录
    if args.skills_dir:
        skills_dir = Path(args.skills_dir)
    else:
        # 自动检测：scripts/check_skill.py -> skill_optimizer -> skills
        script_dir = Path(__file__).parent
        skills_dir = script_dir.parent.parent  # scripts/../.. = skills目录

    if not skills_dir.exists():
        print(f"错误: Skills目录不存在: {skills_dir}", file=sys.stderr)
        sys.exit(1)

    checker = SkillChecker(skills_dir)

    if args.all:
        reports = checker.check_all()
        if args.json:
            print(json.dumps([r.to_dict() for r in reports], ensure_ascii=False, indent=2))
        else:
            for report in reports:
                print_report(report, detailed=args.report)
            print(f"\n总计: {len(reports)} 个skill, {sum(1 for r in reports if r.passed)} 个通过")
    elif args.skill:
        skill_path = skills_dir / args.skill / "SKILL.md"
        if not skill_path.exists():
            print(f"错误: Skill不存在: {skill_path}", file=sys.stderr)
            sys.exit(1)
        report = checker.check_skill(skill_path)
        if args.json:
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        else:
            print_report(report, detailed=True)
    else:
        print("请指定 --skill 或 --all", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()