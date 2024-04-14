from arrow import get
from fastapi.routing import APIRouter

from chatgpt import AIInterpreter
from common2 import get_business
from constants import date_format, date_format2
from fbcalendar import FBCalendar
from model import (
    Business,
    EventStatus,
    MinimalClientModel,
    SearchAppointmentRequest,
    SearchAppointmentResponse,
    SendNotyf,
    SetAppointmentRequest,
    SetAppointmentResponse,
    Subject,
)
from notyf import Notyf
from utils import cross_sync_business_and_client

router = APIRouter()


@router.get("/business")
def business_info(businessEmail: str) -> Business | None:
    return get_business(businessEmail=businessEmail)


async def handle_search(
    body: SearchAppointmentRequest, subject: Subject
) -> SearchAppointmentResponse:
    if subject.business is not None and subject.phone is not None:
        output = AIInterpreter().ask(q=body.request, current_time=body.currentTime)
        if output is not None:
            return SearchAppointmentResponse(
                success=True,
                slots=FBCalendar(subject.business, output).find_available_slots(),
                query=output,
            )
    return SearchAppointmentResponse(slots=[], query=None)


@router.post("/appointments/search")
async def search(body: SearchAppointmentRequest) -> SearchAppointmentResponse:
    subject = Subject(business=body.business, phone="")
    return await handle_search(body=body, subject=subject)


async def handle_create_appointment(
    body: SetAppointmentRequest, subject: Subject
) -> SetAppointmentResponse:
    if subject.business is not None and subject.phone is not None:
        fbc = FBCalendar(subject.business, None)
        c = fbc.get_calendar(calendarId=body.calendarId)
        if c is not None:
            notyf = Notyf(
                subject=subject,
                start_time=get(body.startTime).to(c.timeZone).format(date_format),
                end_time=get(body.endTime).to(c.timeZone).format(date_format),
                query=body.query,
            )
            de = fbc.create_event(
                calendarId=body.calendarId,
                start_time=body.startTime,
                end_time=body.endTime,
                notyf=notyf,
                description=body.description,
                status=EventStatus.confirmed
                if body.query is None
                else EventStatus.tentative,
            )
            if body.userPhone is not None:
                cross_sync_business_and_client(
                    business=subject.business,
                    user_phone=body.userPhone,
                    mcm=MinimalClientModel(name=body.name, phone=body.userPhone),
                )
            if de is not None:
                if (
                    de.calendarId is not None
                    and de.eventId is not None
                    and de.status is not None
                ):
                    _t3 = await notyf.notify(de=de, cal=c)
                    if _t3.result is not None and body.sendNotification is True:
                        await Notyf.send_fcm_messages(
                            sns=[
                                SendNotyf(
                                    title="Appointment booked",
                                    body=f"Your appointment was booked with {subject.business}, at {get(_t3.result.startTime).format(date_format2)}",
                                    data={},
                                    phoneNumber=subject.phone,
                                )
                            ]
                        )
                    return _t3
    return SetAppointmentResponse()


@router.post("/appointments")
async def create_appointment(body: SetAppointmentRequest) -> SetAppointmentResponse:
    subject = Subject(business=body.business, phone=body.userPhone)
    return await handle_create_appointment(body=body, subject=subject)
