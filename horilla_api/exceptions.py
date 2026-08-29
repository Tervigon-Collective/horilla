"""Normalize DRF error payloads for web and API clients."""

from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler


def _first_validation_message(detail):
    if isinstance(detail, list):
        return str(detail[0]) if detail else "Validation error"
    if isinstance(detail, dict):
        if detail.get("non_field_errors"):
            val = detail["non_field_errors"]
            return str(val[0] if isinstance(val, list) else val)
        if detail.get("message"):
            return str(detail["message"])
        if detail.get("error"):
            return str(detail["error"])
        if detail:
            key = next(iter(detail))
            val = detail[key]
            if isinstance(val, list) and val:
                return str(val[0])
            return str(val)
    return str(detail)


def horilla_api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    if isinstance(exc, ValidationError):
        message = _first_validation_message(data)
        response.data = {
            "message": message,
            "error": message,
            "detail": data,
        }
    elif isinstance(data, dict):
        if "detail" in data and "message" not in data:
            msg = str(data["detail"])
            data.setdefault("message", msg)
            data.setdefault("error", msg)
        elif "error" in data and "message" not in data:
            data["message"] = data["error"]
        elif "message" in data and "error" not in data:
            data["error"] = data["message"]
        response.data = data

    return response
