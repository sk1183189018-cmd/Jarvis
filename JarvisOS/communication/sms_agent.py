communication/sms_agent.py

"""
JarvisOS - SMS Agent

SMS integration layer.

This module provides a safe abstraction for sending and reading SMS.

Important:

- JarvisOS does NOT silently send SMS.
- Sending SMS requires confirm=True.
- The module supports provider APIs through configuration.
- No fake SMS service URL is hard-coded.
- Without a configured provider, the module reports that SMS
  is unavailable instead of pretending that a message was sent.

Supported provider style:

1. HTTP/REST SMS provider
2. Custom endpoint configured through environment variables

Environment variables:

JARVIS_SMS_API_URL=
JARVIS_SMS_API_KEY=
JARVIS_SMS_SENDER=
JARVIS_SMS_TIMEOUT=20
JARVIS_SMS_MAX_MESSAGE_LENGTH=1600

Example provider request:

POST JARVIS_SMS_API_URL

Headers:
Authorization: Bearer <API_KEY>
Content-Type: application/json

JSON:
{
"to": "+919999999999",
"from": "JarvisOS",
"message": "Hello"
}

The exact provider payload can differ. For providers with a
different API format, this class can be extended safely.
"""

from future import annotations

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
import requests
except ImportError:
requests = None

logger = logging.getLogger(
"JarvisOS.SMSAgent"
)

============================================================

DATA CLASSES

============================================================

@dataclass
class SMSMessage:
"""
Represents an SMS message.
"""

message_id: str = ""
sender: str = ""
recipient: str = ""
message: str = ""
timestamp: str = ""
direction: str = "outgoing"
status: str = ""
provider: str = ""

@dataclass
class SMSResult:
"""
Standard result returned by SMS operations.
"""

success: bool
message: str = ""
error: str = ""
message_id: str = ""
data: Any = None

def to_dict(self) -> dict[str, Any]:
    return asdict(self)

============================================================

SMS AGENT

============================================================

class SMSAgent:
"""
Safe SMS provider integration.

Sending is always confirmation-gated.
"""

DEFAULT_TIMEOUT = 20

MAX_MESSAGE_LENGTH = 1600

def __init__(
    self,
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    sender: Optional[str] = None,
    timeout: Optional[int] = None,
    history_path: Optional[str | Path] = None,
) -> None:

    self.api_url = (
        api_url
        or os.getenv(
            "JARVIS_SMS_API_URL",
            "",
        ).strip()
    )

    self.api_key = (
        api_key
        or os.getenv(
            "JARVIS_SMS_API_KEY",
            "",
        ).strip()
    )

    self.sender = (
        sender
        or os.getenv(
            "JARVIS_SMS_SENDER",
            "",
        ).strip()
    )

    try:
        self.timeout = int(
            timeout
            if timeout is not None
            else os.getenv(
                "JARVIS_SMS_TIMEOUT",
                str(self.DEFAULT_TIMEOUT),
            )
        )
    except (TypeError, ValueError):

        self.timeout = (
            self.DEFAULT_TIMEOUT
        )

    self.timeout = max(
        5,
        min(
            self.timeout,
            120,
        ),
    )

    self.max_message_length = (
        self.MAX_MESSAGE_LENGTH
    )

    self.history_path = (
        Path(history_path)
        if history_path
        else Path("data")
        / "sms_history.json"
    )

    self.history_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    self.history: list[dict[str, Any]] = []

    self._load_history()

# ========================================================
# VALIDATION
# ========================================================

@staticmethod
def normalize_phone(
    phone: str,
) -> str:

    if not isinstance(
        phone,
        str,
    ):

        raise ValueError(
            "Phone number must be a string."
        )

    phone = phone.strip()

    if not phone:
        raise ValueError(
            "Phone number is empty."
        )

    # Keep leading + and digits.
    normalized = re.sub(
        r"[^\d+]",
        "",
        phone,
    )

    # Only one leading + is allowed.
    if normalized.count("+") > 1:

        raise ValueError(
            "Invalid phone number."
        )

    if "+" in normalized[1:]:

        raise ValueError(
            "Invalid phone number."
        )

    digits = normalized.lstrip(
        "+"
    )

    # Basic international-number validation.
    if not digits.isdigit():

        raise ValueError(
            "Invalid phone number."
        )

    if not 7 <= len(digits) <= 15:

        raise ValueError(
            "Phone number must contain "
            "7 to 15 digits."
        )

    return (
        "+"
        + digits
        if normalized.startswith("+")
        else digits
    )

def validate_message(
    self,
    message: str,
) -> str:

    if not isinstance(
        message,
        str,
    ):

        raise ValueError(
            "SMS message must be text."
        )

    message = message.strip()

    if not message:

        raise ValueError(
            "SMS message cannot be empty."
        )

    if len(message) > (
        self.max_message_length
    ):

        raise ValueError(
            "SMS message is too long. "
            f"Maximum is {self.max_message_length} characters."
        )

    return message

# ========================================================
# CONFIGURATION
# ========================================================

def is_configured(self) -> bool:

    return bool(
        self.api_url
        and self.api_key
    )

def get_status(self) -> dict[str, Any]:

    return {
        "configured": self.is_configured(),
        "provider_url_configured": bool(
            self.api_url
        ),
        "api_key_configured": bool(
            self.api_key
        ),
        "sender_configured": bool(
            self.sender
        ),
        "timeout": self.timeout,
        "history_count": len(
            self.history
        ),
        "requests_available": (
            requests is not None
        ),
    }

# ========================================================
# HTTP
# ========================================================

def _headers(self) -> dict[str, str]:

    return {
        "Authorization": (
            f"Bearer {self.api_key}"
        ),
        "Content-Type": (
            "application/json"
        ),
        "Accept": "application/json",
        "User-Agent": "JarvisOS-SMS-Agent/1.0",
    }

def _request(
    self,
    payload: dict[str, Any],
) -> SMSResult:

    if requests is None:

        return SMSResult(
            success=False,
            error=(
                "The 'requests' package is not installed."
            ),
        )

    if not self.is_configured():

        return SMSResult(
            success=False,
            error=(
                "SMS provider is not configured. "
                "Set JARVIS_SMS_API_URL and "
                "JARVIS_SMS_API_KEY."
            ),
        )

    try:

        response = requests.post(
            self.api_url,
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )

        response_text = (
            response.text[:5000]
        )

        try:
            response_data = (
                response.json()
            )
        except ValueError:
            response_data = (
                response_text
            )

        if 200 <= response.status_code < 300:

            return SMSResult(
                success=True,
                message=(
                    "SMS provider accepted "
                    "the request."
                ),
                data=response_data,
            )

        return SMSResult(
            success=False,
            error=(
                "SMS provider returned "
                f"HTTP {response.status_code}."
            ),
            data=response_data,
        )

    except requests.Timeout:

        return SMSResult(
            success=False,
            error=(
                "SMS provider request timed out."
            ),
        )

    except requests.RequestException as exc:

        logger.error(
            "SMS provider request failed: %s",
            exc,
        )

        return SMSResult(
            success=False,
            error=(
                f"SMS provider request failed: {exc}"
            ),
        )

    except Exception as exc:

        logger.exception(
            "Unexpected SMS request error."
        )

        return SMSResult(
            success=False,
            error=str(exc),
        )

# ========================================================
# SEND SMS
# ========================================================

def send_sms(
    self,
    recipient: str,
    message: str,
    confirm: bool = False,
    sender: Optional[str] = None,
) -> SMSResult:

    """
    Send an SMS.

    confirm=True is mandatory because sending an SMS
    is an external side effect.
    """

    try:

        recipient = self.normalize_phone(
            recipient
        )

        message = self.validate_message(
            message
        )

    except ValueError as exc:

        return SMSResult(
            success=False,
            error=str(exc),
        )

    if not confirm:

        return SMSResult(
            success=False,
            message=(
                "SMS sending requires confirmation."
            ),
            error=(
                "confirm=True is required."
            ),
        )

    if not self.is_configured():

        return SMSResult(
            success=False,
            error=(
                "SMS provider is not configured."
            ),
        )

    sender_value = (
        sender
        or self.sender
    )

    payload = {
        "to": recipient,
        "from": sender_value,
        "message": message,
    }

    started = time.time()

    result = self._request(
        payload
    )

    elapsed = round(
        time.time() - started,
        3,
    )

    message_id = ""

    if isinstance(
        result.data,
        dict,
    ):

        for key in (
            "message_id",
            "messageId",
            "id",
            "sid",
        ):

            value = result.data.get(
                key
            )

            if value:

                message_id = str(
                    value
                )

                break

    result.message_id = (
        message_id
    )

    record = SMSMessage(
        message_id=message_id,
        sender=sender_value,
        recipient=recipient,
        message=message,
        timestamp=datetime.now().isoformat(),
        direction="outgoing",
        status=(
            "sent"
            if result.success
            else "failed"
        ),
        provider=self.api_url,
    )

    self._add_history(
        record,
        elapsed=elapsed,
    )

    return result

# ========================================================
# ALIASES
# ========================================================

def send(
    self,
    recipient: str,
    message: str,
    confirm: bool = False,
) -> SMSResult:

    return self.send_sms(
        recipient=recipient,
        message=message,
        confirm=confirm,
    )

# ========================================================
# INCOMING SMS
# ========================================================

def read_messages(
    self,
    limit: int = 20,
) -> SMSResult:

    """
    Read incoming SMS.

    Generic SMS providers do not share one standard API,
    therefore this method expects the configured provider
    to expose GET / configured API endpoint semantics.

    If the endpoint does not support GET, the method safely
    reports the limitation.
    """

    if requests is None:

        return SMSResult(
            success=False,
            error=(
                "The 'requests' package is not installed."
            ),
        )

    if not self.is_configured():

        return SMSResult(
            success=False,
            error=(
                "SMS provider is not configured."
            ),
        )

    try:

        limit = max(
            1,
            min(
                int(limit),
                100,
            ),
        )

    except (
        TypeError,
        ValueError,
    ):

        limit = 20

    try:

        response = requests.get(
            self.api_url,
            headers=self._headers(),
            params={
                "limit": limit,
                "direction": "incoming",
            },
            timeout=self.timeout,
        )

        if not (
            200
            <= response.status_code
            < 300
        ):

            return SMSResult(
                success=False,
                error=(
                    "SMS provider does not expose "
                    "a compatible read endpoint or "
                    f"returned HTTP {response.status_code}."
                ),
            )

        try:

            data = response.json()

        except ValueError:

            data = response.text

        messages = (
            self._parse_messages(
                data
            )
        )

        return SMSResult(
            success=True,
            message=(
                f"Retrieved {len(messages)} messages."
            ),
            data=messages,
        )

    except Exception as exc:

        logger.error(
            "Could not read SMS messages: %s",
            exc,
        )

        return SMSResult(
            success=False,
            error=str(exc),
        )

# ========================================================
# PARSE INCOMING
# ========================================================

@staticmethod
def _parse_messages(
    data: Any,
) -> list[dict[str, Any]]:

    if isinstance(
        data,
        dict,
    ):

        for key in (
            "messages",
            "data",
            "results",
            "items",
        ):

            if isinstance(
                data.get(key),
                list,
            ):

                data = data[key]
                break

    if not isinstance(
        data,
        list,
    ):

        return []

    output = []

    for item in data:

        if isinstance(
            item,
            SMSMessage,
        ):

            output.append(
                asdict(item)
            )

        elif isinstance(
            item,
            dict,
        ):

            output.append(
                {
                    "message_id": str(
                        item.get(
                            "message_id",
                            item.get(
                                "id",
                                "",
                            ),
                        )
                    ),
                    "sender": str(
                        item.get(
                            "sender",
                            item.get(
                                "from",
                                "",
                            ),
                        )
                    ),
                    "recipient": str(
                        item.get(
                            "recipient",
                            item.get(
                                "to",
                                "",
                            ),
                        )
                    ),
                    "message": str(
                        item.get(
                            "message",
                            item.get(
                                "body",
                                "",
                            ),
                        )
                    ),
                    "timestamp": str(
                        item.get(
                            "timestamp",
                            item.get(
                                "created_at",
                                "",
                            ),
                        )
                    ),
                    "direction": str(
                        item.get(
                            "direction",
                            "incoming",
                        )
                    ),
                    "status": str(
                        item.get(
                            "status",
                            "",
                        )
                    ),
                }
            )

    return output

# ========================================================
# SEARCH LOCAL HISTORY
# ========================================================

def search_history(
    self,
    query: str,
    limit: int = 50,
) -> list[dict[str, Any]]:

    query = (
        str(query)
        .strip()
        .lower()
    )

    if not query:
        return []

    matches = []

    for item in reversed(
        self.history
    ):

        text = " ".join(
            [
                str(
                    item.get(
                        "recipient",
                        "",
                    )
                ),
                str(
                    item.get(
                        "sender",
                        "",
                    )
                ),
                str(
                    item.get(
                        "message",
                        "",
                    )
                ),
                str(
                    item.get(
                        "status",
                        "",
                    )
                ),
            ]
        ).lower()

        if query in text:

            matches.append(
                item
            )

            if len(matches) >= limit:
                break

    return matches

# ========================================================
# HISTORY
# ========================================================

def _load_history(self) -> None:

    if not self.history_path.exists():
        return

    try:

        with self.history_path.open(
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(
                file
            )

        if isinstance(
            data,
            list,
        ):

            self.history = data

    except Exception as exc:

        logger.warning(
            "Could not load SMS history: %s",
            exc,
        )

def _save_history(self) -> None:

    try:

        temporary = (
            self.history_path.with_suffix(
                ".tmp"
            )
        )

        with temporary.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                self.history,
                file,
                indent=2,
                ensure_ascii=False,
            )

        temporary.replace(
            self.history_path
        )

    except Exception as exc:

        logger.error(
            "Could not save SMS history: %s",
            exc,
        )

def _add_history(
    self,
    record: SMSMessage,
    elapsed: float = 0.0,
) -> None:

    item = asdict(
        record
    )

    item["elapsed_seconds"] = (
        elapsed
    )

    self.history.append(
        item
    )

    # Keep local history bounded.
    if len(self.history) > 1000:

        self.history = (
            self.history[-1000:]
        )

    self._save_history()

def get_history(
    self,
    limit: int = 50,
) -> list[dict[str, Any]]:

    try:

        limit = max(
            1,
            min(
                int(limit),
                500,
            ),
        )

    except (
        TypeError,
        ValueError,
    ):

        limit = 50

    return list(
        reversed(
            self.history[-limit:]
        )
    )

def clear_history(
    self,
    confirm: bool = False,
) -> SMSResult:

    if not confirm:

        return SMSResult(
            success=False,
            error=(
                "confirm=True is required "
                "to clear SMS history."
            ),
        )

    self.history.clear()

    self._save_history()

    return SMSResult(
        success=True,
        message="SMS history cleared.",
    )

# ========================================================
# CONNECTION TEST
# ========================================================

def test_connection(self) -> SMSResult:

    if requests is None:

        return SMSResult(
            success=False,
            error=(
                "The 'requests' package is not installed."
            ),
        )

    if not self.is_configured():

        return SMSResult(
            success=False,
            error=(
                "SMS provider is not configured."
            ),
        )

    try:

        response = requests.get(
            self.api_url,
            headers=self._headers(),
            params={
                "limit": 1,
            },
            timeout=self.timeout,
        )

        if 200 <= response.status_code < 300:

            return SMSResult(
                success=True,
                message=(
                    "SMS provider is reachable."
                ),
            )

        return SMSResult(
            success=False,
            error=(
                "SMS provider returned "
                f"HTTP {response.status_code}."
            ),
        )

    except Exception as exc:

        return SMSResult(
            success=False,
            error=str(exc),
        )

# ========================================================
# EXPORT
# ========================================================

def export_history(
    self,
    path: str | Path,
) -> SMSResult:

    destination = Path(
        path
    ).expanduser()

    try:

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with destination.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                self.history,
                file,
                indent=2,
                ensure_ascii=False,
            )

        return SMSResult(
            success=True,
            message=(
                "SMS history exported."
            ),
            data=str(
                destination
            ),
        )

    except Exception as exc:

        logger.error(
            "SMS history export failed: %s",
            exc,
        )

        return SMSResult(
            success=False,
            error=str(exc),
        )

# ========================================================
# CLOSE
# ========================================================

def close(self) -> None:

    self._save_history()

def __enter__(
    self,
) -> "SMSAgent":

    return self

def __exit__(
    self,
    exc_type: Any,
    exc_value: Any,
    traceback_value: Any,
) -> None:

    self.close()

============================================================

SHARED INSTANCE

============================================================

_sms_agent: Optional[SMSAgent] = None

def get_sms_agent() -> SMSAgent:

global _sms_agent

if _sms_agent is None:

    _sms_agent = SMSAgent()

return _sms_agent

============================================================

CONVENIENCE FUNCTIONS

============================================================

def send_sms(
recipient: str,
message: str,
confirm: bool = False,
) -> SMSResult:

return get_sms_agent().send_sms(
    recipient=recipient,
    message=message,
    confirm=confirm,
)

def read_sms(
limit: int = 20,
) -> SMSResult:

return get_sms_agent().read_messages(
    limit=limit
)

============================================================

DIRECT TEST

============================================================

if name == "main":

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)

print("=" * 60)
print("JARVIS OS - SMS AGENT TEST")
print("=" * 60)

agent = SMSAgent()

print(
    json.dumps(
        agent.get_status(),
        indent=2,
    )
)

# Deliberately does NOT send an SMS.
result = agent.send_sms(
    recipient="+919999999999",
    message="JarvisOS test message",
    confirm=False,
)

print("\nSafe send test:")

print(
    json.dumps(
        result.to_dict(),
        indent=2,
        default=str,
    )
)

print(
    "\nNo real SMS was sent."
)

agent.close()
