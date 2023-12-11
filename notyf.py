from copy import deepcopy
from dataclasses import asdict
from string import ascii_letters, ascii_lowercase, ascii_uppercase

from arrow import get
from nanoid import generate

from database import fsdb
from gcalendar import CreatedEvent
from model import (CommonResponse, CommonAppointmentRequest, Output,
                   SetAppointmentResponse, CommonDocument, Subject)


def generate_id() -> str:
    return generate(ascii_letters + ascii_lowercase + ascii_uppercase, 20)


class Notyf:
    def __init__(self, subject: Subject, start_time: str, end_time: str, query: Output) -> None:
        self.bzz_email = subject.business
        self.phoneNumber = subject.user_phone
        self.start_time = start_time
        self.end_time = end_time
        self.query = query
        #
        self.message_doc_id = generate_id()
        self.message_path = f"users/{self.phoneNumber}/messages/{self.message_doc_id}"
        self.notification_doc_id = generate_id()
        self.notification_path = f"businesses/{self.bzz_email}/user_notifications/{self.phoneNumber}/notifications/{self.notification_doc_id}"
        #
        bzz_doc = f"businesses/{self.bzz_email}"
        user_doc = f"users/{self.phoneNumber}"
        self.bzz_data = fsdb.document(bzz_doc).get().to_dict()
        self.user_data = fsdb.document(user_doc).get().to_dict()

    def get_human_readable_message(self) -> str:
        at = self.query.appointment_type
        at = at[0].upper() + at[1:]
        return f"""
{at} Appointment:
Client name: User{self.phoneNumber}
Client Ph: {self.phoneNumber}
Duration: {self.start_time} to {self.end_time}
Business: {self.bzz_email}
DocId: {self.message_doc_id}
""".strip()

    def get_message_doc_data(self) -> CommonDocument:
        at = self.query.appointment_type
        at = at[0].upper() + at[1:]
        mins = get(self.start_time).to("+00:00").format("M/D/YYYY h:mm A")
        return CommonDocument(
            business=self.bzz_email,
            msg=f"{at} Appoinment",
            onUTCMins=mins,
            sentUTCMins=mins,
            reminder_lead_mins="60",
            state="UNREAD",
            phoneNumber=self.phoneNumber,
            msg_full_text=self.get_human_readable_message(),
            calendarId=None,
            calendarEventId=None,
            calendarStatus=None,
            docPath=None,
            otherDocPath=None,
            query=None
        )

    def notify(self, ce: CreatedEvent) -> SetAppointmentResponse:
        msg = self.get_message_doc_data()
        msg.calendarId = ce.calendarId
        msg.calendarEventId = ce.eventId
        msg.calendarStatus = ce.status
        #
        msg.docPath = self.message_path
        msg.otherDocPath = self.notification_path
        #
        msg.query = {
            "appointment_type": self.query.appointment_type,
            "start_date": str(self.query.start_date),
            "end_date": str(self.query.end_date),
            "start_time": str(self.query.start_time),
            "end_time": str(self.query.end_time),
            "user_request": self.query.user_request
        }
        nty = deepcopy(msg)
        nty.docPath = self.notification_path
        nty.otherDocPath = self.message_path
        #
        fsdb.document(self.message_path).set(asdict(msg))
        fsdb.document(self.notification_path).set(asdict(nty))
        return SetAppointmentResponse(success=True, calendarId=ce.calendarId, eventId=ce.eventId, status=ce.status)

    def update(self, body: CommonAppointmentRequest, update_data: dict) -> CommonResponse:
        messages = (fsdb.collection(f"users/{self.phoneNumber}/messages") if self.phoneNumber is not None and self.phoneNumber != "" else fsdb.collection_group("messages"))\
            .where("calendarId", "==", body.calendarId)\
            .where("calendarEventId", "==", body.eventId)\
            .where("business", "==", self.bzz_email)\
            .limit(1).get()
        for x in messages:
            fsdb.document(x.reference.path).update(update_data)
        return CommonResponse(success=True)
