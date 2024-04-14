from typing import Tuple

from firebase_admin import auth
from requests import post

from database import initialized


def get_auth_tokens(uid: str) -> Tuple[str, str]:
    api_key = "AIzaSyCJP6WWR7mY27RN2fKP3otFgbDfZeAmjno"
    token = auth.create_custom_token(uid=uid)
    resp1 = post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={api_key}",
        {"token": token, "returnSecureToken": True},
    )
    resp2 = post(
        f"https://securetoken.googleapis.com/v1/token?key={api_key}",
        {
            "grant_type": "refresh_token",
            "refresh_token": resp1.json().get("refreshToken"),
        },
    )
    return resp2.json().get("refresh_token"), resp2.json().get("access_token")


bzz_uid = "DogX72S9ssaxAygA8FI2XpV4IG13"
bzz_uid2 = "I7a8KAOF5ifk1JXUbUwQVuxSmpC3"
user_uid = "yb3fhnUolPbfr70Uek5UbBJGrCl2"
user_uid2 = "LXEoy1NYQCU2tkLUHId0FoPTseH3"

if __name__ == "__main__":
    if initialized:
        _, t = get_auth_tokens(uid=bzz_uid)
        print(f"{t}")
        _, t = get_auth_tokens(uid=user_uid)
        print(f"\n{t}")
