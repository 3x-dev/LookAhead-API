from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, date, time

from pydantic.dataclasses import dataclass as pydantic_dataclass

"""
This module contains the model classes, pretty self explanatory.
"""


@dataclass
class AppointmentType:
    _type: str
    duration: int
    _break: int


@pydantic_dataclass
@dataclass
class Output:
    appointment_type: str
    start_date: str
    end_date: str
    start_time: str
    end_time: str
    user_request: str

@pydantic_dataclass
@dataclass
class OutputDate:
    appointment_type: str
    start_date: date
    end_date: date
    start_time: time
    end_time: time
    user_request: str

@dataclass
class Event:
    event_id: str
    start_at: int
    end_at: int


@dataclass
class Slot:
    start_at: int
    end_at: int


@dataclass
class SlotStr:
    start_at: str
    end_at: str


@dataclass
class CommonResponse:
    success: bool


@dataclass
class GetAppointmentRequest:
    business: str
    request: str
    current_time: str


@dataclass
class SlotHolder:
    calendarId: str
    calendarName: str
    items: List[SlotStr]


@dataclass
class GetAppointmentResponse:
    success: bool
    slots: Optional[List[SlotHolder]]
    query: Optional[Output]


@dataclass
class SetAppointmentRequest:
    business: str
    calendarId: str
    start_time: str
    end_time: str
    query: Output


@dataclass
class SetAppointmentResponse:
    success: bool
    calendarId: Optional[str]
    eventId: Optional[str]
    status: Optional[str]


@dataclass
class CommonAppointmentRequest:
    calendarId: str
    eventId: str
    business: Optional[str] = field(default=None)
    user_phone: Optional[str] = field(default=None)


@dataclass
class UpdateAppointmentRequest:
    calendarId: str
    eventId: str
    start_time: Optional[datetime] = field(default=None)
    end_time: Optional[datetime] = field(default=None)


@dataclass
class Subject:
    business: str
    user_phone: str


@dataclass
class CommonDocument:
    business: str
    msg: str
    onUTCMins: str
    sentUTCMins: str
    reminder_lead_mins: str
    state: str
    phoneNumber: str
    phoneNumber: str
    msg_full_text: str
    calendarId: str
    calendarEventId: str
    calendarStatus: str
    docPath: str
    otherDocPath: str
    query: Output

@dataclass
class BusinessCalendar:
    calendarId: str
    calendarName: str
    timeZone: str
    opens: time
    closes: time
    daysOpen: List[int]
    description: str
    
@dataclass
class GetCalendarsResponse:
    items: List[BusinessCalendar]

@dataclass    
class CreateCalendarRequest:
    calendarName: str
    timeZone: str
    opens: str
    closes: str
    daysOpen: List[int]
    description: str
    
@dataclass    
class DeleteCalendarResponse:
    message: str
    status: str

@dataclass    
class CreateCalendarResponse:
    calendar: BusinessCalendar
    
@dataclass 
class Appointment:
    eventId: str
    colorId: int
    customer: str
    description: str
    startTime: datetime
    endTime: datetime
    status: str
    summary: str
