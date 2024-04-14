from asyncio import create_task, gather
from copy import deepcopy
from dataclasses import asdict
from typing import List

from arrow import get
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import TypeAdapter

from common import generate_id
from constants import date_format2
from database import FcmResult, SendNotyf, fsdb, send_fcm_message, send_sms
from model import (
    CommonDocument,
    DatabaseCalendar,
    DatabaseEvent,
    Output,
    SetAppointmentResponse,
    Subject,
)


class Notyf:
    def __init__(
        self, subject: Subject, start_time: str, end_time: str, query: Output | None
    ) -> None:
        self.bzz_email = subject.business
        self.phoneNumber = subject.phone
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
        if self.query is not None:
            at = self.query.appointmentType
            at = at[0].upper() + at[1:]
            return f"""
    {at} Appointment:
    Client name: User{self.phoneNumber}
    Client Ph: {self.phoneNumber}
    Duration: {self.start_time} to {self.end_time}
    Business: {self.bzz_email}
    DocId: {self.message_doc_id}
    """.strip()
        return ""

    def get_message_doc_data(self) -> CommonDocument:
        at = ""
        if self.query is not None:
            at = self.query.appointmentType
            at = at[0].upper() + at[1:]
        mins = get(self.start_time).to("+00:00").format(date_format2)
        return CommonDocument(
            business=self.bzz_email or "",
            msg=f"{at} Appoinment",
            onUTCMins=mins,
            sentUTCMins=mins,
            reminderLeadMins="60",
            state="UNREAD",
            phoneNumber=self.phoneNumber or "",
            msgFullText=self.get_human_readable_message(),
            calendarId="",
            calendarEventId="",
            calendarStatus="",
            calendarName="",
            calendarTimeZone="",
            docPath="",
            otherDocPath="",
            query=None,
        )

    async def notify(
        self, de: DatabaseEvent, cal: DatabaseCalendar
    ) -> SetAppointmentResponse:
        msg = self.get_message_doc_data()
        msg.calendarId = cal.calendarId
        msg.calendarEventId = de.eventId
        msg.calendarStatus = de.status
        msg.calendarName = cal.calendarName
        msg.calendarTimeZone = cal.timeZone
        #
        msg.docPath = self.message_path
        msg.otherDocPath = self.notification_path
        #
        msg.query = self.query
        nty = deepcopy(msg)
        nty.docPath = self.notification_path
        nty.otherDocPath = self.message_path
        #
        fsdb.document(self.message_path).set(asdict(msg))
        fsdb.document(self.notification_path).set(asdict(nty))
        return SetAppointmentResponse(success=True, result=de)

    @staticmethod
    def update(business: str, calendarId: str, eventId: str, update_data: dict):
        messages = (
            fsdb.collection_group("messages")
            .where(filter=FieldFilter("calendarId", "==", calendarId))
            .where(filter=FieldFilter("calendarEventId", "==", eventId))
            .where(filter=FieldFilter("business", "==", business))
            .limit(1)
            .get()
        )
        if len(messages) > 0:
            _t = messages[0].to_dict()
            data = (
                TypeAdapter(CommonDocument).validate_python(_t)
                if _t is not None
                else None
            )
            if data is not None and data.docPath is not None:
                fsdb.document(data.docPath).update(update_data)

    @staticmethod
    async def send_fcm_messages(sns: List[SendNotyf]) -> List[FcmResult]:
        sns = list(filter(lambda x: x.phoneNumber is not None, sns))

        async def get_tokens_and_send_message(sn: SendNotyf) -> FcmResult:
            _t: List[str] = list(
                filter(
                    lambda x: x is not None,
                    map(
                        lambda x: x.to_dict().get("token"),
                        fsdb.collection(f"users/{sn.phoneNumber}/tokens").get(),
                    ),
                )
            )
            fcm_result = await send_fcm_message(sn=sn, fcm_tokens=list(set(_t)))
            fcm_result.phoneNumber = sn.phoneNumber
            if fcm_result.totalTokens == 0 or fcm_result.successCount == 0:
                await send_sms(sn=sn)
            return fcm_result

        tasks = [create_task(get_tokens_and_send_message(sn=sn)) for sn in sns]
        return await gather(*tasks)
