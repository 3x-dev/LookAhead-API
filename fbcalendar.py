from calendar import Calendar
from dataclasses import dataclass
from typing import Any, List, Optional
from common import is_valid_date
from database import db_create_calendar, db_create_event, db_delete_calendars, db_get_calendars, db_get_events, db_update_event
from model import Appointment, BusinessCalendar, CommonAppointmentRequest, CreateCalendarRequest, Output, SlotHolder, UpdateAppointmentRequest
from notyf import Notyf
from slot_search import SlotSearch
from constants import iso_8601
from datetime import datetime

@dataclass
class CreatedEvent:
    calendarId: Optional[str]
    eventId: Optional[str]
    status: Optional[str]
    
class FBCalendar(object):
    
    def __init__(self, email, output: Output) -> None:
        self.output = output
        self.email = email
    
    '''
    .create_event(
            calendarId=body.calendarId, start_time=body.start_time, end_time=body.end_time, notyf=notyf)
            '''
    def create_event(self, 
        calendarId: str, 
        start_time: str, 
        end_time: str, 
        notyf: Notyf) -> CreatedEvent:
        # convert start_time string into iso_8601 datetime format
        stime = datetime.fromisoformat(start_time)
        etime = datetime.fromisoformat(end_time)
        event = {
            "summary": "Appointment",
            "calendarId": calendarId,
            "description": notyf.get_human_readable_message(),
            "status": "tentative",
            "customer": notyf.phoneNumber,
            "startTime": stime,
            "endTime": etime,
            "colorId": "8"
        }
        response = db_create_event(event, email=self.email, calendarId=calendarId)
        return CreatedEvent(calendarId=calendarId, eventId=response["id"], status=response["status"])
    
    def confirm_appointment(self, eventId: str, body) -> (dict,bool):
        appoint = db_update_event(self.email,
                                   calendarId=body.calendarId,
                                    eventId=eventId, body={
                                        "status": "confirmed",
                                        "colorId": 2
                                    })
        return appoint, appoint.get("status") == "confirmed"

    def cancel_appointment(self, eventId: str, body: CommonAppointmentRequest) -> bool:
        response = db_update_event(self.email,
            eventId=eventId, body={
                "status": "cancelled",
                "colorId": 3
            })
        return response.get("status") == "cancelled"
    
    async def _get_events(self) -> List[Any]:
        """
        This function returns the events between timeMin to timeMax for the calendars that are eligible to be considered for finding slots as determined by _calendar_eligibility_criteria().

        Returns:
            List[SlotHolder]: Returns a list where items of type https://developers.google.com/calendar/api/v3/reference/events#resource.
        """
        _calendars = {}
        cals = db_get_calendars(email=self.email)
        for c in cals:
            calendarId = c["calendarId"]
            _calendars[calendarId] = {"items": [], "timeZone": c["timeZone"], "calendarName": c["calendarName"]}
            _events = db_get_events(self.email, c["calendarId"], self.output.start_date, self.output.end_date)
            '''
            populate _calendars based on _events["calendarId"]
            so for unique calendarId, we will have a list of SlotHolder
            '''
            if _events:
                for event in _events:
                    calendarId = event["calendarId"]
                    # if calendarId not in _calendars:
                    #     _calendars[calendarId] = {"items": [], "timeZone": c["timeZone"], "calendarName": c["calendarName"]}
                    _calendars[calendarId]["items"].append(event)
        return _calendars
    
    async def find_available_slots(self) -> List[SlotHolder]:
        """
        This functions is the entry point, it makes use of all the other functions of the class to provide available slots.

        Returns:
            List[Slot]: List of available slots.
        """

        _calendars = await self._get_events()
        slots: List[SlotHolder] = []

        for x in _calendars:
            _slots = await SlotSearch(self.output, _calendars[x]["items"],
                                      _calendars[x]["timeZone"]).find_available_slots()
            slots.append(SlotHolder(
                calendarId=x,
                calendarName=_calendars[x]["calendarName"],
                items=_slots
            ))

        return slots
    
    async def get_calendars(self):
        cals = db_get_calendars(self.email)
        return cals

    async def create_calendar(self, body: CreateCalendarRequest):
        c = db_create_calendar(self.email, body)
        return c
    
    async def delete_calendar(self, calendarId: str):
        return db_delete_calendars(self.email, calendarId)
    
    async def update_appointment(self, eventId: str, body: UpdateAppointmentRequest) -> (dict, bool):
        appoint = db_update_event(self.email,
                                   calendarId=body.calendarId,
                                    eventId=eventId, body={
                                        "startTime": body.start_time,
                                        "endTime": body.end_time
                                    })
        return appoint, appoint.get("status") == "confirmed"
        pass
    
    async def get_calendar_events(self, calendarId, startTime, endTime)->List[Appointment]:
        appointments = db_get_events(self.email, calendarId, startTime, endTime)
        return appointments