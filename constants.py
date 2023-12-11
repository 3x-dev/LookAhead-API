from typing import List

from model import AppointmentType

api_key = "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"

service_account = {
    "type": "service_account",
    "project_id": "lookahead-ef698",
    "private_key_id": "9b2c805f5e513e73bc3bbbd5a5e2dc6a31814e8f",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQC3diLAj2HasYYB\nK35eXhAMMaZJquxn0kT2qgbnVVQ4ImXWMZrgsZJptg7M/1YkiX9m2Xinjhr42Ntv\n8U7rQiWavhA2ZsTmTN3WexYMGR+m/3dbyuxo3yxd9/MOiF6+vBMUBuiNj0Vm+WRz\nZ0MZnp8ED2QNSyce5psKCONkAnx8eDOYkhnX9oTBzKeU884dbAH1GsQsHf3iSjNv\nJji1DMp9WTaEkDShT3JJxRfupFD8nA4sKyMspl8bwpxXJ7nPxIDkxY2dD1xt9R9w\nsmbngY+yzJn47vL7K1w4GmkfJUoegfiXN4OlXS5HDDCNqX2nNDrIqwOEuk11GGxw\neodYOmxLAgMBAAECggEAAqXv5nurW+7IEmhAULhm3uYwkkunUfBVEoJtyxUOPCky\n8x6QL8IgbOo12HuvEKPzdNaayUBh30myETGYhAjWZh9sOHzPRsvBQAFS1iXesRhq\n7qZFN1ZRW6HinkkVpQct91IKNVDmHZBoBMpuy4XgobxfI1n8XJPTlRd/wMfQaDOF\nuQ8wPvVGM+5HE9uoXYZOK1EJoD6ip6SVVGwWsRgIXpSfjz1w18ehzlGtYcZDuLYL\n7Q97C2M1CNdvBYEIwkJfD1+YjS0aKCojVgYqy1KGznHlXu9vidt+vS/ZL294o8vQ\nJKNbaMR5xe1z4Qw5+udInGwutP0exUE8gGAWjY/6gQKBgQDdrG9BRBrlEDYqHU8J\njJ+L6KEdWMGlhtZxCm+7lJ/x+TUihgUuP7lv3+mmvxV9JwYqnhsijFoZINSEYWFm\nzEpB0eSrCxWSrY/F0m3S9alL5a8NpRiIiwjPJd3BgJZSqWDdEXz40dBnmmJUnxvL\nE3QUc4iN2cO7sO3aX7g7KOMNIQKBgQDT3uZqq0KvECwjC72akj2pBryCN2q2/xvR\nRo/Cn/VhR8vSAG/w8WxydeduFjdJBDGW8UR5Fa0J5BJkj3fGfGgHZYIw1s4hFl79\nkN8lrDXctJH2LtDgE046nsv6nuwJhCk+CexSgVCNvJGOZq1aDS87hRbJyDxz5bhw\nEsOriQp/6wKBgHLsqA1lOrBRNFOnOEfSIRFO/OCTGGoxutGGQKE2j6nKsrKAWwU8\nQm5u3tr1LDXjWn4T1CuYKknmzGcJeY7rEQCIyg2nRHr0Aprj2s5JUIkpvhTL6Ck6\nM8n5bruYZ9bZO3/BRlJVrL9Zuer3RliFcGP99ejc4m5XbykNAR2it/whAoGAa0qh\nnLsFlem2sDit16zfFM2YgMjXfbxKtfvpqUGf3ZeiG8Kk7XsU1BHpFNKjRJKfGjUr\n27WiXzPkLJCKszUk6Tn6aAkfcZoGmJnYpxdCX3YBxI2IsTCVmRH5cf0wwtDuocAc\nsNtTk7M+csKEXun2VUncdGq2Umqur/KQrDlF2+kCgYAwGO/wVVIxgnv4J8aCpI2R\nWLxib35EFBQAJWJ5p6YkjUSYI4qqbONgL+C7f5UDPzVYgOnSWzQvb+DYudh8dlSC\nCUisraC/LhvBK4pEh4Qn/EOayBHekMJB56yDUmDtIK8iXQa7tRPp3I2iyAm42/Oc\nvaRZaivkKAi1Ry78VWsiVg==\n-----END PRIVATE KEY-----\n",
    "client_email": "firebase-adminsdk-vbkbv@lookahead-ef698.iam.gserviceaccount.com",
    "client_id": "101004230399650913814",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-vbkbv%40lookahead-ef698.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com"
}

client_id = "969915620660-roqafrunebg7atcjgjkvrbkrv16dk3vq.apps.googleusercontent.com"
client_secret = "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"

model_name = "gpt-3.5-turbo"

default_duration = 30
default_break = 0

appointment_types: List[AppointmentType] = [
    AppointmentType(
        _type="doctor",
        duration=default_duration,
        _break=default_break
    ),
    AppointmentType(
        _type="hygienist",
        duration=60,
        _break=default_break
    ),
    AppointmentType(
        _type="dentist",
        duration=30,
        _break=default_break
    ),
    AppointmentType(
        _type="cleaning",
        duration=default_duration,
        _break=default_break
    ),
]

date_format = "YYYY-MM-DD"
iso_8601 = "YYYY-MM-DDTHH:mm:ssZZ"

work_start_from = "08:00"  # 8 am
work_stop_at = "18:00"  # 6 pm

minimum_divisible = 30 * 60  # 30 minutes
