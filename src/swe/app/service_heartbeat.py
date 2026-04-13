# -*- coding: utf-8 -*-
"""服务心跳模块：向远程接口定期发送心跳信号。

在服务启动时开启后台心跳任务，每30秒（可配置）发送一次正常心跳。
在进程结束前发送一次关闭信号（enabled=false）。

关键特性：
1. 心跳任务完全独立运行，不影响用户请求处理
2. 捕获 SIGTERM/SIGINT 信号，确保 Kubernetes 优雅关闭时发送关闭心跳
3. 使用 atexit 作为最后的兜底方案

需要配置的环境变量：
- SWE_SERVICE_HEARTBEAT_ENABLED: 是否启用（默认true）
- SWE_SERVICE_HEARTBEAT_URL: 心跳接口地址（必填）
- SWE_SERVICE_HEARTBEAT_INTERVAL: 心跳间隔秒数（默认30）
- SWE_SERVICE_HEARTBEAT_INSTANCE_PORT: 实例端口（默认8088）
- SWE_SERVICE_HEARTBEAT_WEIGHT: 权重（默认1）
- SWE_SERVICE_HEARTBEAT_SERVICE_NAME: 服务名称（默认swe）

容器自带的环境变量（自动获取，无需配置）：
- CMB_CAAS_SERVICEUNITID: 服务单元标识
- CMB_CLUSTER: 可用区标识

接口入参：
- serviceName: String, 必填, 服务名称（默认swe）
- serviceUnit: String, 可选, 服务单元标识（容器自带CMB_CAAS_SERVICEUNITID）
- az: String, 可选, 可用区标识（容器自带CMB_CLUSTER）
- instanceIp: String, 必填, 实例IP（从/etc/hosts读取）
- instancePort: Integer, 必填, 实例端口（默认8088）
- enabled: Boolean, 可选, 是否启用（正常true，关闭时false）
- weight: Integer, 可选, 权重（默认1）
"""

import asyncio
import atexit
import logging
import os
import signal
import socket
import sys
from types import FrameType
from typing import Callable, Optional

import httpx

from ..config import load_config
from ..config.config import ServiceHeartbeatConfig

logger = logging.getLogger(__name__)

# 环境变量名：服务单元标识
SERVICE_UNIT_ENV_VAR = "CMB_CAAS_SERVICEUNITID"
# 环境变量名：可用区标识
AZ_ENV_VAR = "CMB_CLUSTER"

# 关闭信号标志
_shutdown_requested = False


def _is_valid_instance_ip(ip: str) -> bool:
    """返回是否为有效的非回环 IPv4 地址。"""
    if ip in ("127.0.0.1", "::1", "localhost"):
        return False
    try:
        socket.inet_aton(ip)
    except socket.error:
        return False
    return True


def _get_instance_ip_from_hosts(
    hosts_path: str = "/etc/hosts",
) -> Optional[str]:
    """从 hosts 文件中读取第一个有效的实例 IP。"""
    if not os.path.exists(hosts_path):
        return None

    try:
        with open(hosts_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                ip = parts[0]
                if _is_valid_instance_ip(ip):
                    logger.info("从/etc/hosts获取实例IP: %s", ip)
                    return ip
    except OSError as e:
        logger.warning("读取/etc/hosts失败: %s，将尝试获取本机IP", e)

    return None


def _get_local_instance_ip() -> str:
    """获取本机 IP 作为实例 IP 的备用方案。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            logger.info("获取本机IP: %s", local_ip)
            return local_ip
    except OSError as e:
        logger.warning("获取本机IP失败: %s", e)
        return "127.0.0.1"


def get_instance_ip() -> str:
    """获取实例IP地址。

    优先从/etc/hosts文件中读取容器IP，如果失败则尝试获取本机IP。
    """
    instance_ip = _get_instance_ip_from_hosts()
    if instance_ip:
        return instance_ip
    return _get_local_instance_ip()


def get_service_unit() -> Optional[str]:
    """从环境变量获取服务单元标识。"""
    return os.environ.get(SERVICE_UNIT_ENV_VAR)


def get_az() -> Optional[str]:
    """从环境变量获取可用区标识。"""
    return os.environ.get(AZ_ENV_VAR)


def send_sync_shutdown_heartbeat(url: str, payload: dict) -> bool:
    """同步发送关闭心跳（用于信号处理和atexit）。

    Args:
        url: 心跳接口地址
        payload: 请求体（enabled=false）

    Returns:
        是否成功发送
    """
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(url, json=payload)
            if response.status_code >= 200 and response.status_code < 300:
                logger.info(
                    "同步关闭心跳发送成功: status=%d",
                    response.status_code,
                )
                return True
            logger.warning(
                "同步关闭心跳发送失败: status=%d",
                response.status_code,
            )
            return False
    except Exception as e:  # pylint: disable=broad-except
        logger.error("同步关闭心跳发送异常: %s", repr(e))
        return False


class ServiceHeartbeatManager:
    """服务心跳管理器：管理心跳任务的启动、停止和心跳发送。

    设计要点：
    1. 心跳循环在独立 asyncio.Task 中运行，完全不影响主服务
    2. 所有异常被捕获并记录，不会传播到外部
    3. HTTP 请求有独立的超时控制（10秒），不会阻塞
    4. 支持信号处理（SIGTERM/SIGINT）实现优雅关闭
    """

    def __init__(self, config: Optional[ServiceHeartbeatConfig] = None):
        """初始化心跳管理器。

        Args:
            config: 心跳配置，如果为None则从config.json加载
        """
        self._config = config
        self._instance_ip: Optional[str] = None
        self._service_unit: Optional[str] = None
        self._az: Optional[str] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._client: Optional[httpx.AsyncClient] = None
        self._shutdown_callback: Optional[Callable] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _load_config(self) -> ServiceHeartbeatConfig:
        """加载心跳配置。"""
        if self._config is not None:
            return self._config
        config = load_config()
        return config.service_heartbeat

    def _build_payload(self, enabled: bool = True) -> dict:
        """构建心跳请求体。

        Args:
            enabled: 是否启用，正常心跳为true，关闭时为false

        Returns:
            请求体字典
        """
        cfg = self._load_config()

        # 懒加载实例信息（只加载一次）
        if self._instance_ip is None:
            self._instance_ip = get_instance_ip()
        if self._service_unit is None:
            self._service_unit = get_service_unit()
        if self._az is None:
            self._az = get_az()

        payload = {
            "serviceName": cfg.service_name,
            "instanceIp": self._instance_ip,
            "instancePort": cfg.instance_port,
            "enabled": enabled,
            "weight": cfg.weight,
        }

        # 可选字段
        if self._service_unit:
            payload["serviceUnit"] = self._service_unit
        if self._az:
            payload["az"] = self._az

        return payload

    async def _send_heartbeat(self, enabled: bool = True) -> bool:
        """发送心跳请求（异步）。

        完全独立的操作，异常不会传播到外部。

        Args:
            enabled: 是否启用，正常心跳为true，关闭时为false

        Returns:
            是否成功发送（仅用于日志，不影响主流程）
        """
        cfg = self._load_config()
        if not cfg.url:
            logger.warning("心跳URL未配置，跳过心跳发送")
            return False

        payload = self._build_payload(enabled)

        try:
            # 懒创建客户端，独立超时控制
            if self._client is None:
                self._client = httpx.AsyncClient(timeout=10.0)

            logger.debug("发送心跳: url=%s, payload=%s", cfg.url, payload)

            response = await self._client.post(cfg.url, json=payload)

            if 200 <= response.status_code < 300:
                logger.info(
                    "心跳发送成功: enabled=%s, status=%d",
                    enabled,
                    response.status_code,
                )
                return True
            logger.warning(
                "心跳发送失败: status=%d, body=%s",
                response.status_code,
                response.text[:200] if response.text else "",
            )
            return False

        except httpx.TimeoutException:
            logger.warning("心跳发送超时: url=%s", cfg.url)
            return False
        except httpx.RequestError as e:
            logger.warning("心跳发送网络错误: %s", e)
            return False
        except Exception as e:  # pylint: disable=broad-except
            # 所有异常被捕获，不影响主服务
            logger.error("心跳发送异常: %s", repr(e))
            return False

    async def _heartbeat_loop(self) -> None:
        """心跳循环：定期发送心跳。

        完全独立的循环，所有异常被捕获，不影响主服务。
        """
        cfg = self._load_config()
        interval = cfg.interval_seconds

        logger.info("心跳循环启动: interval=%ds, url=%s", interval, cfg.url)

        while self._running and not _shutdown_requested:
            # 发送心跳，失败不影响循环继续
            await self._send_heartbeat(enabled=True)

            # 等待下一次心跳
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info("心跳循环被取消")
                break

        logger.info("心跳循环结束")

    async def start(self) -> None:
        """启动心跳任务。

        心跳任务在独立的 asyncio.Task 中运行，不影响主服务。
        """
        cfg = self._load_config()

        if not cfg.enabled:
            logger.info("服务心跳未启用，跳过启动")
            return

        if not cfg.url:
            logger.warning("服务心跳URL未配置，跳过启动")
            return

        if self._running:
            logger.warning("心跳任务已在运行")
            return

        # 获取当前事件循环，用于信号处理
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        self._running = True
        self._task = asyncio.create_task(
            self._heartbeat_loop(),
            name="service-heartbeat",
        )
        logger.info("服务心跳任务已启动")

        # 注册信号处理器和atexit回调
        self._register_shutdown_handlers()

    def _register_shutdown_handlers(self) -> None:
        """注册进程关闭处理器（信号 + atexit）。"""
        cfg = self._load_config()
        if not cfg.enabled or not cfg.url:
            return

        # 注册信号处理器（SIGTERM, SIGINT）
        # 这对于 Kubernetes 优雅关闭至关重要
        def _signal_handler(
            signum: int,
            frame: FrameType | None,
        ) -> None:
            """信号处理器：设置关闭标志并触发优雅关闭。"""
            _ = frame  # 未使用，但信号处理器签名需要
            sig_name = signal.Signals(signum).name
            logger.info("收到关闭信号: %s (%d)", sig_name, signum)
            global _shutdown_requested
            _shutdown_requested = True

            # 立即发送同步关闭心跳
            # 因为异步的 stop() 可能不会在信号处理后执行
            payload = self._build_payload(enabled=False)
            send_sync_shutdown_heartbeat(cfg.url, payload)

            # 如果有事件循环，尝试安排异步关闭
            if self._loop and not self._loop.is_closed():
                try:
                    self._loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(self._async_stop()),
                    )
                except Exception:  # pylint: disable=broad-except
                    pass

            # 对于 SIGINT (Ctrl+C)，退出进程
            if signum == signal.SIGINT:
                sys.exit(0)

        # 注册信号处理器
        # SIGTERM: Kubernetes 发送的优雅关闭信号
        # SIGINT: Ctrl+C 发送的信号
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, _signal_handler)
                logger.info("已注册信号处理器: %s", sig.name)
            except (ValueError, OSError) as e:
                # Windows 可能不支持某些信号
                logger.warning("无法注册信号处理器 %s: %s", sig.name, e)

        # 注册 atexit 回调作为兜底
        def _atexit_handler() -> None:
            """atexit 回调：进程退出时发送关闭心跳。"""
            global _shutdown_requested
            if _shutdown_requested:
                # 已经在信号处理器中发送过了
                return

            logger.info("进程退出，发送关闭心跳")
            payload = self._build_payload(enabled=False)
            send_sync_shutdown_heartbeat(cfg.url, payload)

        atexit.register(_atexit_handler)
        logger.info("已注册atexit关闭心跳回调")

    async def _async_stop(self) -> None:
        """异步停止心跳任务。"""
        self._running = False

        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._client is not None:
            await self._client.aclose()
            self._client = None

        logger.info("服务心跳异步停止完成")

    async def stop(self) -> None:
        """停止心跳任务并发送关闭信号。

        在正常关闭流程（lifespan finally块）中调用。
        """
        global _shutdown_requested

        if not self._running:
            return

        self._running = False

        # 取消心跳循环任务
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # 发送关闭信号（enabled=false）
        # 如果还没有发送过（信号处理器可能已经发送）
        if not _shutdown_requested:
            logger.info("发送服务关闭心跳信号...")
            await self._send_heartbeat(enabled=False)

        # 关闭HTTP客户端
        if self._client is not None:
            await self._client.aclose()
            self._client = None

        logger.info("服务心跳已停止")


# 全局心跳管理器实例
_manager: Optional[ServiceHeartbeatManager] = None


def get_service_heartbeat_manager(
    config: Optional[ServiceHeartbeatConfig] = None,
) -> ServiceHeartbeatManager:
    """获取全局心跳管理器实例。"""
    global _manager
    if _manager is None:
        _manager = ServiceHeartbeatManager(config)
    return _manager


async def start_service_heartbeat(
    config: Optional[ServiceHeartbeatConfig] = None,
) -> None:
    """启动服务心跳。"""
    manager = get_service_heartbeat_manager(config)
    await manager.start()


async def stop_service_heartbeat() -> None:
    """停止服务心跳并发送关闭信号。"""
    global _manager
    if _manager is not None:
        await _manager.stop()
