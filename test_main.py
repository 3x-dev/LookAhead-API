from copy import deepcopy
from dataclasses import asdict
from random import choice

from fastapi.testclient import TestClient
from jwt import decode as jwt_decode
from pydantic import TypeAdapter
from pytest import fixture

from common import generate_id
from database import SendNotyf
from la_token import bzz_uid, bzz_uid2, get_auth_tokens, user_uid, user_uid2
from main import app
from model import (
    BusinessListResponse,
    BusinessUserListResponse,
    CalendarResponse,
    ClientModel,
    ClientModelResponse,
    ClientsModelResponse,
    CommonResponse,
    CreateUserRequest,
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
    SetAppointmentRequest,
    SetAppointmentResponse,
    Todo,
    TodoBase,
    TodoBaseUpdate,
    TodoListResponse,
    TodoResponse,
    TodoStatus,
    UpdatableClientModel,
    UpdateAppointmentRequest,
    UpdateCalendarRequest,
)

client = TestClient(app=app)

bzz_headers = {"AccessKey": get_auth_tokens(uid=bzz_uid)[1]}

bzz_headers2 = {"AccessKey": get_auth_tokens(uid=bzz_uid2)[1]}

user_headers = {"AccessKey": get_auth_tokens(uid=user_uid)[1]}

user_headers2 = {"AccessKey": get_auth_tokens(uid=user_uid2)[1]}

calendar = DatabaseCalendar(
    calendarName="Test calendar",
    timeZone="Asia/Kolkata",
    opens="09:00",
    closes="17:00",
    daysOpen=[False, True, True, True, True, True, False],
    description="Python testing",
    durationMins=60,
    breakMins=10,
)

event: DatabaseEvent | None = None


@fixture(scope="session")
def business() -> str:
    return jwt_decode(bzz_headers["AccessKey"], options={"verify_signature": False})[
        "email"
    ]


@fixture(scope="session")
def business2() -> str:
    return jwt_decode(bzz_headers2["AccessKey"], options={"verify_signature": False})[
        "email"
    ]


@fixture(scope="session")
def phone_number() -> str:
    return jwt_decode(user_headers["AccessKey"], options={"verify_signature": False})[
        "phone_number"
    ]


@fixture(scope="session")
def phone_number2() -> str:
    return jwt_decode(user_headers2["AccessKey"], options={"verify_signature": False})[
        "phone_number"
    ]


def test_create_calendar():
    global calendar
    response = TypeAdapter(CalendarResponse).validate_python(
        client.post("/calendars", headers=bzz_headers, json=asdict(calendar)).json()
    )
    if response.calendar is not None:
        _t1 = asdict(calendar)
        del _t1["calendarId"]
        _t2 = asdict(deepcopy(response.calendar))
        del _t2["calendarId"]

        assert _t1 == _t2
        calendar.calendarId = response.calendar.calendarId


def test_get_calendars():
    response = TypeAdapter(GetCalendarsResponse).validate_python(
        client.get("/calendars", headers=bzz_headers).json()
    )
    assert len(response.items) > 0
    assert calendar.calendarId in list(map(lambda x: x.calendarId, response.items))


def test_update_calendar():
    global calendar
    _t = UpdateCalendarRequest(calendarName=f"New name - {generate_id()}")
    response = TypeAdapter(CalendarResponse).validate_python(
        client.put(
            f"/calendars/{calendar.calendarId}", headers=bzz_headers, json=asdict(_t)
        ).json()
    )
    assert response.success is True and response.calendar is not None
    calendar = response.calendar


def test_update_calendar2():
    global calendar
    _t = UpdateCalendarRequest(timeZone="Asia/Paris")
    response = TypeAdapter(CommonResponse).validate_python(
        client.put(
            f"/calendars/{calendar.calendarId}", headers=bzz_headers, json=asdict(_t)
        ).json()
    )
    assert response.success is False


def test_create_appointment(business):
    global calendar, event
    response = TypeAdapter(SearchAppointmentResponse).validate_python(
        client.post(
            "/appointments/search",
            headers=user_headers,
            json=asdict(
                TypeAdapter(SearchAppointmentRequest).validate_python(
                    {
                        "business": business,
                        "request": "book me an appointment with doctor next thursday anytime during the day",
                        "currentTime": "2026-12-15T10:50:00+05:30",
                    }
                )
            ),
        ).json()
    )

    assert response.success is True

    if response.success and response.query is not None:
        _t = list(filter(lambda x: x.calendarId == calendar.calendarId, response.slots))

        if len(_t) > 0:
            slot_holder = _t[0]
            slot = choice(slot_holder.items)

            response2 = TypeAdapter(SetAppointmentResponse).validate_python(
                client.post(
                    "/appointments",
                    headers=user_headers,
                    json=asdict(
                        SetAppointmentRequest(
                            business=business,
                            calendarId=slot_holder.calendarId,
                            startTime=slot.startTime,
                            endTime=slot.endTime,
                            query=response.query,
                        )
                    ),
                ).json()
            )

            assert response2.result is not None
            event = response2.result


def test_update_appointment(business):
    global event
    if event is not None:
        response = TypeAdapter(EventResponse).validate_python(
            client.put(
                f"/appointments/{event.calendarId}/update/{event.eventId}",
                headers=user_headers,
                json=asdict(
                    UpdateAppointmentRequest(
                        business=business, status=EventStatus.confirmed
                    )
                ),
            ).json()
        )

        assert response.success is True and response.event is not None
        event = response.event


def test_update_appointment2(business):
    global event
    if event is not None:
        response = TypeAdapter(EventResponse).validate_python(
            client.put(
                f"/appointments/{event.calendarId}/update/{event.eventId}",
                headers=user_headers,
                json=asdict(
                    UpdateAppointmentRequest(
                        business=business,
                        startTime=event.startTime + 60 * 60,
                        endTime=event.endTime + 60 * 60,
                    )
                ),
            ).json()
        )

        assert response.success is True and response.event is not None
        event = response.event


def test_get_appointments():
    global event
    if event is not None:
        response = TypeAdapter(GetAppointmentsResponse).validate_python(
            client.get(
                f"/calendars/{event.calendarId}/appointments?startDate={event.startTime}&endDate={event.endTime}",
                headers=bzz_headers,
            ).json()
        )
        assert event.eventId in list(map(lambda x: x.eventId, response.items))


def test_get_appointments2():
    global event
    if event is not None:
        response = TypeAdapter(GetAppointmentsResponse).validate_python(
            client.get(
                f"/calendars/{event.calendarId}/appointments?startDate={event.startTime}&endDate={event.endTime}&status={event.status}",
                headers=bzz_headers,
            ).json()
        )
        assert event.eventId in list(map(lambda x: x.eventId, response.items))


def test_delete_calendar():
    global calendar
    if calendar is not None:
        response = TypeAdapter(CommonResponse).validate_python(
            client.delete(
                f"/calendars/{calendar.calendarId}", headers=bzz_headers
            ).json()
        )
        assert response.success is True


cm: ClientModel | None = None


def test_create_client(phone_number):
    global cm
    response = TypeAdapter(ClientModelResponse).validate_python(
        client.post(
            "/clientManagement",
            headers=bzz_headers,
            json=asdict(MinimalClientModel(phone=phone_number)),
        ).json()
    )
    assert response is not None
    assert response.client is not None
    assert response.client.phone == phone_number
    cm = response.client


def test_update_client(phone_number):
    global cm
    if cm is not None:
        new_client_name = f"John {generate_id(length=5)}"
        new_client_group = generate_id(length=8)
        response = TypeAdapter(ClientModelResponse).validate_python(
            client.put(
                f"/clientManagement/{phone_number}",
                headers=bzz_headers,
                json=asdict(
                    UpdatableClientModel(name=new_client_name, group=new_client_group)
                ),
            ).json()
        )
        assert response is not None
        assert response.client is not None
        assert response.client.name == new_client_name
        assert response.client.group == new_client_group
        cm = response.client


def test_get_client(phone_number):
    global cm
    if cm is not None:
        response = TypeAdapter(ClientModelResponse).validate_python(
            client.get(
                f"/clientManagement/{phone_number}",
                headers=bzz_headers,
            ).json()
        )
        assert response is not None
        assert response.client is not None
        cm = response.client


def test_get_clients(phone_number):
    global cm
    if cm is not None:
        response = TypeAdapter(ClientsModelResponse).validate_python(
            client.get(
                "/clientManagement",
                headers=bzz_headers,
            ).json()
        )
        assert response is not None
        assert response.clients is not None
        present = False
        for z in response.clients:
            if z.phone == phone_number:
                present = True
                break
        assert present is True


def test_delete_client(phone_number):
    global cm
    if cm is not None:
        response = TypeAdapter(CommonResponse).validate_python(
            client.delete(
                f"/clientManagement/{phone_number}",
                headers=bzz_headers,
            ).json()
        )
        assert response is not None
        assert response.success is True


def test_messaging(phone_number):
    response = TypeAdapter(CommonResponse).validate_python(
        client.post(
            "/messaging",
            headers=bzz_headers,
            json=asdict(
                MessagingRequest(
                    msg="test message", client_phone_numbers=[phone_number]
                )
            ),
        ).json()
    )
    assert response is not None
    assert response.success is True


todo: Todo | None = None


def test_todo_create(phone_number, phone_number2):
    global todo
    response = TypeAdapter(TodoResponse).validate_python(
        client.post(
            "/todo",
            headers=user_headers,
            json=asdict(
                TodoBase(
                    collaborators=[phone_number2],
                    onUTCMins="",
                    msg="test todo",
                    note="test todo",
                    status=TodoStatus.PENDING,
                )
            ),
        ).json()
    )
    assert response is not None
    assert response.result is not None
    assert phone_number2 in response.result.collaborators
    todo = response.result


def test_todo_update(phone_number2):
    global todo
    if todo is not None:
        new_msg = "todo updated"
        response = TypeAdapter(TodoResponse).validate_python(
            client.put(
                f"/todo/{todo.todoID}",
                headers=user_headers2,
                json=asdict(
                    TodoBaseUpdate(
                        msg=new_msg,
                        note=new_msg,
                        status=TodoStatus.DONE,
                    )
                ),
            ).json()
        )
        assert response is not None
        assert response.result is not None
        assert response.result.msg == new_msg and response.result.note == new_msg
        assert phone_number2 in response.result.collaborators
        todo = response.result


def test_todo_read_all(phone_number):
    global todo
    if todo is not None:
        response = TypeAdapter(TodoListResponse).validate_python(
            client.get("/todo", headers=user_headers2).json()
        )
        assert response is not None
        assert response.result is not None
        present = False
        for z in response.result:
            if z.creator == phone_number:
                present = True
        assert present is True


def test_todo_read_all2(phone_number2):
    global todo
    if todo is not None:
        response = TypeAdapter(TodoListResponse).validate_python(
            client.get("/todo", headers=user_headers2).json()
        )
        assert response is not None
        assert response.result is not None
        present = False
        for z in response.result:
            if phone_number2 in z.collaborators:
                present = True
        assert present is True


def test_todo_delete():
    global todo
    if todo is not None:
        response = TypeAdapter(CommonResponse).validate_python(
            client.delete(f"/todo/{todo.todoID}", headers=user_headers).json()
        )
        assert response is not None
        assert response.success is True


def test_create_user(business2):
    response = client.post(
        "/um/user",
        headers=bzz_headers,
        json=asdict(
            CreateUserRequest(
                email=business2,
            )
        ),
    ).json()
    assert response is None


def test_get_businesses(business):
    response = TypeAdapter(BusinessListResponse).validate_python(
        client.get(
            "/um/businesses",
            headers={"OnBehalfOf": business, **bzz_headers2},
        ).json()
    )
    assert response is not None
    present = False
    for z in response.result:
        if z.business == business:
            present = True
    assert present is True


def test_get_secondaryusers(business, business2):
    response = TypeAdapter(BusinessUserListResponse).validate_python(
        client.get(
            "/um/secondaryusers",
            headers={"OnBehalfOf": business, **bzz_headers2},
        ).json()
    )
    assert response is not None
    present = False
    for z in response.result:
        if z.email == business2:
            present = True
    assert present is True


def test_delete_user(business2):
    response = client.delete(
        f"/um/user/{business2}",
        headers=bzz_headers,
    ).json()
    assert response is None


def test_get_businesses2(business):
    response = TypeAdapter(BusinessListResponse).validate_python(
        client.get(
            "/um/businesses",
            headers={"OnBehalfOf": business, **bzz_headers2},
        ).json()
    )
    assert response is not None
    present = False
    for z in response.result:
        if z.business == business:
            present = True
    assert present is False


def test_send_notification(phone_number2):
    to = [
        SendNotyf(
            title="Notification api test",
            body="pytest",
            data={},
            phoneNumber=phone_number2,
        )
    ]
    response = TypeAdapter(FcmResultResponse).validate_python(
        client.post(
            "/sendNotification",
            headers=bzz_headers,
            json=asdict(SendNotificationRequest(to=to)),
        ).json()
    )
    assert response.success is True
    assert len(response.result) == len(to)


# .\venv\Scripts\activate.ps1
# pytest -s -p no:warnings
