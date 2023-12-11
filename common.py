from datetime import datetime, timedelta
from typing import List

from arrow import get
from pytz import FixedOffset, all_timezones, timezone, utc

from constants import iso_8601


def get_unix(s: str, fmt: str = iso_8601) -> int:
    return int(get(s, fmt).timestamp())


def from_unix_to_iso(_t: int) -> str:
    return get(_t).format(iso_8601)


def get_seconds_so_far(_t: int | str) -> int:
    if isinstance(_t, int):
        return int(_t % (60 * 60 * 24))
    else:
        return int(get_unix(_t) % (60 * 60 * 24))


def convert_unix_to_timezone(unix_timestamp: int, offset: str) -> datetime:
    hours, minutes = map(int, offset.split(":"))
    offset = timedelta(hours=hours, minutes=minutes)
    tz = FixedOffset(offset.total_seconds() / 60)
    dt = datetime.fromtimestamp(unix_timestamp, tz=utc)
    localized_dt = dt.astimezone(tz)
    return localized_dt


def hh_mm_to_seconds(s: str) -> int:
    try:
        spl = s.split(":")
        return int(spl[0]) * 60 * 60 + int(spl[1]) * 60
    except:
        pass
    return 0


def special_conv(_t: int | str, offset: str) -> int:
    if isinstance(_t, str):
        _t = get_unix(_t)
    dt = convert_unix_to_timezone(_t, offset)
    return hh_mm_to_seconds(str(dt)[-14:-6])


def get_timezones_for_offset(offset_str: str) -> List[str]:
    hours, minutes = map(int, offset_str.split(':'))
    offset_minutes = hours * 60 + minutes

    matching_timezones = [tz for tz in all_timezones if timezone(
        tz).utcoffset(datetime.utcnow()).total_seconds() == offset_minutes * 60]

    return matching_timezones


def is_valid_date(s: str, fmt: str) -> bool:
    """
    This function checks if the given string from chatgpt output is a valid date or not.

    Args:
        s (str): The date string.
        fmt (str): The expected format the date string to be in.

    Returns:
        bool: Whether the date is valid or not.
    """
    try:
        _ = get(s, fmt)
        return True
    except:
        pass
    return False
