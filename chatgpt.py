from json import loads
from typing import Any, Optional

from arrow import get
from demjson3 import encode
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from pydantic import TypeAdapter
from tenacity import retry, retry_if_result, stop_after_attempt

from constants import api_key, date_format, model_name
from model import Output


def is_valid_date(s: str, fmt: str = date_format) -> bool:
    """
    This function checks if the given string from chatgpt output is a valid date or not.

    Args:
        s (str): The date string or unix timestamp.
        fmt (str): The expected format the date string to be in.

    Returns:
        bool: Whether the date is valid or not.
    """

    try:
        _ = get(s, fmt)
        return True
    except Exception as e:
        print(e)
        pass
    return False


df = "YYYY-MM-DD"

prompt = f"""
I need your assistance in extracting specific information from user inputs in my app.

Our users are looking to book an appointment with a doctor/dentist/hygienist/cleaning or with someone else,
They would send us inputs via. text message, Your job is to interpret that message and find out -

1. with whom they want to book an appointment (appointmentType)
2. when they want to book an appointment in {df} format (startDate and endDate)
3. time preference of the user (startTime and endTime)

Important things to note -

1. I want the output in JSON and JSON alone, don't apologise, don't output anything but the JSON
2. If you are able to figure out who they are seeking an appointment with then put that in appointmentType field, If you can't figure the type of appointment then set the "appointmentType" field to "anyone"
3. The current time is - %s
4. I want you to output the date in {df}, and in the same timezone as the input
5. Use 24 Hour clock for time preference, and If they have no preference for time, then set "startTime" to 00:00 and "endTime" to 23:59
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
  "appointmentType": "doctor",
  "startDate": "<FIGURE OUT THE NEXT SUNDAY>",
  "endDate": "<FIGURE OUT THE SATURDAY OF THE NEXT WEEK>",
  "startTime": "00:00",
  "endTime": "23:59"
}}

Example 2 -

User Input - "Find me an appointment in next two weeks afternoon"
Expected Output -

{{
  "appointmentType": "anyone",
  "startDate": "<FIGURE OUT THE START OF NEXT WEEK>",
  "endDate": "<FIGURE OUT THE SATURDAY OF THE 2ND WEEK FROM NOW>",
  "startTime": "13:00",
  "endTime": "16:59"
}}

Example 3 -

User Input - "Find me a hygienist appointment this month in the morning"
Expected Output -

{{
  "appointmentType": "hygienist",
  "startDate": "<FIGURE OUT THE 1ST DAY OF CURRENT MONTH>",
  "endDate": "<FIGURE OUT THE LAST DAY OF CURRENT MONTH>",
  "startTime": "05:00",
  "endTime": "11:59"
}}
""".strip()


class AIInterpreter:
    """
    This class takes care of interpreting the user input and extracting the required information from it and more.

    Attributes:
        model_name (str): The chatgpt model to use, default is gpt-3.5-turbo.
    """

    def __init__(self, model_name: str = model_name) -> None:
        self.llm = ChatOpenAI(api_key=api_key, model=model_name, temperature=0)

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
            return (
                len(spl) == 2 and (0 <= int(spl[0]) <= 24) and (0 <= int(spl[1]) <= 59)
            )
        except Exception as _:
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
        except Exception as _:
            pass
        return None

    def _validate(
        self, q: str, outjson: Optional[Any], current_time: str
    ) -> Optional[Output]:
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
                _temp["userRequest"] = q
                output = TypeAdapter(Output).validate_python(_temp)

                if (
                    is_valid_date(output.startDate, df)
                    and is_valid_date(output.endDate, df)
                    and self._is_valid_time(output.startTime)
                    and self._is_valid_time(output.endTime)
                ):
                    _tz = current_time[-6:]
                    startDate = get(f"{output.startDate}T00:00:00{_tz}")
                    endDate = get(f"{output.endDate}T23:59:59{_tz}")

                    if startDate.timestamp() > endDate.timestamp():
                        return None

                    return Output(
                        appointmentType=output.appointmentType,
                        startDate=startDate.format(date_format),
                        endDate=endDate.format(date_format),
                        startTime=output.startTime,
                        endTime=output.endTime,
                        userRequest=output.userRequest,
                    )
            except Exception as e:
                print(e)
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
        output = self.llm.predict_messages(
            [SystemMessage(content=(prompt % current_time)), HumanMessage(content=q)]
        )
        outjson = self._convert_to_json(str(output.content))
        return self._validate(q, outjson, current_time)

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

    def ask(self, q: str, current_time: str) -> Optional[Output]:
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
            return self._ask(q, get(current_time, date_format).format())
        except Exception as e:
            print(e)
            pass
        return None
