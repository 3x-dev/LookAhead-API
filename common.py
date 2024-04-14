from string import ascii_letters, ascii_lowercase, ascii_uppercase

from nanoid import generate


def generate_id(length: int = 20) -> str:
    return generate(ascii_letters + ascii_lowercase + ascii_uppercase, length)
