from dataclasses import asdict
from time import time
from typing import List, Tuple

from arrow import Arrow, get
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import TypeAdapter

from common import generate_id
from database import fsdb
from model import (
    DatabaseCalendar,
    DatabaseEvent,
    Event,
    EventStatus,
    Output,
    Slot,
    SlotHolder,
    UpdateAppointmentRequest,
    UpdateAppointmentRequestExtras,
    UpdateCalendarRequest,
)
from notyf import Notyf
from slot_search import SlotSearch


def get_doc_path(x: str, y: str | None = None, z: str | None = None):
    _t = f"businesses/{x}/calendars"
    if y is not None:
        _t += f"/{y}"
    return f"{_t}/events/{z}" if z is not None else _t


def get_events(
    email: str,
    calendarId: str,
    start_date: Arrow,
    end_date: Arrow,
    status: EventStatus | None = None,
    user_phone: str | None = None,
) -> List[DatabaseEvent]:
    events: List[DatabaseEvent] = []
    if email is not None:
        doc_ref = (
            fsdb.collection(f"{get_doc_path(email, calendarId)}/events")
            .where(filter=FieldFilter("startTime", ">=", int(start_date.timestamp())))
            .where(filter=FieldFilter("startTime", "<=", int(end_date.timestamp())))
        )
        if status is not None:
            doc_ref = doc_ref.where(filter=FieldFilter("status", "==", status))
        if user_phone is not None:
            doc_ref = doc_ref.where(filter=FieldFilter("customer", "==", user_phone))
        ta = TypeAdapter(DatabaseEvent)
        events = list(
            map(lambda x: ta.validate_python(x.to_dict(), strict=False), doc_ref.get())
        )
    return events


def recalibrate_day(incoming_day):
    if not (0 <= incoming_day <= 6):
        raise ValueError("Invalid day: Day must be in the range 0 to 6")

    recalibrated_day = (incoming_day + 1) % 7
    return recalibrated_day


def is_future_date(s: Slot) -> bool:
    return s.startTime > time()


class FBCalendar:
    def __init__(self, email: str, output: Output | None) -> None:
        self.email = email
        self.output = output

    def create_calendar(self, body: DatabaseCalendar) -> DatabaseCalendar | None:
        fsdb.document(get_doc_path(self.email, body.calendarId)).set(asdict(body))
        return self.get_calendar(calendarId=body.calendarId)

    def get_calendar(self, calendarId: str) -> DatabaseCalendar | None:
        data = fsdb.document(get_doc_path(x=self.email, y=calendarId)).get().to_dict()
        return (
            TypeAdapter(DatabaseCalendar).validate_python(data)
            if data is not None
            else None
        )

    def get_calendars(self) -> List[DatabaseCalendar]:
        return list(
            map(
                lambda x: TypeAdapter(DatabaseCalendar).validate_python(x.to_dict()),
                fsdb.collection(get_doc_path(x=self.email)).get(),
            )
        )

    def update_calendar(
        self, calendarId: str, body: UpdateCalendarRequest
    ) -> DatabaseCalendar | None:
        fsdb.document(get_doc_path(self.email, calendarId)).update(
            TypeAdapter(UpdateCalendarRequest).dump_python(body, exclude_none=True)
        )
        return self.get_calendar(calendarId=calendarId)

    def delete_calendar(self, calendarId: str):
        fsdb.recursive_delete(fsdb.document(get_doc_path(self.email, calendarId)))

    def create_event(
        self,
        calendarId: str,
        start_time: int,
        end_time: int,
        notyf: Notyf,
        description: str | None = None,
        status: EventStatus = EventStatus.tentative,
    ) -> DatabaseEvent | None:
        event = DatabaseEvent(
            calendarId=calendarId,
            summary="Appointment",
            description=description
            if description is not None
            else notyf.get_human_readable_message(),
            status=status,
            customer=notyf.phoneNumber or "",
            startTime=start_time,
            endTime=end_time,
        )
        event.eventId = generate_id()
        fsdb.document(get_doc_path(self.email, event.calendarId, event.eventId)).set(
            asdict(event)
        )
        return self._get_event(calendarId=calendarId, eventId=event.eventId)

    def update_event(
        self, calendarId: str, eventId: str, body: UpdateAppointmentRequest
    ) -> DatabaseEvent | None:
        fsdb.document(get_doc_path(self.email, calendarId, eventId)).update(
            TypeAdapter(UpdateAppointmentRequest).dump_python(body, exclude_none=True)
        )
        return self._get_event(calendarId=calendarId, eventId=eventId)

    def update_event_extras(
        self, calendarId: str, eventId: str, body: UpdateAppointmentRequestExtras
    ) -> DatabaseEvent | None:
        fsdb.document(get_doc_path(self.email, calendarId, eventId)).update(
            TypeAdapter(UpdateAppointmentRequestExtras).dump_python(
                body, exclude_none=True
            )
        )
        return self._get_event(calendarId=calendarId, eventId=eventId)

    def _get_event(self, calendarId: str, eventId: str) -> DatabaseEvent | None:
        data = (
            fsdb.document(get_doc_path(self.email, calendarId, eventId)).get().to_dict()
        )
        return (
            TypeAdapter(DatabaseEvent).validate_python(data)
            if data is not None
            else None
        )

    def _get_events(self) -> List[Tuple[DatabaseCalendar, List[DatabaseEvent]]]:
        """
        This function returns the events between timeMin to timeMax for the calendars that are eligible to be considered for finding slots.
        """
        _t: List[Tuple[DatabaseCalendar, List[DatabaseEvent]]] = []

        calendars = self.get_calendars()

        if self.output is not None:
            for c in calendars:
                _t.append(
                    (
                        c,
                        list(
                            filter(
                                lambda x: x.status != EventStatus.cancelled,
                                get_events(
                                    self.email,
                                    c.calendarId,
                                    get(self.output.startDate),
                                    get(self.output.endDate),
                                ),
                            )
                        ),
                    )
                )
        return _t

    def find_available_slots(self) -> List[SlotHolder]:
        """
        This functions is the entry point, it makes use of all the other functions of the class to provide available slots.

        Returns:
            List[SlotHolder]: List of available slots along with other info.
        """

        events = self._get_events()
        slots: List[SlotHolder] = []

        if self.output is not None:
            for e in events:
                slots.append(
                    SlotHolder(
                        calendarId=e[0].calendarId,
                        calendarName=e[0].calendarName,
                        timeZone=e[0].timeZone,
                        opens=e[0].opens,
                        closes=e[0].closes,
                        items=list(
                            filter(
                                is_future_date,
                                filter(
                                    lambda x: e[0].daysOpen[
                                        recalibrate_day(
                                            get(x.startTime).to(e[0].timeZone).weekday()
                                        )
                                    ]
                                    is True,
                                    SlotSearch(
                                        self.output,
                                        list(
                                            map(
                                                lambda x: Event(
                                                    eventId=x.eventId,
                                                    startTime=x.startTime,
                                                    endTime=x.endTime,
                                                ),
                                                e[1],
                                            )
                                        ),
                                        e[0],
                                    ).find_available_slots_internal(),
                                ),
                            )
                        ),
                    )
                )
        return slots
