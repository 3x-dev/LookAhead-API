from typing import List

from firebase_admin import _apps as initialized
from firebase_admin import credentials, firestore, initialize_app
from firebase_admin.messaging import (
    BatchResponse,
    MulticastMessage,
    Notification,
    send_multicast,
)
from google.cloud.firestore import Client
from telnyx import Message

from constants import service_account, telnyx_api_key, telnyx_number
from model import FcmResult, SendNotyf

if not initialized:
    initialize_app(credential=credentials.Certificate(service_account))

fsdb: Client = firestore.client()


async def send_fcm_message(sn: SendNotyf, fcm_tokens: List[str]) -> FcmResult:
    message = MulticastMessage(
        tokens=fcm_tokens,
        data={},
        notification=Notification(title=sn.title, body=sn.body),
    )
    result: BatchResponse = send_multicast(message)
    return FcmResult(
        phoneNumber=None,
        totalTokens=len(fcm_tokens),
        successCount=result.success_count,
        failureCount=result.failure_count,
    )


async def send_sms(sn: SendNotyf):
    try:
        Message.create(
            api_key=telnyx_api_key,
            from_=telnyx_number,
            to=sn.phoneNumber,
            text=f"{sn.title}\n{sn.body}\nhttps://urlgeni.us/lkhd",
        )
    except Exception as _:
        pass
