from dataclasses import asdict

from pydantic import TypeAdapter

from database import fsdb
from model import Business, ClientModel, MinimalClientModel


def cross_sync_business_and_client(
    business: str, user_phone: str, mcm: MinimalClientModel | None = None
):
    cm: ClientModel | None = None
    if mcm is not None:
        cm = TypeAdapter(ClientModel).validate_python(asdict(mcm))
    user_path = f"users/{user_phone}"
    if cm is None:
        _t = fsdb.document(user_path).get().to_dict()
        if _t is not None:
            cm = TypeAdapter(ClientModel).validate_python(_t)
    if cm is None:
        cm = ClientModel(phone=user_phone)
    if mcm is not None and mcm.phone is not None:
        cm.phone = mcm.phone

    bzz: Business | None = None
    bzz_path = f"businesses/{business}"
    _t = fsdb.document(bzz_path).get().to_dict()
    if _t is not None:
        bzz = TypeAdapter(Business).validate_python(
            {**_t, "docID": business, "business": business}
        )
    if bzz is None:
        bzz = Business(docID=business, email=business, business=business)

    if cm is not None and bzz is not None:
        _p = f"businesses/{bzz.business}/clients/{cm.phone}"
        _t = fsdb.document(_p).get().to_dict()
        if _t is None:
            fsdb.document(_p).set(asdict(cm))

        _p = f"users/{cm.phone}/businesses/{bzz.business}"
        _t = fsdb.document(_p).get().to_dict()
        if _t is None:
            fsdb.document(_p).set(asdict(bzz))
