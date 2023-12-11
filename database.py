import datetime
from typing import Optional, List

from firebase_admin import credentials, firestore, initialize_app
from google.cloud.firestore import Client
from google.cloud.firestore_v1.base_query import FieldFilter

from constants import service_account
from model import BusinessCalendar, CreateCalendarRequest

initialize_app(credential=credentials.Certificate(service_account))

fsdb: Client = firestore.client()


def get_rt_from_db(email: Optional[str] = None) -> Optional[str]:
    """
    This function fetches refresh token from the firestore for a given email accordingly.

    Args:
        email (Optional[str]): The email.

    Returns:
        Optional[str]: If refresh token is found then it is returned otherwise None.
    """
    if email is not None:
        doc_ref = fsdb.collection("businesses").document(email)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get("refreshToken")
    return None

'''
create a document with the following structure
event {
    createdBy: string
    title: string
    description: string
    startTime: timestamp
    duration: number
    calender: string
    attendent: string
    serviceType: string
    status: string
    customer: string
    notes: string
}
'''

def db_create_event(event, email: str, calendarId: str) -> Optional[dict]:
    if email is not None:
        col_ref = fsdb.collection("businesses").document(email).collection("calendars").document(calendarId).collection("events")
        update_time, event_ref = col_ref.add(event)
        print(f"Created event with id {event_ref.id} at {update_time} in calendar {calendarId}")
        event["id"] = event_ref.id
        return event

def db_update_event(email: str, eventId: str, calendarId: str, body: dict) -> Optional[dict]:
    if email is not None:
        doc_ref = fsdb.collection("businesses").document(email).collection("calendars").document(calendarId).collection("events").document(eventId)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            if "status" in data:
                data["status"] = body["status"]
            if "colorId" in data:
                data["colorId"] = body["colorId"]
            doc_ref.set(data, merge=True)
            return data
        return body
    
def db_get_events(email: str, calendarId: str, start_date: datetime, end_date: datetime) -> Optional[dict]:
    if email is not None:
        doc_ref = fsdb.collection("businesses").document(email).collection("calendars").document(calendarId).collection("events").where(filter=FieldFilter("startTime", ">=", start_date)).where(filter=FieldFilter("startTime", "<=", end_date))
        docs = doc_ref.stream()
        events = []
        for d in docs:
            e = d.to_dict()
            e["eventId"] = d.id
            events.append(e)
        return events
    
def db_get_calendars(email: str) -> List[BusinessCalendar] :
    col_ref = fsdb.collection("businesses").document(email).collection("calendars")
    cals = col_ref.stream()
    calendars = []
    for doc in cals:
        d = doc.to_dict()
        d["calendarId"]  = doc.id
        calendars.append(d)
    # if len(calendars) == 0:
    #     default = db_create_calendar(
    #         email=email, 
    #         body={
    #             "calendarName": "default",
    #             "timeZone": "GMT",
    #             "opens": "8:00 AM",
    #             "closes": "5:00 PM",
    #             "daysOpen": [
    #                 0, 1, 2, 3, 4, 5
    #             ],
    #             "description": "Default Calendar"
    #         }
    #     )
    #     calendars.append(default)
    return calendars

def db_create_calendar(email: str, body: CreateCalendarRequest) -> dict:    
    col_ref = fsdb.collection("businesses").document(email).collection("calendars")
    opens = body.opens
    closes = body.closes
    d = {
        "calendarName": body.calendarName,
        "timeZone": body.timeZone,
        "opens": opens,
        "closes": closes,
        "daysOpen": body.daysOpen,
        "description": body.description,
    }
    update_time, event_ref = col_ref.add(d)
    print(f"Created calendar with id {event_ref.id} at {update_time}")
    d["calendarId"] = event_ref.id
    return d

def db_delete_calendars(email: str, calendarId: str) -> List[str]:    
    doc_ref = fsdb.collection("businesses").document(email).collection("calendars").document(calendarId)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.delete()
        return True
    return False