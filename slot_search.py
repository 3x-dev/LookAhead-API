from copy import deepcopy
from typing import Any, List

from arrow import get

from common import get_unix, hh_mm_to_seconds, special_conv
from constants import (appointment_types, default_break, default_duration,
                       iso_8601, minimum_divisible, work_start_from,
                       work_stop_at)
from model import Event, Output, Slot, SlotStr


class SlotSearch:
    def __init__(self, output: Output, events: List[Any], bzz_timezone: str) -> None:
        self.output = output
        self.events = events
        self.bzz_timezone = bzz_timezone

    def _find_gaps(self, events: List[Event], sss: int, eee: int) -> List[Slot]:
        if self.bzz_timezone == "":
            return []
        # Find the time ranges between sss and eee when the business is closed
        # i.e. as of now, 6:00 pm > and 8:00 am < are closed for the timezone of the business
        # Book that as events
        wsf = hh_mm_to_seconds(work_start_from)
        wsa = hh_mm_to_seconds(work_stop_at)

        fake_events: List[Event] = []
        _sss = deepcopy(sss)
        _eee = deepcopy(eee)
        while _sss <= _eee:
            _t1 = hh_mm_to_seconds(get(_sss).to(
                self.bzz_timezone).format(iso_8601)[-14:-6])
            if _t1 < wsf:  # Imagine _t1 is 7 am for the businesse's timezone
                # So we added an event, from 7 am to 8 am
                _diff = (wsf - _t1)
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
                    six_2_12 = (seconds_in_a_day - wsa)
                    till_wsa = seconds_in_a_day - \
                        six_2_12 - \
                        wsf - frm_wsf
                    # till_wsa is the seconds remaining till 6 pm from _sss
                    next_i_incre = till_wsa + \
                        six_2_12 + wsf
                    fake_events.append(
                        Event("", _sss + till_wsa, _sss + next_i_incre))
                    # Now (sss + i) is at 8 am but of the next day
                    _sss += next_i_incre

        # Sort events based on the start_at attribute
        events.extend(fake_events)
        events = sorted(events, key=lambda event: event.start_at)

        gaps: List[Slot] = []

        # Check initial gap
        if sss < events[0].start_at:
            gaps.append(Slot(sss, events[0].start_at))

        # Check gaps between events
        for i in range(len(events) - 1):
            # If the end of the current event is less than the start of the next event,
            # it means there's a gap
            if events[i].end_at < events[i+1].start_at:
                gaps.append(Slot(events[i].end_at, events[i+1].start_at))
            # If the current event ends after the next event starts,
            # adjust the start of the next event to avoid overlap
            elif events[i].end_at > events[i+1].start_at:
                events[i+1].start_at = events[i].end_at

        # Check final gap
        if events[-1].end_at < eee:
            gaps.append(Slot(events[-1].end_at, eee))

        return gaps

    async def find_available_slots(self) -> List[SlotStr]:
        events: List[Event] = []

        # Convert elements to Event objects
        events = list(map(lambda x: Event(
            event_id=x.get("id"),
            start_at=int(
                get(x.get("start", {}).get("dateTime", 0)).timestamp()),
            end_at=int(get(x.get("end", {}).get("dateTime", 0)).timestamp())
        ), self.events))

        # Now we got events which is a list of Event objects
        # Remove events whose start_at or end_at is 0 or timezone is empty
        events = list(filter(lambda x: x.start_at !=
                      0 and x.end_at != 0, events))
        user_tz_offset = self.output.start_date[-6:]

        _gaps: List[Slot] = self._find_gaps(
            events=events,
            sss=get_unix(self.output.start_date),
            eee=get_unix(self.output.end_date)
        )

        # Desired from and to in local time of the calendar
        _dfr = hh_mm_to_seconds(get(
            f"{self.output.start_date[0:11]}{self.output.start_time}:00{self.output.start_date[-6:]}").to(self.bzz_timezone).format(iso_8601)[-14:-6]
        )
        _dto = hh_mm_to_seconds(get(
            f"{self.output.start_date[0:11]}{self.output.end_time}:00{self.output.start_date[-6:]}").to(self.bzz_timezone).format(iso_8601)[-14:-6]
        )

        wsf = hh_mm_to_seconds(work_start_from)
        wsa = hh_mm_to_seconds(work_stop_at)

        # Explanation
        # (_dfr < wsf and _dto < wsf) - their desired time starts before 8 am also ends before 8 am
        # (_dfr > wsa and _dto > wsa) - their desired time starts after 6 pm also ends after 6 pm (max 12 it can be and 12 is midnight)
        # (_dfr > wsa and _dto < wsf) - their desired time starts after 6 pm and ends before 8 am (before the doctor even wakes up!)
        if (_dfr < wsf and _dto < wsf) \
                or (_dfr > wsa and _dto > wsa) \
            or (_dfr > wsa and _dto < wsf):
            _gaps = []

        prefer_from = special_conv(
            f"2023-01-01T{self.output.start_time}:00{self.output.start_date[-6:]}", user_tz_offset)
        prefer_to = special_conv(
            f"2023-01-01T{self.output.end_time}:00{self.output.start_date[-6:]}", user_tz_offset)

        gaps: List[Slot] = []

        # Now remove the _gaps which do not fall in the desired time range
        for g in _gaps:
            # sa is when the gap starts at in user's timezone offset from start of their day
            # e.g. If the gap starts at 8 am in user's timezone then sa would be 8 * 60 * 60
            sa = special_conv(g.start_at, user_tz_offset)
            # ea is when the gap ends at in user's timezone offset from start of their day
            ea = special_conv(g.end_at, user_tz_offset)

            if sa >= prefer_from and ea <= prefer_to:  # a perfect scenario
                gaps.append(g)
            elif sa <= prefer_from:
                slot = Slot(0, 0)
                # since user's preference matters more than when slot would start, thus use prefer_from
                slot.start_at = (g.start_at - sa) + prefer_from
                # if the slot ends after user's preferred to time range then consider user's preferred time as end at
                # e.g. If slot is available from 10 am to 2 pm but user wants appointment from 10 am to 12 pm
                # then end at would be 12 pm not 2 pm, even though 2 pm is available
                slot.end_at = ((g.end_at - ea) +
                               prefer_to) if ea > prefer_to else g.end_at
                gaps.append(slot)
            elif sa >= prefer_from:
                slot = Slot(0, 0)
                # In this scenario, slot is available from a later moment than what's preferred by user
                # thus, start at would be from when slot is available from
                slot.start_at = g.start_at
                slot.end_at = ((g.end_at - ea) +
                               prefer_to) if ea > prefer_to else g.end_at
                gaps.append(slot)

        _gaps.clear()
        _gaps = deepcopy(gaps)
        gaps.clear()

        duration, _break = default_duration, default_break

        for appointment in appointment_types:
            if appointment._type == self.output.appointment_type:
                duration, _break = appointment.duration, appointment._break

        required_time = duration * 60 + _break * 60

        # Now we got _gaps which fall into desired time range and are available for booking
        # Now we need to check if the duration of the gap is enough for the appointment

        for g in _gaps:
            rounded = (g.start_at // minimum_divisible) * minimum_divisible
            if g.start_at > rounded:
                g.start_at = rounded + minimum_divisible
            else:
                g.start_at = rounded

            time_diff = g.end_at - g.start_at
            if time_diff >= required_time:
                current_time = g.start_at
                while time_diff >= required_time:
                    time_diff -= required_time
                    gaps.append(Slot(current_time, g.end_at - time_diff))
                    current_time += required_time

        # Now sort the list of gaps based on the start_at attribute
        slots: List[SlotStr] = list(
            sorted(map(lambda x: SlotStr(
                start_at=get(x.start_at).to(user_tz_offset).format(iso_8601),
                end_at=get(x.end_at).to(user_tz_offset).format(iso_8601)
            ), gaps), key=lambda s: get_unix(s.start_at)))
        return slots
