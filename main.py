from asyncio import create_task, gather
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from time import time
from typing import Annotated, Any, Dict, List

from arrow import get
from fastapi import FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from firebase_admin import auth
from google.cloud.firestore import Query
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import TypeAdapter
from starlette.exceptions import HTTPException
from starlette.status import __all__

from common import generate_id
from common2 import find_subject
from constants import date_format, date_format2
from database import fsdb
from embed import handle_create_appointment, handle_search
from embed import router as embed_router
from fbcalendar import FBCalendar, get_events
from model import (
    CalendarResponse,
    ClientModel,
    ClientModelResponse,
    ClientsModelResponse,
    CommonResponse,
    DatabaseCalendar,
    DatabaseEvent,
    EventResponse,
    EventStatus,
    FcmResultResponse,
    GetAppointmentsResponse,
    GetCalendarsResponse,
    MessagingRequest,
    MinimalClientModel,
    SearchAppointmentRequest,
    SearchAppointmentResponse,
    SendNotificationRequest,
    SendNotyf,
    SetAppointmentRequest,
    SetAppointmentResponse,
    Subject,
    Todo,
    TodoBase,
    TodoBaseUpdate,
    TodoListResponse,
    TodoResponse,
    UpdatableClientModel,
    UpdateAppointmentRequestExtras,
    UpdateCalendarRequest,
)
from notyf import Notyf
from um import router as um_router
from utils import cross_sync_business_and_client

app = FastAPI(
    title="Lookahead API",
    summary="Provides API to interact with AI to book appointments",
)

embed = "/embed"


def add_cors_headers(response: Response) -> Response:
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


async def catch_all(
    _: Request,
    e: HTTPException | RequestValidationError | ResponseValidationError | Any,
) -> Response:
    resp = CommonResponse()
    if type(e) == HTTPException:
        resp.message = e.detail
    elif type(e) == RequestValidationError or type(e) == ResponseValidationError:
        resp.message = TypeAdapter(List[Dict]).validate_python(eval(str(e)))
    return add_cors_headers(JSONResponse(content=asdict(resp)))


app = FastAPI(
    exception_handlers={
        key: catch_all
        for key in list(
            filter(lambda y: y != 200, map(lambda x: int(x.split("_")[1]), __all__))
        )
    }
)


@app.middleware("http")
async def auth_mw(request: Request, call_next):
    """
    This function is a middleware for the fast api application.
    It verifies the accesskey in the header and if it is valid then it adds the decoded token to the request state.
    """
    if request.url.path in ["/docs", "/openapi.json"] or request.url.path.startswith(
        embed
    ):
        response = await call_next(request)
        return add_cors_headers(response=response)
    accesskey = request.headers.get("accesskey")
    if accesskey is not None:
        try:
            decoded_token = auth.verify_id_token(accesskey)
            request.state.decoded_token = decoded_token
            response = await call_next(request)
            return add_cors_headers(response=response)
        except Exception as e:
            return add_cors_headers(
                response=JSONResponse(
                    content=asdict(CommonResponse(message="Error: " + str(e)))
                )
            )
    else:
        return add_cors_headers(
            JSONResponse(
                content=asdict(
                    CommonResponse(message="Auth error, double check your token!")
                )
            )
        )


@app.post("/calendars")
async def create_calendar(
    request: Request, accesskey: Annotated[str | None, Header()], body: DatabaseCalendar
) -> CalendarResponse:
    body.calendarId = generate_id()
    subject = await find_subject(request=request)
    _ = get(0, tzinfo=body.timeZone)
    calendar = (
        FBCalendar(subject.business, None).create_calendar(body)
        if subject.business is not None
        else None
    )
    return CalendarResponse(success=calendar is not None, calendar=calendar)


@app.get("/calendars")
async def get_calendars(
    request: Request, accesskey: Annotated[str | None, Header()]
) -> GetCalendarsResponse:
    subject = await find_subject(request=request)
    return GetCalendarsResponse(
        success=True,
        items=FBCalendar(subject.business, None).get_calendars()
        if subject.business is not None
        else [],
    )


@app.put("/calendars/{calendarId}")
async def update_calendar(
    request: Request,
    accesskey: Annotated[str | None, Header()],
    calendarId: str,
    body: UpdateCalendarRequest,
) -> CalendarResponse:
    subject = await find_subject(request=request)
    if body.timeZone is not None:
        _ = get(0, tzinfo=body.timeZone)
    calendar = (
        FBCalendar(subject.business, None).update_calendar(
            calendarId=calendarId, body=body
        )
        if subject.business is not None
        else None
    )
    return CalendarResponse(success=calendar is not None, calendar=calendar)


@app.delete("/calendars/{calendarId}")
async def delete_calendar(
    request: Request, accesskey: Annotated[str | None, Header()], calendarId: str
) -> CommonResponse:
    subject = await find_subject(request=request)
    return CommonResponse(
        success=(FBCalendar(subject.business, None).delete_calendar(calendarId) is None)
        if subject.business is not None
        else False
    )


@app.get("/calendars/{calendarId}/appointments")
async def get_appointments(
    request: Request,
    accesskey: Annotated[str | None, Header()],
    calendarId: str,
    startDate: datetime | str | int,
    endDate: datetime | str | int,
    status: EventStatus | None = None,
    email: str | None = None,
) -> GetAppointmentsResponse:
    subject = await find_subject(request=request)

    if subject.business is None:
        subject.business = email

    def _cast(z: str):
        try:
            return int(z)
        except Exception as _:
            return 0

    startDate = (
        _cast(startDate)
        if isinstance(startDate, str) and _cast(startDate) != 0
        else startDate
    )
    endDate = (
        _cast(endDate) if isinstance(endDate, str) and _cast(endDate) != 0 else endDate
    )

    if subject.business is not None:
        events: List[DatabaseEvent] = get_events(
            email=subject.business,
            calendarId=calendarId,
            start_date=get(startDate),
            end_date=get(endDate),
            status=status,
            user_phone=subject.phone,
        )
        return GetAppointmentsResponse(success=len(events) > 0, items=events)
    return GetAppointmentsResponse(items=[])


@app.post("/appointments/search")
async def search(
    request: Request,
    accesskey: Annotated[str | None, Header()],
    body: SearchAppointmentRequest,
) -> SearchAppointmentResponse:
    subject = await find_subject(request=request)
    return await handle_search(body=body, subject=subject)


@app.post("/appointments")
async def create_appointment(
    request: Request,
    accesskey: Annotated[str | None, Header()],
    body: SetAppointmentRequest,
) -> SetAppointmentResponse:
    subject = await find_subject(request=request)
    return await handle_create_appointment(body=body, subject=subject)


@app.put("/appointments/{calendarId}/update/{eventId}")
async def update_appointment(
    request: Request,
    accesskey: Annotated[str | None, Header()],
    calendarId: str,
    eventId: str,
    body: UpdateAppointmentRequestExtras,
) -> EventResponse:
    subject = await find_subject(request=request)
    if subject.business is not None:
        fbc = FBCalendar(subject.business, None)
        event = fbc.update_event(calendarId, eventId, body=body)
        if event is not None:
            update_data = {}

            update_data["calendarStatus"] = "updated"

            if (
                body.status == EventStatus.confirmed
                or body.status == EventStatus.cancelled
            ):
                update_data["calendarStatus"] = body.status

            if body.startTime is not None and body.endTime is not None:
                update_data["onUTCMins"] = (
                    get(body.startTime).to("+00:00").format(date_format2)
                )

            Notyf.update(subject.business, calendarId, eventId, update_data)

            if body.customer is not None and event.customer != body.customer:
                """
                If we want to update the phone number then first in regards to the appointment document only that particular field be updated and nothing else
                Secondly, a new client has to be added, don't do anything for the client already previous added for the wrong number
                Study create appointment source code
                """
                event.customer = body.customer
                cross_sync_business_and_client(
                    business=subject.business, user_phone=event.customer
                )
                _event = fbc.update_event_extras(
                    calendarId,
                    eventId,
                    body=UpdateAppointmentRequestExtras(
                        business=body.business,
                        customer=event.customer,
                        description=body.description,
                    ),
                )
                if _event is not None:
                    c = fbc.get_calendar(calendarId=_event.calendarId)
                    if c is not None:
                        notyf = Notyf(
                            subject=Subject(
                                business=subject.business, phone=_event.customer
                            ),
                            start_time=get(_event.startTime)
                            .to(c.timeZone)
                            .format(date_format),
                            end_time=get(_event.endTime)
                            .to(c.timeZone)
                            .format(date_format),
                            query=None,
                        )
                        _ = await notyf.notify(de=_event, cal=c)
                        return EventResponse(success=True, event=_event)
            return EventResponse(success=True, event=event)
    return EventResponse(event=None)


async def get_client_and_lastLogin(
    business: str, user_phone: str, cm: ClientModel | None = None
) -> ClientModel:
    async def step1():
        nonlocal cm
        if cm is None:
            cm = TypeAdapter(ClientModel).validate_python(
                fsdb.document(f"businesses/{business}/clients/{user_phone}")
                .get()
                .to_dict()
            )

    lastLogin: str | None = None

    async def step2():
        nonlocal lastLogin
        _t1 = fsdb.document(f"users/{user_phone}").get().to_dict()
        if _t1 is not None:
            lastLogin = _t1.get("last_login")

    tasks = [create_task(step1()), create_task(step2())]
    _ = await gather(*tasks)

    assert cm is not None

    if lastLogin is not None:
        cm.lastLogin = lastLogin

    return cm


@app.post("/sendNotification")
async def send_notification(
    request: Request,
    accesskey: Annotated[str | None, Header()],
    body: SendNotificationRequest,
) -> FcmResultResponse:
    return FcmResultResponse(
        success=True, result=await Notyf.send_fcm_messages(sns=body.to)
    )


@app.post("/clientManagement")
async def create_client(
    request: Request,
    accesskey: Annotated[str | None, Header()],
    body: MinimalClientModel,
) -> ClientModelResponse | None:
    subject = await find_subject(request=request)
    if subject.business is not None:
        cross_sync_business_and_client(
            business=subject.business, user_phone=body.phone, mcm=body
        )
        return ClientModelResponse(
            success=True,
            client=await get_client_and_lastLogin(
                business=subject.business, user_phone=body.phone
            ),
        )
    return None


@app.put("/clientManagement/{client_phone}")
async def update_client(
    request: Request,
    accesskey: Annotated[str | None, Header()],
    client_phone: str,
    body: UpdatableClientModel,
) -> ClientModelResponse | None:
    subject = await find_subject(request=request)
    if subject.business is not None:
        doc_path = f"businesses/{subject.business}/clients/{client_phone}"
        fsdb.document(doc_path).update(
            TypeAdapter(UpdatableClientModel).dump_python(body, exclude_none=True)
        )
        return ClientModelResponse(
            success=True,
            client=await get_client_and_lastLogin(
                business=subject.business, user_phone=client_phone
            ),
        )
    return None


@app.get("/clientManagement/{client_phone}")
async def get_client(
    request: Request, accesskey: Annotated[str | None, Header()], client_phone: str
) -> ClientModelResponse | None:
    subject = await find_subject(request=request)
    if subject.business is not None:
        return ClientModelResponse(
            success=True,
            client=await get_client_and_lastLogin(
                business=subject.business, user_phone=client_phone
            ),
        )
    return None


@app.get("/clientManagement")
async def get_clients(
    request: Request, accesskey: Annotated[str | None, Header()], limit: int = 100
) -> ClientsModelResponse | None:
    if limit > 100:
        limit = 100
    subject = await find_subject(request=request)
    if subject.business is not None:
        col_path = f"businesses/{subject.business}/clients"
        _t1 = fsdb.collection(col_path).limit(limit).get()
        tasks = []
        for z in _t1:
            cm = TypeAdapter(ClientModel).validate_python(z.to_dict())
            tasks.append(
                create_task(
                    get_client_and_lastLogin(
                        business=subject.business, user_phone=cm.phone, cm=cm
                    )
                )
            )
        _t2: List[ClientModel] = await gather(*tasks)
        clients = list(
            sorted(
                list(filter(lambda z: z.phone != "+10000000000", _t2)),
                key=lambda z: z.phone,
            )
        )
        return ClientsModelResponse(success=True, clients=clients)
    return None


@app.delete("/clientManagement/{client_phone}")
async def delete_client(
    request: Request, accesskey: Annotated[str | None, Header()], client_phone: str
) -> CommonResponse:
    subject = await find_subject(request=request)
    if subject.business is not None:
        doc_path = f"businesses/{subject.business}/clients/{client_phone}"
        doc_ref = fsdb.document(doc_path)
        fsdb.recursive_delete(doc_ref)
        fsdb.document(f"users/{client_phone}/businesses/{subject.business}").delete()
        return CommonResponse(success=True)
    return CommonResponse(success=False)


@app.post("/messaging")
async def create_messaging(
    request: Request, accesskey: Annotated[str | None, Header()], body: MessagingRequest
) -> CommonResponse:
    subject = await find_subject(request=request)
    if subject.business is not None:
        send_everyone = False

        def get_phone_numbers_by_group(group: str) -> List[str]:
            return list(
                map(
                    lambda x: x.id,
                    fsdb.collection(f"businesses/{subject.business}/clients")
                    .where(filter=FieldFilter("group", "==", group))
                    .get(),
                )
            )

        phone_numbers = body.client_phone_numbers
        if "+10000000000" in phone_numbers:
            send_everyone = True
            body.group_names = []

        for x in body.group_names:
            phone_numbers.extend(get_phone_numbers_by_group(x))

        if send_everyone is True:
            phone_numbers = []
            for z in (
                fsdb.collection(f"businesses/{subject.business}/clients")
                .limit(1000)
                .get()
            ):
                phone_numbers.append(z.id)

        phone_numbers = list(sorted(list(set(phone_numbers))))

        async def add_msg_and_send_fcm_notification(phone_number: str):
            msg_id = generate_id()
            dp1 = f"businesses/{subject.business}/clients/{phone_number}/messages/{msg_id}"
            dp2 = f"users/{phone_number}/messages/{msg_id}"
            _d = {
                "business": subject.business,
                "client": phone_number,
                "msg": body.msg,
                "onUTCMins": get(body.onUTCMins).to("+00:00").format(date_format2),
                "reminder_lead_mins": str(body.reminder_lead_mins),
                "sentUTCMins": get(int(time())).to("+00:00").format(date_format2),
                "state": "UNREAD",
            }
            fsdb.document(dp1).set(_d)
            fsdb.document(dp2).set(_d)

        tasks = []
        for z in phone_numbers:
            tasks.append(create_task(add_msg_and_send_fcm_notification(z)))
        _ = await gather(*tasks)

        await Notyf.send_fcm_messages(
            sns=list(
                map(
                    lambda z: SendNotyf(
                        title="New notification", body=body.msg, data={}, phoneNumber=z
                    ),
                    phone_numbers,
                )
            )
        )

        return CommonResponse(success=True)
    return CommonResponse(success=False)


def todo_format(todo: Todo) -> Todo:
    _c = deepcopy(todo)
    _c.createdUTCMins = get(_c.createdUTCMins).to("+00:00").format(date_format2)
    _c.updatedUTCMins = get(_c.updatedUTCMins).to("+00:00").format(date_format2)
    return _c


@app.post("/todo")
async def todo_create(
    request: Request, accesskey: Annotated[str | None, Header()], body: TodoBase
) -> TodoResponse:
    subject = await find_subject(request=request)
    if subject.phone is not None:
        _t2 = get(int(time())).to("+00:00")
        if subject.phone in body.collaborators:
            body.collaborators.remove(subject.phone)
        _t1 = TypeAdapter(Todo).validate_python(
            Todo(
                todoID=generate_id(),
                creator=subject.phone,
                createdUTCMins=int(_t2.timestamp()),
                updatedUTCMins=int(_t2.timestamp()),
                **asdict(body),
            )
        )
        fsdb.document(f"ToDos/{_t1.todoID}").set(asdict(_t1))
        return TodoResponse(success=True, result=todo_format(_t1))
    return TodoResponse(success=False)


@app.get("/todo")
async def todo_read_all(
    request: Request, accesskey: Annotated[str | None, Header()]
) -> TodoListResponse:
    subject = await find_subject(request=request)
    if subject.phone is not None:
        created_ones = (
            fsdb.collection("ToDos")
            .where(filter=FieldFilter("creator", "==", subject.phone))
            .order_by("updatedUTCMins", direction=Query.DESCENDING)
            .limit(50)
            .get()
        )
        collab_ones = (
            fsdb.collection("ToDos")
            .where(filter=FieldFilter("collaborators", "array_contains", subject.phone))
            .order_by("updatedUTCMins", direction=Query.DESCENDING)
            .limit(50)
            .get()
        )

        _t1 = list(
            map(
                lambda z: TypeAdapter(Todo).validate_python(z.to_dict()),
                created_ones + collab_ones,
            )
        )
        unq_todos = list({todo.todoID: todo for todo in _t1}.values())
        unq_todos.sort(key=lambda z: z.updatedUTCMins, reverse=True)
        return TodoListResponse(
            success=True, result=list(map(lambda z: todo_format(z), unq_todos))
        )
    return TodoListResponse(success=False)


@app.put("/todo/{todoID}")
async def todo_update(
    request: Request,
    accesskey: Annotated[str | None, Header()],
    todoID: str,
    body: TodoBaseUpdate,
) -> TodoResponse:
    subject = await find_subject(request=request)
    if subject.phone is not None:
        doc_ref = f"ToDos/{todoID}"
        _t2 = fsdb.document(doc_ref).get().to_dict()
        _t3 = TypeAdapter(Todo).validate_python(_t2) if _t2 is not None else None
        if _t3 is not None and (
            _t3.creator == subject.phone or subject.phone in _t3.collaborators
        ):
            if body.collaborators is not None:
                if _t3.creator in body.collaborators:
                    body.collaborators.remove(_t3.creator)
                body.collaborators = list(set(body.collaborators))
            fsdb.document(doc_ref).update(
                {
                    **TypeAdapter(TodoBaseUpdate).dump_python(body, exclude_none=True),
                    **{"updatedUTCMins": int(time())},
                }
            )
            _t1 = fsdb.document(doc_ref).get().to_dict()
            return TodoResponse(
                success=True,
                result=todo_format(TypeAdapter(Todo).validate_python(_t1))
                if _t1 is not None
                else None,
            )
    return TodoResponse(success=False)


@app.delete("/todo/{todoID}")
async def todo_delete(
    request: Request, accesskey: Annotated[str | None, Header()], todoID: str
) -> CommonResponse:
    subject = await find_subject(request=request)
    if subject.phone is not None:
        doc_ref = f"ToDos/{todoID}"
        _t2 = fsdb.document(doc_ref).get().to_dict()
        _t3 = TypeAdapter(Todo).validate_python(_t2) if _t2 is not None else None
        if _t3 is not None and (
            _t3.creator == subject.phone or subject.phone in _t3.collaborators
        ):
            fsdb.document(doc_ref).delete()
            return CommonResponse(success=True)
    return CommonResponse(success=False)


app.include_router(embed_router, prefix=embed)
app.include_router(um_router, prefix="/um")
