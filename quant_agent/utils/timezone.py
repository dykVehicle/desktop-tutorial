"""
时区与交易时间管理模块

全局使用北京时间 (Asia/Shanghai, UTC+8)。
提供交易时间判断功能。
"""

from datetime import datetime, timezone, timedelta

# 北京时间时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))


def now_beijing() -> datetime:
    """
    获取当前北京时间。

    Returns:
        带时区信息的北京时间 datetime
    """
    return datetime.now(BEIJING_TZ)


def beijing_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    获取当前北京时间的格式化字符串。

    Args:
        fmt: 时间格式

    Returns:
        格式化后的北京时间字符串
    """
    return now_beijing().strftime(fmt)


def is_trading_day(dt: datetime | None = None) -> bool:
    """
    判断是否为交易日（简单判断：周一到周五）。

    注意：不含节假日判断，仅排除周末。
    完整的节假日日历需要外部数据源支持。

    Args:
        dt: 待判断的日期，默认当前北京时间

    Returns:
        是否为交易日
    """
    if dt is None:
        dt = now_beijing()
    # 周一=0, 周日=6；交易日为周一到周五
    return dt.weekday() < 5


def is_trading_hours(dt: datetime | None = None) -> bool:
    """
    判断当前是否处于A股交易时间。

    A股交易时间（北京时间）：
    - 上午: 09:30 ~ 11:30
    - 下午: 13:00 ~ 15:00

    Args:
        dt: 待判断的时间，默认当前北京时间

    Returns:
        是否在交易时间内
    """
    if dt is None:
        dt = now_beijing()

    if not is_trading_day(dt):
        return False

    t = dt.time()

    # 上午盘: 09:30 ~ 11:30
    morning_open = datetime.strptime("09:30", "%H:%M").time()
    morning_close = datetime.strptime("11:30", "%H:%M").time()

    # 下午盘: 13:00 ~ 15:00
    afternoon_open = datetime.strptime("13:00", "%H:%M").time()
    afternoon_close = datetime.strptime("15:00", "%H:%M").time()

    return (morning_open <= t <= morning_close) or (afternoon_open <= t <= afternoon_close)


def get_market_status(dt: datetime | None = None) -> str:
    """
    获取当前市场状态描述。

    Args:
        dt: 待判断的时间，默认当前北京时间

    Returns:
        市场状态字符串
    """
    if dt is None:
        dt = now_beijing()

    if not is_trading_day(dt):
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return f"休市（{weekday_names[dt.weekday()]}）"

    t = dt.time()
    morning_open = datetime.strptime("09:30", "%H:%M").time()
    morning_close = datetime.strptime("11:30", "%H:%M").time()
    afternoon_open = datetime.strptime("13:00", "%H:%M").time()
    afternoon_close = datetime.strptime("15:00", "%H:%M").time()

    if t < morning_open:
        return "盘前（未开盘）"
    elif morning_open <= t <= morning_close:
        return "交易中（上午盘）"
    elif morning_close < t < afternoon_open:
        return "午间休市"
    elif afternoon_open <= t <= afternoon_close:
        return "交易中（下午盘）"
    else:
        return "已收盘"
