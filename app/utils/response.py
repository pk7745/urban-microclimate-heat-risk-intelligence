"""
Standardized JSON response utilities and error handlers for Flask API.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from flask import jsonify, Response


def api_success(data: Any = None,
                message: Optional[str] = None,
                meta: Optional[Dict[str, Any]] = None,
                status_code: int = 200) -> Tuple[Response, int]:
    """Formats a successful API response."""
    payload = {
        "status": "success",
        "data": data if data is not None else {},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if message:
        payload["message"] = message
    if meta is not None:
        payload["meta"] = meta
    return jsonify(payload), status_code


def api_error(message: str,
              error_code: str = "BAD_REQUEST",
              status_code: int = 400,
              details: Optional[Any] = None) -> Tuple[Response, int]:
    """Formats a standardized error API response."""
    payload = {
        "status": "error",
        "error": {
            "code": error_code,
            "message": message
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if details:
        payload["error"]["details"] = details
    return jsonify(payload), status_code
