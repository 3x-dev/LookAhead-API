from dataclasses import asdict
from typing import Annotated, Any, List

from arrow import get
from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from firebase_admin import auth
from datetime import datetime
#from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.cors import CORSMiddleware

from chatgpt import AIInterpreter
from constants import iso_8601
from database import get_rt_from_db
from exceptions import AppException
from fbcalendar import FBCalendar
from gcalendar import GCalendar
from model import (Appointment, CommonAppointmentRequest, CommonResponse, CreateCalendarRequest, CreateCalendarResponse, DeleteCalendarResponse,
                   GetAppointmentRequest, GetAppointmentResponse, GetCalendarsResponse,
                   SetAppointmentRequest, SetAppointmentResponse, Subject,
                   UpdateAppointmentRequest)
from notyf import Notyf

"""
This module is the entry point of the application.
"""

app = FastAPI(title="Lookahead API",
              summary="Provides API to interact with AI to book appointments")

def add_cors_headers(response: Any):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"

@app.middleware("http")
async def auth_mw(request: Request, call_next):
    """
    This function is a middleware for the fast api application.
    It verifies the accesskey in the header and if it is valid then it adds the decoded token to the request state.

    Args:
        request (Request): The request.
        call_next: Next fuction.
    """
    if request.url.path in ["/docs", "/openapi.json"]:
        response = await call_next(request)
        add_cors_headers(response)
        return response
    accesskey = request.headers.get("accesskey")
    if accesskey is not None:
        try:
            decoded_token = auth.verify_id_token(accesskey)
            request.state.decoded_token = decoded_token
            response = await call_next(request)
            add_cors_headers(response)
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"message": "Error: "+str(e)}
            )
    else:
        return JSONResponse(
                status_code=403,
                content={"message": "Error: accesskey is not set"}
            )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # allow all methods
    allow_headers=["*"],  # allow all headers
)

@app.post("/getAppointment")
async def GetAppointment(request: Request, accesskey: Annotated[str | None, Header()], body: GetAppointmentRequest) -> GetAppointmentResponse:
    output = AIInterpreter()._ask(q=body.request, current_time=body.current_time)
    if output is not None:
        phoneNumber = request.state.decoded_token.get("phone_number")
        phoneNumber = request.state.decoded_token.get(
            "phoneNumber") if phoneNumber is None else phoneNumber
        if phoneNumber is not None:
            bzz_refreshToken = get_rt_from_db(email=body.business)
            if bzz_refreshToken is not None:
                return GetAppointmentResponse(success=True, slots=await GCalendar(bzz_refreshToken, output).find_available_slots(), query=output)
    return GetAppointmentResponse(success=False, slots=[], query=None)


@app.post("/setAppointment")
async def SetAppointment(request: Request, accesskey: Annotated[str | None, Header()], body: SetAppointmentRequest) -> SetAppointmentResponse:
    phoneNumber = request.state.decoded_token.get("phone_number")
    phoneNumber = request.state.decoded_token.get(
        "phoneNumber") if phoneNumber is None else phoneNumber
    if phoneNumber is not None:
        bzz_refreshToken = get_rt_from_db(email=body.business)
        if bzz_refreshToken is not None:
            notyf = Notyf(subject=Subject(business=body.business, user_phone=phoneNumber),
                          start_time=body.start_time, end_time=body.end_time, query=body.query)
            ce = GCalendar(bzz_refreshToken, None).create_event(
                calendarId=body.calendarId, start_time=body.start_time, end_time=body.end_time, summary=notyf.get_human_readable_message())
            if ce.calendarId is not None and ce.eventId is not None and ce.status is not None:
                return notyf.notify(ce=ce)
    return SetAppointmentResponse(success=False, calendarId=None, eventId=None, status=None)


def find_subject(body: CommonAppointmentRequest, decoded_token: Any) -> Subject:
    business = decoded_token.get("email")
    if business is None:
        business = body.business if body.business is not None else None
    user_phone = decoded_token.get("phone_number")
    user_phone = decoded_token.get(
        "phoneNumber") if user_phone is None else user_phone
    if user_phone is None:
        user_phone = body.user_phone
    return Subject(business=business, user_phone=user_phone)


@app.post("/confirmAppointment")
async def ConfirmAppointment(request: Request, accesskey: Annotated[str | None, Header()], body: CommonAppointmentRequest) -> CommonResponse:
    subject = find_subject(
        body=body, decoded_token=request.state.decoded_token)
    if subject.business is not None:
        bzz_refreshToken = get_rt_from_db(email=subject.business)
        if bzz_refreshToken is not None:
            if GCalendar(bzz_refreshToken, None).confirm_appointment(body=body):
                return Notyf(subject, None, None, None).update(body=body, update_data={"calendarStatus": "confirmed"})
    return CommonResponse(success=False)


@app.post("/updateAppointment")
async def UpdateAppointment(request: Request, accesskey: Annotated[str | None, Header()], body: UpdateAppointmentRequest) -> CommonResponse:
    subject = find_subject(
        body=body, decoded_token=request.state.decoded_token)
    if subject.business is not None:
        bzz_refreshToken = get_rt_from_db(email=subject.business)
        if bzz_refreshToken is not None:
            if GCalendar(bzz_refreshToken, None).update_appointment(body=body):
                return Notyf(subject, body.start_time, body.end_time, None).update(body, {
                    "calendarStatus": "updated",
                    "onUTCMins": get(body.start_time, iso_8601).to("+00:00").format("YYYY-MM-DD h:mm A")
                })
    return CommonResponse(success=False)


@app.post("/deleteAppointment")
async def DeleteAppointment(request: Request, accesskey: Annotated[str | None, Header()], body: CommonAppointmentRequest) -> CommonResponse:
    subject = find_subject(
        body=body, decoded_token=request.state.decoded_token)
    if subject.business is not None:
        bzz_refreshToken = get_rt_from_db(email=subject.business)
        if bzz_refreshToken is not None:
            if GCalendar(bzz_refreshToken, None).cancel_appointment(body=body):
                return Notyf(subject, None, None, None).update(body=body, update_data={"calendarStatus": "cancelled"})
    return CommonResponse(success=False)


'''
output = {{
  "appointment_type": "hygienist",
  "start_date": "<FIGURE OUT THE 1ST DAY OF CURRENT MONTH>",
  "end_date": "<FIGURE OUT THE LAST DAY OF CURRENT MONTH>",
  "start_time": "05:00",
  "end_time": "11:59"
}}
'''
@app.post("/appointments/search", tags=["Appointments (for Businesses and Customers)"])
async def search(request: Request, accesskey: Annotated[str | None, Header()], body: GetAppointmentRequest) -> GetAppointmentResponse:
    subject = find_subject(
        body=body, decoded_token=request.state.decoded_token)
    output = AIInterpreter()._ask(q=body.request, current_time=body.current_time)
    if output is not None:
        phoneNumber = request.state.decoded_token.get("phone_number")
        phoneNumber = request.state.decoded_token.get(
            "phoneNumber") if phoneNumber is None else phoneNumber
        if phoneNumber is not None:
            return GetAppointmentResponse(success=True, slots=await FBCalendar(subject.business, output).find_available_slots(), query=output)
    return GetAppointmentResponse(success=False, slots=[], query=None)

@app.post("/appointments", tags=["Appointments (for Businesses and Customers)"])
async def create(request: Request, accesskey: Annotated[str | None, Header()], body: SetAppointmentRequest) -> SetAppointmentResponse:
    subject = find_subject(
        body=body, decoded_token=request.state.decoded_token)
    phoneNumber = request.state.decoded_token.get("phone_number")
    phoneNumber = request.state.decoded_token.get(
        "phoneNumber") if phoneNumber is None else phoneNumber
    if phoneNumber is not None:
        notyf = Notyf(subject=Subject(business=subject.business, user_phone=phoneNumber),
                        start_time=body.start_time, end_time=body.end_time, query=body.query)
        ce = FBCalendar(subject.business, None).create_event(
            calendarId=body.calendarId, start_time=body.start_time, end_time=body.end_time, notyf=notyf)
        if ce.calendarId is not None and ce.eventId is not None and ce.status is not None:
            return notyf.notify(ce=ce)
    return SetAppointmentResponse(success=False, calendarId=None, eventId=None, status=None)

@app.put("/appointments/{eventId}/update", tags=["Appointments (for Businesses and Customers)"])
async def update(eventId: str, request: Request, accesskey: Annotated[str | None, Header()], body: UpdateAppointmentRequest) -> CommonResponse:
    subject = find_subject(
        body=body, decoded_token=request.state.decoded_token)
    print(f"PUT /appointments/{eventId}/update for business: {subject.business}")
    if subject.business is not None:
        appoint, status = FBCalendar(subject.business, None).update_appointment(eventId, body=body)
        if status:
            return Notyf(subject, body.start_time, body.end_time, None).update(body, {
                "calendarStatus": "updated",
                "onUTCMins": get(body.start_time, iso_8601).to("+00:00").format("YYYY-MM-DD h:mm A")
            })
    return CommonResponse(success=False)

@app.put("/appointments/{eventId}/confirm", tags=["Appointments (for Businesses and Customers)"])
async def confirm(eventId: str, request: Request, accesskey: Annotated[str | None, Header()], body: CommonAppointmentRequest) -> CommonResponse:
    subject = find_subject(
        body=body, decoded_token=request.state.decoded_token)
    print(f"PUT /appointments/{eventId}/confirm for business: {subject.business}")
    if subject.business is not None:
        appoint, status = FBCalendar(subject.business, None).confirm_appointment(eventId, body=body)
        if status:
            return Notyf(subject, appoint["startTime"], appoint["endTime"], None).update(body, {
                "calendarStatus": "confirmed"
            })
    return CommonResponse(success=False)


@app.delete("/appointments/{eventId}", tags=["Appointments (for Businesses and Customers)"])
async def delete(eventId: str, request: Request, accesskey: Annotated[str | None, Header()], body: CommonAppointmentRequest) -> CommonResponse:
    subject = find_subject(
        body=body, decoded_token=request.state.decoded_token)
    print(f"DELETE /appointments/{eventId} for business: {subject.business}")
    if subject.business is not None:
        if FBCalendar(subject.business, None).cancel_appointment(eventId, body=body):
            return Notyf(subject, None, None, None).update(body=body, update_data={"calendarStatus": "cancelled"})
    return CommonResponse(success=False)

@app.post("/calendars", tags=["Calendars (for Businesses)"])
async def create_calendar(request: Request, accesskey: Annotated[str | None, Header()], body: CreateCalendarRequest) -> CreateCalendarResponse:
    decoded_token=request.state.decoded_token
    business = decoded_token.get("email")
    print(f"POST /calendars for business: {business}")
    return CreateCalendarResponse(success=True, calendar=await FBCalendar(business, None).create_calendar(body))

@app.get("/calendars", tags=["Calendars (for Businesses)"])
async def get_calendars(request: Request, accesskey: Annotated[str | None, Header()]) -> GetCalendarsResponse:
    try:
        decoded_token=request.state.decoded_token
        business = decoded_token.get("email")
        print(f"GET /calendars for business: {business}")
        return GetCalendarsResponse(success=True, items=await FBCalendar(business, None).get_calendars())
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"message": e}
        )

@app.get("/calendars/{calendarId}/appointments", tags=["Calendars (for Businesses)"])
async def get_appointments(request: Request, 
                          accesskey: Annotated[str | None, Header()], 
                          start_datetime: datetime,
                          end_datetime: datetime,
                          calendarId: str) -> List[Appointment]:
    decoded_token=request.state.decoded_token
    business = decoded_token.get("email")
    appointments: List[Appointment] = await FBCalendar(business, None).get_calendar_events(calendarId, start_datetime, end_datetime)
    return appointments


@app.delete("/calendars/{calendarId}", tags=["Calendars (for Businesses)"])
async def delete_calendar(request: Request, accesskey: Annotated[str | None, Header()], calendarId: str) -> DeleteCalendarResponse:
    decoded_token=request.state.decoded_token
    business = decoded_token.get("email")
    status = await FBCalendar(business, None).delete_calendar(calendarId)
    if status:
        message = "Deleted"
    else:
        message = "Falied to delete"
    return DeleteCalendarResponse(status=status, message=message)



    
    

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, port=8080)
#uvicorn main:app --reload --port 8080

