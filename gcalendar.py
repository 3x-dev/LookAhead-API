from dataclasses import dataclass
from json import loads
from typing import Any, List, Optional
from urllib.parse import urlencode

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from oauth2 import Client, Consumer

from common import get_timezones_for_offset, is_valid_date
from constants import client_id, client_secret, service_account
from model import CommonAppointmentRequest, Output, SlotHolder, UpdateAppointmentRequest
from slot_search import SlotSearch
from constants import iso_8601

"""
This module provides GCalendar class to interact with google calendar.
"""

consumer = Consumer(key=client_id, secret=client_secret)
client = Client(consumer)


@dataclass
class CreatedEvent:
    calendarId: Optional[str]
    eventId: Optional[str]
    status: Optional[str]


class GCalendar:
    """
    This class provides utility functions to interact with google calendar.
    It uses google calendar api v3.
    It provides a clear interface to get the slots.

    Attributes:
        bzz_refreshToken (str): The refresh token of the business, it is expected not to be None.
        output (Output): The parsed output from AI Interpreter.
    """

    def __init__(self, bzz_refreshToken: str, output: Output) -> None:
        self.business_api: Optional[Resource] = None
        self.output = output

        try:
            access_token = self._get_oauth_token(bzz_refreshToken)
            self.business_api = build(
                "calendar", "v3", credentials=Credentials(token=access_token))
        except:
            pass

    def _get_oauth_token(self, _t: str) -> str:
        """
        This function gets the access token from the refresh token by calling the google oauth2 api.

        Args:
            _t (str): The refresh token.

        Returns:
            str: The access token.
        """
        body = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": _t
        }
        content = "{}"
        try:
            _, content = client.request(
                service_account["token_uri"], "POST", body=urlencode(body))
        except Exception as e:
            print(e)
            print(e)
            print(e)
        return loads(content).get("access_token")

    def _calendar_eligibility_criteria(self, calendar_name: str) -> bool:
        """
        This function determines whether a calendar is eligible to be considered for finding slots.

        Args:
            calendar_name (str): The calendar name.

        Returns:
            bool: Whether to take the specified calendar into consideration.
        """
        return calendar_name.lower().startswith("lookahead")

    async def _get_events(self) -> List[Any]:
        """
        This function returns the events between timeMin to timeMax for the calendars that are eligible to be considered for finding slots as determined by _calendar_eligibility_criteria().

        Returns:
            List[SlotHolder]: Returns a list where items of type https://developers.google.com/calendar/api/v3/reference/events#resource.
        """
        calendars = self.business_api.calendarList().list().execute()
        calendars = list(
            filter(lambda x: self._calendar_eligibility_criteria(x["summary"]), calendars.get("items", [])))

        async def _get_calendar_events(calendarId: str):
            return self.business_api.events().list(calendarId=calendarId,
                                                   timeMin=self.output.start_date, timeMax=self.output.end_date).execute()

        _calendars = []

        for x in calendars:
            _events = await _get_calendar_events(x["id"])
            _calendars.append({
                "calendarId": x["id"],
                "calendarName": x["summary"],
                "timeZone": x["timeZone"],
                "items": _events["items"]
            })

        return _calendars

    def create_event(self, calendarId: str, start_time: str, end_time: str, summary: str) -> CreatedEvent:
        if self.business_api is None:
            return CreatedEvent(None, None, None)

        event = {
            "summary": "Appointment",
            "description": summary,
            "status": "tentative",
            "start": {
                "dateTime": start_time,
                "timeZone": self.get_timezone_for_calendar(calendarId=calendarId, tzoffset=start_time[-6:]),
            },
            "end": {
                "dateTime": end_time,
                "timeZone": self.get_timezone_for_calendar(calendarId=calendarId, tzoffset=end_time[-6:]),
            },
            "colorId": "8"
        }

        response = self.business_api.events().insert(
            calendarId=calendarId, body=event).execute()

        return CreatedEvent(calendarId=calendarId, eventId=response["id"], status=response["status"])

    async def find_available_slots(self) -> List[SlotHolder]:
        """
        This functions is the entry point, it makes use of all the other functions of the class to provide available slots.

        Returns:
            List[Slot]: List of available slots.
        """
        if self.business_api is None:
            return []

        _calendars = await self._get_events()
        slots: List[SlotHolder] = []

        for x in _calendars:
            _slots = await SlotSearch(self.output, x["items"],
                                      x["timeZone"]).find_available_slots()
            slots.append(SlotHolder(
                calendarId=x["calendarId"],
                calendarName=x["calendarName"],
                items=_slots
            ))

        return slots

    def get_timezone_for_calendar(self, calendarId: str, tzoffset: str) -> str:
        calendar_result = self.business_api.calendars().get(
            calendarId=calendarId).execute()
        ctz = [calendar_result.get("timeZone")]
        otz = get_timezones_for_offset(tzoffset)
        common_elements = list(set(ctz).intersection(set(otz)))
        return common_elements[0] if len(common_elements) == 1 else ctz

    def confirm_appointment(self, body: CommonAppointmentRequest) -> bool:
        if self.business_api is None:
            return False

        response = self.business_api.events().patch(
            calendarId=body.calendarId, eventId=body.eventId, body={
                "status": "confirmed",
                "colorId": "2"
            }).execute()

        return response.get("status") == "confirmed"

    def cancel_appointment(self, body: CommonAppointmentRequest) -> bool:
        if self.business_api is None:
            return False

        response = self.business_api.events().patch(
            calendarId=body.calendarId, eventId=body.eventId, body={
                "status": "cancelled"
            }).execute()

        return response.get("status") == "cancelled"

    def update_appointment(self, body: UpdateAppointmentRequest) -> bool:
        if self.business_api is not None:
            if body.start_time is not None and body.end_time is not None:
                if is_valid_date(body.start_time, iso_8601) and is_valid_date(body.end_time, iso_8601):
                    response = self.business_api.events().patch(
                        calendarId=body.calendarId, eventId=body.eventId, body={
                            "start": {
                                "dateTime": body.start_time,
                                "timeZone": self.get_timezone_for_calendar(calendarId=body.calendarId, tzoffset=body.start_time[-6:]),

                            },
                            "end": {
                                "dateTime": body.end_time,
                                "timeZone": self.get_timezone_for_calendar(calendarId=body.calendarId, tzoffset=body.end_time[-6:]),
                            },
                        }).execute()
                    return response is not None
        return False
