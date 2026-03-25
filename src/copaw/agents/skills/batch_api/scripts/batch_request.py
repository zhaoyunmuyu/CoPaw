#!/usr/bin/env python3
"""批量API请求执行器。

根据输入数据文件和配置执行多个API请求。
支持进度追踪、错误恢复和结果聚合。

用法:
    python batch_request.py --config config.json --input input.json --output results.json
    python batch_request.py --config config.json --input input.json --output results.json --resume
"""

import argparse
import asyncio
import csv
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """批量请求配置。"""
    base_url: str
    endpoint: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    request_body: Optional[Dict[str, Any]] = None
    url_params: Dict[str, str] = field(default_factory=dict)
    response_data_path: str = "$"
    id_field: str = "id"
    timeout: float = 30.0
    retry_count: int = 3
    retry_delay: float = 1.0
    concurrency: int = 1
    delay_between_requests: float = 0.0


@dataclass
class Progress:
    """进度追踪状态。"""
    processed_ids: List[str] = field(default_factory=list)
    last_index: int = 0
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "processed_ids": self.processed_ids,
            "last_index": self.last_index,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Progress":
        return cls(
            processed_ids=data.get("processed_ids", []),
            last_index=data.get("last_index", 0),
            timestamp=data.get("timestamp", ""),
        )


def load_config(config_path: Path) -> Config:
    """从JSON文件加载配置。"""
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Config(**data)


def load_input(input_path: Path) -> List[Dict[str, Any]]:
    """从JSON或CSV文件加载输入数据。"""
    suffix = input_path.suffix.lower()

    if suffix == ".json":
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        raise ValueError("JSON input must be a list or contain a 'data' key")

    elif suffix == ".csv":
        items = []
        with open(input_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                items.append(dict(row))
        return items

    else:
        raise ValueError(f"Unsupported input format: {suffix}")


def substitute_template(template: str, data: Dict[str, Any]) -> str:
    """替换{字段}占位符为数据值。"""
    def replacer(match):
        field_name = match.group(1)
        value = data.get(field_name, "")
        return str(value)

    return re.sub(r"\{(\w+)\}", replacer, template)


def substitute_dict(template: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
    """递归替换字典中的占位符。"""
    result = {}
    for key, value in template.items():
        if isinstance(value, str):
            result[key] = substitute_template(value, data)
        elif isinstance(value, dict):
            result[key] = substitute_dict(value, data)
        elif isinstance(value, list):
            result[key] = [
                substitute_template(item, data) if isinstance(item, str) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def extract_jsonpath(data: Any, path: str) -> Any:
    """使用简单JSONPath提取数据（以$开头，点号分隔）。"""
    if path == "$":
        return data

    parts = path.lstrip("$.").split(".")
    result = data
    for part in parts:
        if not part:
            continue
        if isinstance(result, dict):
            result = result.get(part)
        elif isinstance(result, list) and part.isdigit():
            result = result[int(part)]
        else:
            return None
    return result


async def make_request(
    client: httpx.AsyncClient,
    config: Config,
    item: Dict[str, Any],
) -> Dict[str, Any]:
    """执行单个API请求，带重试逻辑。"""
    # 构建URL
    endpoint = substitute_template(config.endpoint, item)
    url = f"{config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    # 构建请求头
    headers = substitute_dict(config.headers, item) if config.headers else {}

    # 构建URL参数
    params = substitute_dict(config.url_params, item) if config.url_params else None

    # 构建请求体
    body = None
    if config.request_body and config.method in ("POST", "PUT", "PATCH"):
        body = substitute_dict(config.request_body, item)

    # 重试循环
    last_error = None
    for attempt in range(config.retry_count):
        try:
            response = await client.request(
                method=config.method,
                url=url,
                headers=headers,
                params=params,
                json=body,
                timeout=config.timeout,
            )
            response.raise_for_status()

            result_data = response.json()
            extracted = extract_jsonpath(result_data, config.response_data_path)

            return {
                "input": item,
                "output": extracted,
                "status": "success",
                "status_code": response.status_code,
            }

        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            if e.response.status_code < 500:
                break
        except httpx.RequestError as e:
            last_error = str(e)
        except json.JSONDecodeError:
            last_error = "Invalid JSON response"

        if attempt < config.retry_count - 1:
            await asyncio.sleep(config.retry_delay * (attempt + 1))

    return {
        "input": item,
        "error": last_error,
        "status": "failed",
    }


async def process_batch(
    config: Config,
    items: List[Dict[str, Any]],
    progress: Progress,
    output_path: Path,
    progress_path: Path,
    errors_path: Optional[Path],
    previous_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """处理所有项目并进行进度追踪。"""
    results = previous_results.get("results", []) if previous_results else []
    errors = previous_results.get("errors", []) if previous_results else []
    success_count = previous_results.get("success", 0) if previous_results else 0
    failed_count = previous_results.get("failed", 0) if previous_results else 0

    # 过滤已处理的项目
    processed_set = set(progress.processed_ids)
    pending_items = [
        item for item in items
        if item.get(config.id_field) not in processed_set
    ]

    if not pending_items:
        logger.info("所有项目已处理完成")
        return {
            "status": "completed",
            "total": len(items),
            "success": success_count,
            "failed": failed_count,
            "message": "所有项目已处理完成",
        }

    logger.info(f"正在处理 {len(pending_items)} 个项目（总数: {len(items)}，已完成: {len(processed_set)}）")

    start_time = datetime.now(timezone.utc)

    async with httpx.AsyncClient() as client:
        semaphore = asyncio.Semaphore(min(config.concurrency, 10))

        async def process_item(item: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                result = await make_request(client, config, item)

                if config.delay_between_requests > 0:
                    await asyncio.sleep(config.delay_between_requests)

                return result

        # 分批处理以更新进度
        batch_size = max(10, len(pending_items) // 10)

        for i in range(0, len(pending_items), batch_size):
            batch = pending_items[i:i + batch_size]
            batch_results = await asyncio.gather(*[process_item(item) for item in batch])

            for result in batch_results:
                results.append(result)
                item_id = result["input"].get(config.id_field, "")

                if result["status"] == "success":
                    success_count += 1
                else:
                    failed_count += 1
                    errors.append(result)
                    if errors_path:
                        with open(errors_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps(result, ensure_ascii=False) + "\n")

                progress.processed_ids.append(item_id)

            progress.last_index = i + len(batch)
            progress.timestamp = datetime.now(timezone.utc).isoformat()

            # 保存进度
            with open(progress_path, "w", encoding="utf-8") as f:
                json.dump(progress.to_dict(), f, ensure_ascii=False, indent=2)

            logger.info(f"进度: {len(progress.processed_ids)}/{len(items)} ({success_count} 成功, {failed_count} 失败)")

    end_time = datetime.now(timezone.utc)

    # 构建最终输出
    output = {
        "status": "completed",
        "total": len(items),
        "success": success_count,
        "failed": failed_count,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": (end_time - start_time).total_seconds(),
        "results": results,
    }

    if errors:
        output["errors"] = errors

    return output


def main():
    parser = argparse.ArgumentParser(
        description="批量API请求执行器，支持进度追踪和中断恢复",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--workdir", "-w",
        required=True,
        help="任务目录路径。config/input/output在此目录下",
    )
    parser.add_argument(
        "--config", "-c",
        help="配置文件名（默认: config.json）",
    )
    parser.add_argument(
        "--input", "-i",
        help="输入文件名，支持JSON/CSV（默认: input.json）",
    )
    parser.add_argument(
        "--output", "-o",
        help="输出文件名（默认: results.json）",
    )
    parser.add_argument(
        "--progress", "-p",
        help="进度文件名（默认: results.json.progress.json）",
    )
    parser.add_argument(
        "--errors", "-e",
        help="错误日志文件名（默认: results.json.errors.jsonl）",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="从上次进度恢复执行",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制覆盖已有输出和进度文件",
    )

    args = parser.parse_args()

    # 创建任务目录
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    # 所有文件都在workdir下
    config_path = workdir / (args.config or "config.json")
    input_path = workdir / (args.input or "input.json")
    output_path = workdir / (args.output or "results.json")
    progress_path = workdir / (args.progress or "results.json.progress.json")
    errors_path = workdir / (args.errors or "results.json.errors.jsonl")

    # 验证输入
    if not config_path.exists():
        print(f"错误: 配置文件不存在: {config_path}", file=sys.stderr)
        sys.exit(1)
    if not input_path.exists():
        print(f"错误: 输入文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    # 检查已有文件（恢复模式跳过）
    if output_path.exists() and not args.force and not args.resume:
        print(f"错误: 输出文件已存在: {output_path}。使用 --force 覆盖或 --resume 继续。", file=sys.stderr)
        sys.exit(1)

    # 加载配置和输入数据
    config = load_config(config_path)
    items = load_input(input_path)

    if not items:
        print("错误: 没有要处理的项目", file=sys.stderr)
        sys.exit(1)

    print(f"已加载 {len(items)} 个项目，来自 {input_path}")
    print(f"端点: {config.base_url}{config.endpoint}")
    print(f"方法: {config.method}")
    print(f"并发数: {config.concurrency}")

    # 加载或初始化进度
    progress = Progress()
    if args.resume and progress_path.exists():
        with open(progress_path, "r", encoding="utf-8") as f:
            progress = Progress.from_dict(json.load(f))
        print(f"从进度恢复: 已处理 {len(progress.processed_ids)} 个项目")
    elif progress_path.exists() and not args.force:
        print(f"进度文件已存在: {progress_path}。使用 --resume 继续或 --force 重新开始。", file=sys.stderr)
        sys.exit(1)

    # 新开始时清除错误文件
    if errors_path.exists() and (not args.resume or args.force):
        errors_path.unlink()

    # 恢复模式时加载之前的结果
    previous_results = None
    if args.resume and output_path.exists():
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                previous_results = json.load(f)
        except (json.JSONDecodeError, KeyError):
            pass

    # 执行批量处理
    try:
        result = asyncio.run(process_batch(
            config=config,
            items=items,
            progress=progress,
            output_path=output_path,
            progress_path=progress_path,
            errors_path=errors_path,
            previous_results=previous_results,
        ))

        # 保存最终结果
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # 成功完成后清理进度文件
        if progress_path.exists():
            progress_path.unlink()

        print(f"\n完成: {result['success']}/{result['total']} 成功")
        if result['failed'] > 0:
            print(f"失败: {result['failed']}")
            print(f"错误保存至: {errors_path}")
        print(f"结果保存至: {output_path}")

    except KeyboardInterrupt:
        print("\n已中断。进度保存至:", progress_path)
        sys.exit(130)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()