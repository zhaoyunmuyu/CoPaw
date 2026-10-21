# -*- coding: utf-8 -*-
"""考虑节假日和调休的特殊排程、候选展开与下次运行预览。"""

import calendar as month_calendar
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from time import monotonic

from croniter import croniter

BEIJING = ZoneInfo("Asia/Shanghai")
CALENDAR_DAY = re.compile(r"^(?:LW|([1-9]|[12][0-9]|3[01])W)$", re.IGNORECASE)
# 仅限制展示预览的后续上游查询，不中断已经开始的一次日期查询。
PREVIEW_BUDGET_SECONDS = 2.5


def candidate_cron(cron):
    """日历业务表达式展开为平台每日候选，月份留待逻辑日期准入。"""
    parts = cron.split()
    if len(parts) == 5 and CALENDAR_DAY.fullmatch(parts[2]):
        parts[2] = "*"
        parts[3] = "*"
        if parts[4] == "?":
            parts[4] = "*"
    return " ".join(parts)


def calendar_rule(cron):
    """识别整月工作日规则，避免与星期条件产生不明确的组合语义。"""
    parts = cron.split()
    if len(parts) != 5 or not CALENDAR_DAY.fullmatch(parts[2]):
        return None
    if parts[4] not in {"*", "?"}:
        raise ValueError("W/LW does not support a day-of-week restriction")
    return parts


def validate_cron(cron):
    """统一校验五段业务表达式，日历月份不能因候选展开而漏检。"""
    normalized = " ".join(cron.split())
    parts = normalized.split()
    if len(parts) != 5:
        raise ValueError("cron requires five fields")
    rule = calendar_rule(normalized)
    if not croniter.is_valid(candidate_cron(normalized)):
        raise ValueError("invalid cron expression")
    if rule and not croniter.is_valid(f"0 0 * {parts[3]} *"):
        raise ValueError("invalid calendar month")
    return normalized


async def _target_date(year, month, rule, calendar):
    last = month_calendar.monthrange(year, month)[1]
    if rule.upper() == "LW":
        days = range(last, 0, -1)
    else:
        anchor = min(int(rule[:-1]), last)
        days = sorted(
            range(1, last + 1),
            key=lambda day: (abs(day - anchor), day),
        )
    source = "api"
    for day in days:
        candidate = date(year, month, day)
        observed = await calendar.get_day(candidate)
        if observed["source"] == "fallback":
            source = "fallback"
        if observed["is_workday"]:
            return candidate, source
    return None, source


async def allows(cron, fire_at, calendar, *, run_on_non_workday=False):
    """按北京时间逻辑日期判定一次准入，并返回降级来源及跳过原因。"""
    if not isinstance(calendar, _MemoCalendar):
        calendar = _MemoCalendar(calendar)
    at = fire_at if fire_at.tzinfo else fire_at.replace(tzinfo=timezone.utc)
    day = at.astimezone(BEIJING).date()
    rule = calendar_rule(cron) if cron else None
    nominal = datetime(day.year, day.month, day.day, tzinfo=BEIJING)
    if rule and not croniter.match(f"0 0 * {rule[3]} *", nominal):
        return {
            "business_date": day.isoformat(),
            "is_workday": day.weekday() < 5,
            "source": "fallback",
            "allowed": False,
            "skipped": "calendar_rule",
        }
    result = await calendar.get_day(day)
    source = result["source"]
    allowed = run_on_non_workday or result["is_workday"]
    reason = "" if allowed else "non_workday"
    if rule:
        target, target_source = await _target_date(
            day.year,
            day.month,
            rule[2],
            calendar,
        )
        if target_source == "fallback":
            source = "fallback"
        allowed = target == day
        reason = "" if allowed else "calendar_rule"
    return {
        "business_date": day.isoformat(),
        "is_workday": result["is_workday"],
        "source": source,
        "allowed": bool(allowed),
        "skipped": reason,
    }


class _MemoCalendar:
    """同一准入或预览复用每个日期的一次观测，避免结果中途变化。"""

    def __init__(self, calendar):
        self.calendar = calendar
        self.days = {}
        self.started_at = monotonic()

    async def get_day(self, day):
        if day not in self.days:
            self.days[day] = await self.calendar.get_day(day)
        return self.days[day]


class _PreviewCalendar(_MemoCalendar):
    """共享一轮预览预算；预算耗尽的未知日期仅在本次展示中使用周末兜底。"""

    def __init__(self, memo):
        super().__init__(memo)
        self.days = memo.days
        self.deadline = memo.started_at + PREVIEW_BUDGET_SECONDS
        self.previews = {}

    async def get_day(self, day):
        if day not in self.days:
            if monotonic() >= self.deadline:
                self.days[day] = {
                    "date": day.isoformat(),
                    "is_workday": day.weekday() < 5,
                    "source": "fallback",
                }
            else:
                # 不取消上游已取得但正在写缓存的结果，保留其明确判定。
                self.days[day] = await self.calendar.get_day(day)
        return self.days[day]


def _preview_calendar(calendar):
    if isinstance(calendar, _PreviewCalendar):
        return calendar
    if not isinstance(calendar, _MemoCalendar):
        calendar = _MemoCalendar(calendar)
    if not hasattr(calendar, "preview"):
        calendar.preview = _PreviewCalendar(calendar)
    return calendar.preview


async def next_run_times(
    cron,
    timezone_name,
    calendar,
    *,
    run_on_non_workday=False,
    count=3,
    now=None,
):
    """只读生成未来实际运行时间，不写任务状态或补造平台执行。"""
    if count <= 0:
        return []
    calendar = _preview_calendar(calendar)
    key = (cron, timezone_name, run_on_non_workday, count, now)
    if key not in calendar.previews:
        rule = calendar_rule(cron)
        values = (
            await _calendar_runs(
                cron,
                rule,
                calendar,
                count,
                now,
                timezone_name,
            )
            if rule
            else await _regular_runs(
                cron,
                timezone_name,
                calendar,
                run_on_non_workday,
                count,
                now,
            )
        )
        calendar.previews[key] = tuple(values)
    return list(calendar.previews[key])


async def _regular_runs(
    cron,
    timezone_name,
    calendar,
    run_on_non_workday,
    count,
    now,
):
    """没有可预览日期是合法空结果，不把它误报为整页任务定义损坏。"""
    tz = ZoneInfo(timezone_name or "UTC")
    cursor = now or datetime.now(timezone.utc)
    cursor = (
        cursor.replace(tzinfo=tz)
        if cursor.tzinfo is None
        else cursor.astimezone(tz)
    )
    runs = []
    for _ in range(3660):
        candidate = croniter(cron, cursor).get_next(datetime)
        if (
            await allows(
                cron,
                candidate,
                calendar,
                run_on_non_workday=run_on_non_workday,
            )
        )["allowed"]:
            runs.append(candidate)
            cursor = candidate
        else:
            # 同一非工作日的分钟级候选一并跳过，避免无意义地逐分钟查询。
            local = candidate.astimezone(BEIJING)
            cursor = (
                local.replace(hour=0, minute=0, second=0, microsecond=0)
                + timedelta(days=1, microseconds=-1)
            ).astimezone(tz)
        if len(runs) >= count:
            return runs
    return runs


async def _calendar_runs(cron, rule, calendar, count, now, timezone_name):
    base = (now or datetime.now(timezone.utc)).astimezone(BEIJING)
    clock_timezone = ZoneInfo(timezone_name or "UTC")
    runs = []
    for offset in range(120):
        month_index = base.year * 12 + base.month - 1 + offset
        year, month = month_index // 12, month_index % 12 + 1
        first = datetime(year, month, 1, tzinfo=BEIJING)
        if not croniter.match(f"0 0 * {rule[3]} *", first):
            continue
        target, _ = await _target_date(year, month, rule[2], calendar)
        if target is None:
            continue
        cursor = max(
            first.replace(day=target.day) - timedelta(microseconds=1),
            base,
        ).astimezone(clock_timezone)
        while len(runs) < count:
            candidate = croniter(candidate_cron(cron), cursor).get_next(
                datetime,
            )
            if candidate.astimezone(BEIJING).date() != target:
                break
            runs.append(candidate)
            cursor = candidate
        if len(runs) >= count:
            return runs
    return runs
