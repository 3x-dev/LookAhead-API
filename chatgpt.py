from json import loads
from time import time
from typing import Any, Optional

from arrow import get
from demjson3 import encode
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from pydantic import parse_obj_as
from tenacity import retry, retry_if_result, stop_after_attempt

from constants import (api_key, appointment_types, date_format, iso_8601,
                       model_name)
from model import Output
from common import is_valid_date

"""
This module provides a class with functions that acts as AI Interpreter
"""

prompt = f"""
I need your assistance in extracting specific information from user inputs in my app.

Our users are looking to book an appointment with a {', '.join(sorted(map(lambda x: x._type,appointment_types)))},
They would send us inputs via. text message, Your job is to interpret that message and find out -

1. with whom they want to book an appointment (appointment_type)
2. when they want to book an appointment in {date_format} format (start_date and end_date)
3. time preference of the user (start_time and end_time)

Important things to note -

1. I want the output in JSON and JSON alone, don't apologise, don't output anything but the JSON
2. If you can't figure the type of appointment, then set the "appointment_type" field to "anyone"
3. The current time is - %s
4. I want you to output the time in {date_format}, and in the same timezone as the input
5. Use 24 Hour clock for time preference, and If they have no preference for time, then set "start_time" to 00:00 and "end_time" to 23:59
6. Also, for our case Sunday is the first day of the week, not Monday
7. FYI, these are classifications to interpret the time preference of the user -

    Morning: 08:00 - 11:59
    Noon: 12:00 - 12:59
    Afternoon: 13:00 - 16:59
    Evening: 17:00 - 20:59
    Night: 21:00 - 04:59

Now I'm going to give you some examples, and the expected output JSON, to help you better understand -

Example 1 -

User Input - "Find me a doctor appointment next week"
Expected Output -

{{
  "appointment_type": "doctor",
  "start_date": "<FIGURE OUT THE NEXT SUNDAY>",
  "end_date": "<FIGURE OUT THE SATURDAY OF THE NEXT WEEK>",
  "start_time": "00:00",
  "end_time": "23:59"
}}

Example 2 -

User Input - "Find me an appointment in next two weeks afternoon"
Expected Output -

{{
  "appointment_type": "anyone",
  "start_date": "<FIGURE OUT THE START OF NEXT WEEK>",
  "end_date": "<FIGURE OUT THE SATURDAY OF THE 2ND WEEK FROM NOW>",
  "start_time": "13:00",
  "end_time": "16:59"
}}

Example 3 -

User Input - "Find me a hygienist appointment this month in the morning"
Expected Output -

{{
  "appointment_type": "hygienist",
  "start_date": "<FIGURE OUT THE 1ST DAY OF CURRENT MONTH>",
  "end_date": "<FIGURE OUT THE LAST DAY OF CURRENT MONTH>",
  "start_time": "05:00",
  "end_time": "11:59"
}}
""".strip()


class AIInterpreter:
    """
    This class takes care of interpreting the user input and extracting the required information from it and more.

    Attributes:
        model_name (str): The chatgpt model to use, default is gpt-3.5-turbo.
    """

    def __init__(self, model_name: str = model_name) -> None:
        self.llm = ChatOpenAI(openai_api_key=api_key,
                              temperature=0, model_name=model_name)

    def _is_valid_time(self, s: str) -> bool:
        """
        This function checks if the given string from chatgpt output is a valid time or not.

        Args:
            s (str): The time string e.g. 17:05, 20:30, etc.

        Returns:
            bool: Whether the time is valid or not.
        """
        try:
            spl = s.split(":")
            return len(spl) == 2 and (0 <= int(spl[0]) <= 24) and (0 <= int(spl[1]) <= 59)
        except:
            pass
        return False

    def _convert_to_json(self, unparsed: str) -> Optional[Any]:
        """
        This function tries to parse json from the raw output from chatgpt.

        Args:
            unparsed (str): The raw output from chatgpt.

        Returns:
            Optional[Any]: Returns the parsed json or None.
        """
        try:
            e = encode(unparsed)
            return loads(e)
        except:
            pass
        return None

    def _validate(self, q: str, outjson: Optional[Any], current_time: str) -> Optional[Output]:
        """
        This function validates the parsed json from the raw output from chatgpt.

        Args:
            outjson (Optional[Any]): The result from _convert_to_json.
            current_time (str): The current time provided by user for reference.

        Returns:
            Optional[Output]: If the data is valid returns an object of type Output otherwise None.
        """
        if outjson is not None:
            try:
                _temp = loads(outjson)
                _temp["user_request"] = q
                output = parse_obj_as(Output, _temp)

                if is_valid_date(output.start_date, date_format) and is_valid_date(output.end_date, date_format) and self._is_valid_time(output.start_time) and self._is_valid_time(output.end_time):
                    _tz = current_time[-6:]
                    start_date = get(f"{output.start_date}T00:00:00{_tz}")
                    end_date = get(f"{output.end_date}T23:59:59{_tz}")

                    if start_date.timestamp() > end_date.timestamp():
                        return None

                    def find_appointment_type() -> str:
                        for at in appointment_types:
                            if at._type == output.appointment_type:
                                return at._type
                        return "anyone"

                    return Output(
                        appointment_type=find_appointment_type(),
                        start_date=start_date.format(iso_8601),
                        end_date=end_date.format(iso_8601),
                        start_time=output.start_time,
                        end_time=output.end_time,
                        user_request=output.user_request
                    )
            except:
                pass
        return None

    def __ask(self, q: str, current_time: str) -> Optional[Output]:
        """
        This function calls the underlying apis, validates it and returns the result.

        Args:
            q (str): The user query.
            current_time (str): The current time provided by user for reference.

        Returns:
            Optional[Output]: Returns an Output object upon success otherwise None.
        """
        if is_valid_date(current_time, iso_8601):
            output = self.llm.predict_messages([
                SystemMessage(content=(prompt % current_time)),
                HumanMessage(content=q)
            ])
            outjson = self._convert_to_json(output.content)
            return self._validate(q, outjson, current_time)
        return None

    @retry(stop=stop_after_attempt(3), retry=retry_if_result(lambda x: x is None))
    def _ask(self, q: str, current_time: str) -> Optional[Output]:
        """
        This function calls the __ask function, and It retries 3 times if the result is None.

        Args:
            q (str): The user query.
            current_time (str): The current time provided by user for reference.

        Returns:
            Optional[Output]: Returns an Output object upon success otherwise None.
        """
        return self.__ask(q, current_time)

    def ask(self, q: str, current_time: str = str(get(int(time())))) -> Optional[Output]:
        """
        This function calls the _ask function, which under the hood handles retries if the result is None.
        If the _ask function still can't get a non None value, It throws exception.
        Thus this function is used to catch the exception and return None.

        Args:
            q (str): The user query.
            current_time (str): The current time provided by user for reference.

        Returns:
            Optional[Output]: Returns an Output object upon success otherwise None.
        """
        try:
            return self._ask(q, current_time)
        except:
            pass
        return None
