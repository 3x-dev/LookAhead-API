from asyncio import create_task, gather
from dataclasses import asdict
from typing import List, Tuple

from fastapi import Request
from fastapi.params import Header
from fastapi.routing import APIRouter
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import TypeAdapter
from typing_extensions import Annotated

from common import generate_id
from common2 import find_subject, get_business
from database import fsdb
from model import (
    Business,
    BusinessListResponse,
    BusinessUser,
    BusinessUserListResponse,
    BusinessUserRole,
    CreateUserRequest,
)

col_name = "businessusers"


class BusinessUserManagement:
    def __init__(self, email: str, businessEmail: str) -> None:
        self.email = email
        self.businessEmail = businessEmail

    def _get_doc_at_business(self) -> List[Tuple[str, BusinessUser]]:
        docs = (
            fsdb.collection(col_name)
            .where(filter=FieldFilter("email", "==", self.email))
            .where(filter=FieldFilter("business", "==", self.businessEmail))
            .limit(1)
            .get()
        )
        return list(
            map(
                lambda z: (
                    z.id,
                    TypeAdapter(BusinessUser).validate_python(z.to_dict()),
                ),
                docs,
            )
        )

    def add_user(self, roles: List[BusinessUserRole]) -> None:
        docs = self._get_doc_at_business()
        if len(docs) == 0:
            bu = BusinessUser(
                email=self.email, business=self.businessEmail, roles=roles
            )
            fsdb.document(f"{col_name}/{generate_id()}").set(asdict(bu))

    def remove_user(self) -> None:
        docs = self._get_doc_at_business()
        if len(docs) == 1:
            fsdb.document(f"{col_name}/{docs[0][0]}").delete()

    @staticmethod
    def get_businesses_user_part_of(userEmail: str) -> List[BusinessUser]:
        docs = (
            fsdb.collection(col_name)
            .where(filter=FieldFilter("email", "==", userEmail))
            .get()
        )
        return TypeAdapter(List[BusinessUser]).validate_python(
            list(
                map(
                    lambda z: z.to_dict(),
                    docs,
                )
            )
        )

    @staticmethod
    def get_users_part_of_businesses(businessEmail: str) -> List[BusinessUser]:
        docs = (
            fsdb.collection(col_name)
            .where(filter=FieldFilter("business", "==", businessEmail))
            .get()
        )
        return TypeAdapter(List[BusinessUser]).validate_python(
            list(
                map(
                    lambda z: z.to_dict(),
                    docs,
                )
            )
        )


router = APIRouter()


@router.get("/businesses")
async def get_businesses(
    request: Request, accesskey: Annotated[str | None, Header()]
) -> BusinessListResponse:
    subject = await find_subject(request=request)
    businesses: List[Business] = []
    if subject.business is not None:
        bpo: List[str] = [subject.business]
        bpo.extend(
            list(
                map(
                    lambda z: z.business,
                    BusinessUserManagement.get_businesses_user_part_of(
                        userEmail=subject.business
                    ),
                )
            )
        )

        async def get_business_async(businessEmail: str) -> Business | None:
            return get_business(businessEmail=businessEmail)

        tasks = [create_task(get_business_async(businessEmail=em)) for em in bpo]
        businesses = TypeAdapter(List[Business]).validate_python(
            filter(lambda z: z is not None, await gather(*tasks))
        )
        businesses.sort(key=lambda z: z.email)
    return BusinessListResponse(result=businesses)


@router.post("/user")
async def create_user(
    request: Request,
    accesskey: Annotated[str | None, Header()],
    body: CreateUserRequest,
) -> None:
    subject = await find_subject(request=request)
    if subject.business is not None:
        _t = get_business(businessEmail=subject.business)
        if _t is not None:
            bum = BusinessUserManagement(
                email=body.email, businessEmail=subject.business
            )
            bum.add_user(roles=body.roles)
    return None


@router.delete("/user/{email}")
async def delete_user(
    request: Request, accesskey: Annotated[str | None, Header()], email: str
) -> None:
    subject = await find_subject(request=request)
    if subject.business is not None:
        _t = get_business(businessEmail=subject.business)
        if _t is not None:
            bum = BusinessUserManagement(email=email, businessEmail=subject.business)
            bum.remove_user()
    return None


@router.get("/secondaryusers")
async def get_secondaryusers(
    request: Request, accesskey: Annotated[str | None, Header()]
) -> BusinessUserListResponse:
    subject = await find_subject(request=request)
    blr = BusinessUserListResponse(result=[])
    if subject.business is not None:
        blr.result = BusinessUserManagement.get_users_part_of_businesses(
            businessEmail=subject.business
        )
    return blr
