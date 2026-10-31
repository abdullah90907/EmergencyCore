import math
from datetime import datetime, timezone
from werkzeug.exceptions import BadRequest


def now():
    return datetime.now(timezone.utc).isoformat()


def utc(value):
    if not isinstance(value, str):
        raise BadRequest('An ISO timestamp with timezone is required')
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if date.tzinfo is None:
            raise ValueError()
        return date.astimezone(timezone.utc).isoformat()
    except ValueError:
        raise BadRequest('Invalid ISO timestamp; include timezone') from None


def number(value, low, high):
    try:
        if isinstance(value, bool):
            raise ValueError()
        result = float(value)
        if not math.isfinite(result) or not low <= result <= high:
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise BadRequest(f'Expected a finite number between {low} and {high}') from None


def point(value):
    if not isinstance(value, list) or len(value) != 2:
        raise BadRequest('Coordinates must be [longitude, latitude]')
    return [number(value[0], -180, 180), number(value[1], -90, 90)]


def text(value, maximum=1000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise BadRequest(f'Expected nonempty text with at most {maximum} characters')
    return value.strip()
