from copy import deepcopy
from datetime import datetime, timedelta
from typing import List

from arrow import get
from pytz import FixedOffset, utc

from constants import date_format
from model import DatabaseCalendar, Event, Output, Slot


def get_unix(s: str, fmt: str = date_format) -> int:
    return int(get(s, fmt).timestamp())


def convert_unix_to_timezone(unix_timestamp: int, offset: str) -> datetime:
    hours, minutes = map(int, offset.split(":"))
    tz = FixedOffset(int(timedelta(hours=hours, minutes=minutes).total_seconds() / 60))
    return datetime.fromtimestamp(unix_timestamp, tz=utc).astimezone(tz)


def hh_mm_to_seconds(s: str) -> int:
    try:
        spl = s.split(":")
        return int(spl[0]) * 60 * 60 + int(spl[1]) * 60
    except Exception as _:
        pass
    return 0


def special_conv(_t: int | str, offset: str) -> int:
    if isinstance(_t, str):
        _t = get_unix(_t)
    dt = convert_unix_to_timezone(_t, offset)
    return hh_mm_to_seconds(str(dt)[-14:-6])


class SlotSearch:
    def __init__(
        self, output: Output, events: List[Event], calendar: DatabaseCalendar
    ) -> None:
        self.output = output
        self.events = events
        self.calendar = calendar

    def _find_gaps(self, events: List[Event], sss: int, eee: int) -> List[Slot]:
        # Find the time ranges between sss and eee when the business is closed
        # e.g. If 6:00 pm > and 8:00 am < are closed for the timezone of the business, book that as events
        wsf = hh_mm_to_seconds(self.calendar.opens)
        wsa = hh_mm_to_seconds(self.calendar.closes)

        fake_events: List[Event] = []
        _sss = deepcopy(sss)
        _eee = deepcopy(eee)
        while _sss <= _eee:
            _t1 = hh_mm_to_seconds(
                get(_sss).to(self.calendar.timeZone).format(date_format)[-14:-6]
            )
            if _t1 < wsf:  # Imagine _t1 is 7 am for the businesse's timezone
                # So we added an event, from 7 am to 8 am
                _diff = wsf - _t1
                fake_events.append(Event("", _sss, _sss + _diff))
                _sss += _diff  # Now sss is at 8 am
            elif _t1 == wsf:
                _sss += wsa - wsf
            elif _t1 > wsf:
                # add a (fake) event from 6:00 pm to 8 am
                seconds_in_a_day = 60 * 60 * 24

                if _t1 >= wsa:
                    next_i_incre = (seconds_in_a_day - _t1) + wsf
                    fake_events.append(Event("", _sss, _sss + next_i_incre))
                    # Now (sss + i) is at 8 am but of the next day
                    _sss += next_i_incre
                else:
                    # the seconds from wsf since we know _t1 is after wsf (_t1 is after 8 am!)
                    frm_wsf = _t1 - wsf
                    # ================|<====frm_wsf==>|=========================
                    # ================8am====================6pm============12am
                    #                                 ^
                    #                               _sss
                    # 1. determine and book a fake event from 6 pm to 8 am from the above info
                    # 2. set _sss to next day's 8 am
                    six_2_12 = seconds_in_a_day - wsa
                    till_wsa = seconds_in_a_day - six_2_12 - wsf - frm_wsf
                    # till_wsa is the seconds remaining till 6 pm from _sss
                    next_i_incre = till_wsa + six_2_12 + wsf
                    fake_events.append(
                        Event(
                            eventId="",
                            startTime=_sss + till_wsa,
                            endTime=_sss + next_i_incre,
                        )
                    )
                    # Now (sss + i) is at 8 am but of the next day
                    _sss += next_i_incre

        # Sort events based on the start_at attribute
        events.extend(fake_events)
        events = sorted(events, key=lambda event: event.startTime)

        gaps: List[Slot] = []

        # Check initial gap
        if sss < events[0].startTime:
            gaps.append(Slot(sss, events[0].startTime))

        # Check gaps between events
        for i in range(len(events) - 1):
            # If the end of the current event is less than the start of the next event,
            # it means there's a gap
            if events[i].endTime < events[i + 1].startTime:
                gaps.append(Slot(events[i].endTime, events[i + 1].startTime))
            # If the current event ends after the next event starts,
            # adjust the start of the next event to avoid overlap
            elif events[i].endTime > events[i + 1].startTime:
                events[i + 1].startTime = events[i].endTime

        # Check final gap
        if events[-1].endTime < eee:
            gaps.append(Slot(events[-1].endTime, eee))

        return gaps

    def find_available_slots_internal(self) -> List[Slot]:
        if self.output is None:
            return []

        # Now we got events which is a list of Event objects
        # Remove events whose start_at or end_at is 0
        self.events = list(
            filter(lambda x: x.startTime != 0 and x.endTime != 0, self.events)
        )
        user_tz_offset = self.output.startDate[-6:]

        _gaps: List[Slot] = self._find_gaps(
            events=self.events,
            sss=get_unix(self.output.startDate),
            eee=get_unix(self.output.endDate),
        )

        # Desired from and to in local time of the calendar
        _dfr = hh_mm_to_seconds(
            get(
                f"{self.output.startDate[0:11]}{self.output.startTime}:00{self.output.startDate[-6:]}"
            )
            .to(self.calendar.timeZone)
            .format(date_format)[-14:-6]
        )
        _dto = hh_mm_to_seconds(
            get(
                f"{self.output.startDate[0:11]}{self.output.endTime}:00{self.output.startDate[-6:]}"
            )
            .to(self.calendar.timeZone)
            .format(date_format)[-14:-6]
        )

        wsf = hh_mm_to_seconds(self.calendar.opens)
        wsa = hh_mm_to_seconds(self.calendar.closes)

        # Explanation
        # (_dfr < wsf and _dto < wsf) - their desired time starts before 8 am also ends before 8 am
        # (_dfr > wsa and _dto > wsa) - their desired time starts after 6 pm also ends after 6 pm (max 12 it can be and 12 is midnight)
        # (_dfr > wsa and _dto < wsf) - their desired time starts after 6 pm and ends before 8 am (before the doctor even wakes up!)
        if (
            (_dfr < wsf and _dto < wsf)
            or (_dfr > wsa and _dto > wsa)
            or (_dfr > wsa and _dto < wsf)
        ):
            _gaps = []

        prefer_from = special_conv(
            f"2023-01-01T{self.output.startTime}:00{self.output.startDate[-6:]}",
            user_tz_offset,
        )
        prefer_to = special_conv(
            f"2023-01-01T{self.output.endTime}:00{self.output.startDate[-6:]}",
            user_tz_offset,
        )

        gaps: List[Slot] = []

        # Now remove the _gaps which do not fall in the desired time range
        for g in _gaps:
            # sa is when the gap starts at in user's timezone offset from start of their day
            # e.g. If the gap starts at 8 am in user's timezone then sa would be 8 * 60 * 60
            sa = special_conv(g.startTime, user_tz_offset)
            # ea is when the gap ends at in user's timezone offset from start of their day
            ea = special_conv(g.endTime, user_tz_offset)

            if sa >= prefer_from and ea <= prefer_to:  # a perfect scenario
                gaps.append(g)
            elif sa <= prefer_from:
                slot = Slot(0, 0)
                # since user's preference matters more than when slot would start, thus use prefer_from
                slot.startTime = (g.startTime - sa) + prefer_from
                # if the slot ends after user's preferred to time range then consider user's preferred time as end at
                # e.g. If slot is available from 10 am to 2 pm but user wants appointment from 10 am to 12 pm
                # then end at would be 12 pm not 2 pm, even though 2 pm is available
                slot.endTime = (
                    ((g.endTime - ea) + prefer_to) if ea > prefer_to else g.endTime
                )
                gaps.append(slot)
            elif sa >= prefer_from:
                slot = Slot(0, 0)
                # In this scenario, slot is available from a later moment than what's preferred by user
                # thus, start at would be from when slot is available from
                slot.startTime = g.startTime
                slot.endTime = (
                    ((g.endTime - ea) + prefer_to) if ea > prefer_to else g.endTime
                )
                gaps.append(slot)

        _gaps.clear()
        _gaps = deepcopy(gaps)
        gaps.clear()

        duration, _break = self.calendar.durationMins, self.calendar.breakMins
        required_time = duration * 60 + _break * 60

        # Now we got _gaps which fall into desired time range and are available for booking
        # Now we need to check if the duration of the gap is enough for the appointment

        minimum_divisible = 30 * 60  # 30 minutes

        for g in _gaps:
            rounded = (g.startTime // minimum_divisible) * minimum_divisible
            if g.startTime > rounded:
                g.startTime = rounded + minimum_divisible
            else:
                g.startTime = rounded

            time_diff = g.endTime - g.startTime
            if time_diff >= required_time:
                current_time = g.startTime
                while time_diff >= required_time:
                    time_diff -= required_time
                    gaps.append(Slot(current_time, g.endTime - time_diff))
                    current_time += required_time

        # Now sort the list of gaps based on the start_at attribute
        return list(sorted(gaps, key=lambda s: s.startTime))
