from json import loads
from typing import Dict

from fastapi import Request
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import TypeAdapter
from validators import email as validate_email

from database import fsdb
from model import Business, Subject


async def find_subject(request: Request) -> Subject:
    subject = Subject(business=None, phone=None, secondaryUserEmail=None)
    decoded_token = request.state.decoded_token
    requestor_email = decoded_token.get("email")
    onbehalfof = request.headers.get("OnBehalfOf", "")

    if onbehalfof == "":
        subject.business = requestor_email
    else:
        if not validate_email(onbehalfof):
            raise Exception("Invalid email")
        subject.business = onbehalfof
        subject.secondaryUserEmail = requestor_email

    _body = {}
    try:
        _body = loads(await request.body())
    except Exception as _:
        pass

    if subject.business is None:
        subject.business = _body.get("business", None)

    if subject.phone is None:
        subject.phone = decoded_token.get("phone_number", None)
    if subject.phone is None:
        subject.phone = decoded_token.get("phoneNumber", None)
    if subject.phone is None:
        subject.phone = _body.get("user_phone", None)
    if subject.phone is None:
        subject.phone = _body.get("userPhone", None)

    if subject.secondaryUserEmail == subject.business:
        # When owners of a business make request
        subject.secondaryUserEmail = None

    if subject.secondaryUserEmail is not None:
        _t = (
            fsdb.collection("businessusers")
            .where(
                filter=FieldFilter(
                    "business",
                    "==",
                    subject.business,
                )
            )
            .where(
                filter=FieldFilter(
                    "email",
                    "==",
                    subject.secondaryUserEmail,
                )
            )
            .limit(1)
            .get()
        )

        if len(_t) != 1:
            raise Exception("Unauthorized secondary user")

    return subject


def convert_dict_to_Business_dict(_t: Dict) -> Dict:
    _t2 = _t.get("email") or _t.get("docID") or _t.get("business")
    return {**_t, "docID": _t2, "business": _t2}


def get_business(businessEmail: str) -> Business | None:
    bzz_path = f"businesses/{businessEmail}"
    _t = fsdb.document(bzz_path).get().to_dict()
    if _t is not None:
        try:
            return TypeAdapter(Business).validate_python(
                convert_dict_to_Business_dict(_t=_t)
            )
        except Exception as _:
            pass
    return None
