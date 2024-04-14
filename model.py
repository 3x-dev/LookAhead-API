from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from time import time
from typing import Annotated, Dict, List, Optional

from phonenumbers import is_valid_number, parse
from pydantic import EmailStr
from pydantic.dataclasses import dataclass as pydantic_dataclass

from common import generate_id


@dataclass
class SendNotyf:
    title: str
    body: str
    data: Dict
    phoneNumber: str | None = field(default=None)


@dataclass
class FcmResult:
    phoneNumber: str | None
    totalTokens: int
    successCount: int
    failureCount: int


@pydantic_dataclass
class Output:
    appointmentType: str
    startDate: str
    endDate: str
    startTime: str
    endTime: str
    userRequest: str


@dataclass
class Subject:
    business: str | None
    phone: str | None
    secondaryUserEmail: str | None = None


@dataclass
class CommonDocument:
    business: str
    msg: str
    onUTCMins: str
    sentUTCMins: str
    reminderLeadMins: str
    state: str
    phoneNumber: str
    msgFullText: str
    calendarId: str
    calendarEventId: str
    calendarStatus: str
    calendarName: str
    calendarTimeZone: str
    docPath: str
    otherDocPath: str
    query: Output | None


@dataclass
class DatabaseCalendar:
    calendarName: str
    timeZone: str
    opens: str
    closes: str
    daysOpen: List[bool]
    description: str
    durationMins: int
    breakMins: int
    calendarId: str = field(default_factory=generate_id)


class EventStatus(StrEnum):
    tentative = "tentative"
    confirmed = "confirmed"
    cancelled = "cancelled"


@dataclass
class DatabaseEvent:
    calendarId: str
    summary: str
    description: str
    status: EventStatus
    customer: str
    startTime: int
    endTime: int
    eventId: str = field(default_factory=generate_id)


@dataclass
class Event:
    eventId: str
    startTime: int
    endTime: int


@dataclass
class Slot:
    startTime: int
    endTime: int


@dataclass
class SlotHolder:
    calendarId: str
    calendarName: str
    timeZone: str
    opens: str
    closes: str
    items: List[Slot]


@dataclass(kw_only=True)
class CommonResponse:
    success: bool = field(default=False)
    message: str | List[Dict] | None = field(default=None)


@dataclass
class CalendarResponse(CommonResponse):
    calendar: DatabaseCalendar | None


@dataclass
class GetCalendarsResponse(CommonResponse):
    items: List[DatabaseCalendar]


@dataclass
class UpdateCalendarRequest:
    calendarName: Optional[str] = None
    timeZone: Optional[str] = None
    opens: Optional[str] = None
    closes: Optional[str] = None
    daysOpen: Optional[List[bool]] = None
    description: Optional[str] = None
    durationMins: Optional[int] = None
    breakMins: Optional[int] = None


@dataclass
class GetAppointmentsResponse(CommonResponse):
    items: List[DatabaseEvent]


@dataclass(kw_only=True)
class SearchAppointmentRequest:
    business: str
    request: str
    currentTime: str


@dataclass
class SearchAppointmentResponse(CommonResponse):
    slots: List[SlotHolder]
    query: Optional[Output]


@dataclass(kw_only=True)
class SetAppointmentRequest:
    business: str
    calendarId: str
    startTime: int
    endTime: int
    query: Output | None
    userPhone: str | None = None
    description: str | None = None
    name: str | None = None
    sendNotification: bool = True


@dataclass
class SetAppointmentResponse(CommonResponse):
    result: DatabaseEvent | None = None


@dataclass(kw_only=True)
class UpdateAppointmentRequest:
    business: str
    status: Optional[EventStatus] = None
    startTime: Optional[datetime | str | int] = None
    endTime: Optional[datetime | str | int] = None


def validate_phone_number(value: Optional[str]) -> Optional[str]:
    if value is not None:
        _t = parse(value)
        if is_valid_number(_t) is False:
            return None
    return value


@dataclass
class UpdateAppointmentRequestExtras(UpdateAppointmentRequest):
    customer: Annotated[Optional[str], validate_phone_number] = None
    description: str | None = None


@dataclass
class EventResponse(CommonResponse):
    event: DatabaseEvent | None


@dataclass(kw_only=True)
class SendNotificationRequest:
    to: List[SendNotyf]


@dataclass
class FcmResultResponse(CommonResponse):
    result: List[FcmResult]


@pydantic_dataclass
class UpdatableClientModel:
    name: str | None = None
    email: str | None = None
    group: str | None = None


@pydantic_dataclass(kw_only=True)
class MinimalClientModel(UpdatableClientModel):
    phone: str


@pydantic_dataclass(kw_only=True)
class ClientModel(MinimalClientModel):
    lastLogin: str = field(default="11/11/1111")
    createTimeUTCSecs: int = field(
        default_factory=(lambda: int(datetime.now().timestamp()))
    )


@pydantic_dataclass
class ClientModelResponse(CommonResponse):
    client: ClientModel | None = None


@pydantic_dataclass
class ClientsModelResponse(CommonResponse):
    clients: List[ClientModel] | None = None


@pydantic_dataclass(kw_only=True)
class MessagingRequest:
    msg: str
    onUTCMins: int = field(default_factory=lambda: int(time()))
    reminder_lead_mins: int = field(default=0)
    client_phone_numbers: List[str] = field(default_factory=list)
    group_names: List[str] = field(default_factory=list)


class TodoStatus(StrEnum):
    PENDING = "PENDING"
    ARCHIVED = "ARCHIVED"
    BLOCKED = "BLOCKED"
    DONE = "DONE"


@pydantic_dataclass(kw_only=True)
class TodoBase:
    collaborators: List[str] = field(default_factory=lambda: [])
    msg: str
    onUTCMins: str
    reminder_lead_mins: str = field(default="15")
    note: str
    status: TodoStatus


@pydantic_dataclass(kw_only=True)
class TodoBaseUpdate:
    collaborators: List[str] | None = None
    msg: str | None = None
    onUTCMins: str | None = None
    reminder_lead_mins: str | None = None
    note: str | None = None
    status: TodoStatus | None = None


@pydantic_dataclass(kw_only=True)
class Todo(TodoBase):
    todoID: str
    creator: str
    createdUTCMins: str | int
    updatedUTCMins: str | int


@dataclass
class TodoResponse(CommonResponse):
    result: Todo | None = None


@dataclass
class TodoListResponse(CommonResponse):
    result: List[Todo] | None = None


@dataclass
class Business:
    docID: str
    email: str
    business: str
    name: str = ""
    address: str = ""
    imageURL: str = ""
    type_: str = field(metadata={"asdict_key": "type"}, default="BusinessType.other")


class BusinessUserRole(StrEnum):
    Admin = "Admin"
    Manager = "Manager"
    Billing = "Billing"
    Staff = "Staff"


@pydantic_dataclass
class BusinessUser:
    email: str
    business: str
    roles: List[BusinessUserRole]


@pydantic_dataclass
class CreateUserRequest:
    email: EmailStr
    roles: List[BusinessUserRole] = field(
        default_factory=lambda: [BusinessUserRole.Admin]
    )


@pydantic_dataclass
class BusinessUserListResponse(CommonResponse):
    result: List[BusinessUser] = field(default_factory=lambda: [])


@pydantic_dataclass
class BusinessListResponse(CommonResponse):
    result: List[Business] = field(default_factory=lambda: [])
