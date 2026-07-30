import re

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

def validate_email(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email))

def validate_uuid(uuid_str: str) -> bool:
    return bool(UUID_REGEX.match(uuid_str))