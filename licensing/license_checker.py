licensing/license_checker.py

"""
JarvisOS - License Checker

End-user license validation system.

Features:

- License key loading
- RSA signature verification
- License expiration checking
- Device binding verification
- Feature checking
- License status
- Safe JSON license storage
- ActivationManager compatibility
- LicenseGenerator compatibility

IMPORTANT:
This module verifies a license locally.
It does NOT contact a server unless a future online
license service is added.
"""

from future import annotations

import base64
import hashlib
import json
import logging
import os
import platform
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
except ImportError:
InvalidSignature = Exception
hashes = None
serialization = None
padding = None

logger = logging.getLogger(
"JarvisOS.LicenseChecker"
)

============================================================

DATA CLASSES

============================================================

@dataclass
class LicenseInfo:
"""
Normalized license information.
"""

license_id: str = ""
license_key: str = ""
product: str = "JarvisOS"
version: str = ""
customer: str = ""
email: str = ""

issued_at: str = ""
expires_at: str = ""

license_type: str = "standard"
max_devices: int = 1

device_id: str = ""

features: Optional[list[str]] = None
metadata: Optional[dict[str, Any]] = None

signature: str = ""

def __post_init__(self) -> None:

    if self.features is None:
        self.features = []

    if self.metadata is None:
        self.metadata = {}

@dataclass
class LicenseValidationResult:
"""
Result returned by license validation.
"""

valid: bool
status: str
message: str

license_id: str = ""
license_type: str = ""
customer: str = ""

expires_at: str = ""

device_bound: bool = False
device_match: bool = False

signature_valid: bool = False
expired: bool = False

features: Optional[list[str]] = None
errors: Optional[list[str]] = None
warnings: Optional[list[str]] = None

def to_dict(self) -> dict[str, Any]:
    return asdict(self)

============================================================

LICENSE CHECKER

============================================================

class LicenseChecker:
"""
Local JarvisOS license verification service.

Expected license structure:

{
    "license": {
        "license_id": "...",
        "product": "JarvisOS",
        "version": "1.0.0",
        "customer": "...",
        "email": "...",
        "issued_at": "...",
        "expires_at": "...",
        "license_type": "standard",
        "max_devices": 1,
        "device_id": "",
        "features": [],
        "metadata": {}
    },
    "signature": "BASE64_RSA_SIGNATURE"
}

The signature is generated over the canonical JSON
representation of the "license" object.
"""

DEFAULT_LICENSE_FILE = (
    "data/license.json"
)

ENV_LICENSE_FILE = (
    "JARVIS_LICENSE_FILE"
)

ENV_PUBLIC_KEY = (
    "JARVIS_LICENSE_PUBLIC_KEY"
)

ENV_PUBLIC_KEY_FILE = (
    "JARVIS_LICENSE_PUBLIC_KEY_FILE"
)

PRODUCT_NAME = "JarvisOS"

def __init__(
    self,
    license_path: Optional[str | Path] = None,
    public_key: Optional[str] = None,
    public_key_path: Optional[str | Path] = None,
    expected_product: str = PRODUCT_NAME,
) -> None:

    base_dir = Path(
        __file__
    ).resolve().parents[1]

    configured_license = (
        license_path
        or os.getenv(
            self.ENV_LICENSE_FILE
        )
        or self.DEFAULT_LICENSE_FILE
    )

    self.license_path = (
        self._resolve_path(
            configured_license,
            base_dir,
        )
    )

    configured_public_key = (
        public_key
        or os.getenv(
            self.ENV_PUBLIC_KEY
        )
    )

    configured_public_key_file = (
        public_key_path
        or os.getenv(
            self.ENV_PUBLIC_KEY_FILE
        )
    )

    self.public_key = (
        configured_public_key
    )

    self.public_key_path = (
        self._resolve_path(
            configured_public_key_file,
            base_dir,
        )
        if configured_public_key_file
        else None
    )

    self.expected_product = (
        expected_product
    )

    self._license_data: Optional[
        dict[str, Any]
    ] = None

    self._license_info: Optional[
        LicenseInfo
    ] = None

    self._last_validation: Optional[
        LicenseValidationResult
    ] = None

    self.history: list[
        dict[str, Any]
    ] = []

# ========================================================
# PATH
# ========================================================

@staticmethod
def _resolve_path(
    path_value: str | Path,
    base_dir: Path,
) -> Path:

    path = Path(
        str(path_value)
    )

    if not path.is_absolute():
        path = base_dir / path

    return path.resolve()

# ========================================================
# DEVICE ID
# ========================================================

@staticmethod
def get_device_id() -> str:

    """
    Generate a stable software-level device identifier.

    This is not a hardware-secure identity.
    """

    hostname = platform.node()

    processor = (
        platform.processor()
    )

    machine = (
        platform.machine()
    )

    mac = uuid.getnode()

    raw = "|".join(
        [
            hostname,
            processor,
            machine,
            str(mac),
        ]
    )

    digest = hashlib.sha256(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()

    return (
        "JARVIS-DEVICE-"
        + digest[:32].upper()
    )

# ========================================================
# LOAD PUBLIC KEY
# ========================================================

def _load_public_key_bytes(
    self,
) -> Optional[bytes]:

    if self.public_key:

        key = (
            self.public_key.strip()
            .encode("utf-8")
        )

        return key

    if (
        self.public_key_path
        and self.public_key_path.exists()
    ):

        try:

            return (
                self.public_key_path
                .read_bytes()
            )

        except OSError as exc:

            logger.error(
                "Unable to read public key: %s",
                exc,
            )

    return None

# ========================================================
# LICENSE LOADING
# ========================================================

def load_license(
    self,
    path: Optional[str | Path] = None,
) -> Optional[dict[str, Any]]:

    license_file = (
        self._resolve_path(
            path,
            self.license_path.parent,
        )
        if path
        else self.license_path
    )

    if not license_file.exists():

        self._license_data = None
        self._license_info = None

        return None

    try:

        raw = license_file.read_text(
            encoding="utf-8"
        )

        data = json.loads(
            raw
        )

        if not isinstance(
            data,
            dict,
        ):

            raise ValueError(
                "License file must contain a JSON object."
            )

        self._license_data = data

        self._license_info = (
            self._normalize_license(
                data
            )
        )

        return data

    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:

        logger.error(
            "Failed to load license: %s",
            exc,
        )

        self._license_data = None
        self._license_info = None

        return None

# ========================================================
# NORMALIZE
# ========================================================

def _normalize_license(
    self,
    data: dict[str, Any],
) -> LicenseInfo:

    license_data = data.get(
        "license",
        data,
    )

    if not isinstance(
        license_data,
        dict,
    ):

        license_data = {}

    features = license_data.get(
        "features",
        [],
    )

    if not isinstance(
        features,
        list,
    ):

        features = [
            str(features)
        ]

    metadata = license_data.get(
        "metadata",
        {},
    )

    if not isinstance(
        metadata,
        dict,
    ):

        metadata = {}

    try:

        max_devices = int(
            license_data.get(
                "max_devices",
                1,
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        max_devices = 1

    return LicenseInfo(
        license_id=str(
            license_data.get(
                "license_id",
                license_data.get(
                    "id",
                    "",
                ),
            )
            or ""
        ),
        license_key=str(
            license_data.get(
                "license_key",
                license_data.get(
                    "key",
                    "",
                ),
            )
            or ""
        ),
        product=str(
            license_data.get(
                "product",
                self.expected_product,
            )
            or ""
        ),
        version=str(
            license_data.get(
                "version",
                "",
            )
            or ""
        ),
        customer=str(
            license_data.get(
                "customer",
                "",
            )
            or ""
        ),
        email=str(
            license_data.get(
                "email",
                "",
            )
            or ""
        ),
        issued_at=str(
            license_data.get(
                "issued_at",
                "",
            )
            or ""
        ),
        expires_at=str(
            license_data.get(
                "expires_at",
                "",
            )
            or ""
        ),
        license_type=str(
            license_data.get(
                "license_type",
                license_data.get(
                    "type",
                    "standard",
                ),
            )
            or "standard"
        ),
        max_devices=max_devices,
        device_id=str(
            license_data.get(
                "device_id",
                "",
            )
            or ""
        ),
        features=[
            str(feature)
            for feature in features
        ],
        metadata=metadata,
        signature=str(
            data.get(
                "signature",
                license_data.get(
                    "signature",
                    "",
                ),
            )
            or ""
        ),
    )

# ========================================================
# CANONICAL PAYLOAD
# ========================================================

def _get_signed_payload(
    self,
    data: Optional[
        dict[str, Any]
    ] = None,
) -> bytes:

    source = (
        data
        if data is not None
        else self._license_data
    )

    if not source:

        return b""

    license_data = source.get(
        "license",
        source,
    )

    if not isinstance(
        license_data,
        dict,
    ):

        license_data = {}

    # Remove signature if it happens to be nested.
    payload = dict(
        license_data
    )

    payload.pop(
        "signature",
        None,
    )

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=False,
    )

    return canonical.encode(
        "utf-8"
    )

# ========================================================
# SIGNATURE
# ========================================================

def verify_signature(
    self,
    data: Optional[
        dict[str, Any]
    ] = None,
) -> bool:

    source = (
        data
        if data is not None
        else self._license_data
    )

    if not source:
        return False

    license_info = (
        self._normalize_license(
            source
        )
    )

    signature = (
        license_info.signature
    )

    if not signature:

        return False

    key_bytes = (
        self._load_public_key_bytes()
    )

    if not key_bytes:

        logger.warning(
            "No public key configured."
        )

        return False

    if serialization is None:

        logger.error(
            "cryptography package is not installed."
        )

        return False

    try:

        public_key = (
            serialization
            .load_pem_public_key(
                key_bytes
            )
        )

        signature_bytes = (
            base64.b64decode(
                signature,
                validate=True,
            )
        )

        public_key.verify(
            signature_bytes,
            self._get_signed_payload(
                source
            ),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

        return True

    except (
        InvalidSignature,
        ValueError,
        TypeError,
        Exception,
    ) as exc:

        logger.debug(
            "License signature verification failed: %s",
            exc,
        )

        return False

# ========================================================
# EXPIRATION
# ========================================================

@staticmethod
def _parse_datetime(
    value: str,
) -> Optional[datetime]:

    if not value:
        return None

    value = value.strip()

    try:

        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo is None:

            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    except ValueError:

        return None

def is_expired(
    self,
    license_info: Optional[
        LicenseInfo
    ] = None,
) -> bool:

    info = (
        license_info
        or self._license_info
    )

    if info is None:
        return True

    if not info.expires_at:

        # No expiry means perpetual license.
        return False

    expires = (
        self._parse_datetime(
            info.expires_at
        )
    )

    if expires is None:

        return True

    return (
        datetime.now(
            timezone.utc
        )
        >= expires
    )

# ========================================================
# DEVICE
# ========================================================

def is_device_bound(
    self,
    license_info: Optional[
        LicenseInfo
    ] = None,
) -> bool:

    info = (
        license_info
        or self._license_info
    )

    if info is None:
        return False

    return bool(
        info.device_id.strip()
    )

def is_device_match(
    self,
    license_info: Optional[
        LicenseInfo
    ] = None,
    device_id: Optional[str] = None,
) -> bool:

    info = (
        license_info
        or self._license_info
    )

    if info is None:
        return False

    if not info.device_id:

        return True

    current_device = (
        device_id
        or self.get_device_id()
    )

    return (
        info.device_id.strip().lower()
        == current_device.strip().lower()
    )

# ========================================================
# PRODUCT
# ========================================================

def is_correct_product(
    self,
    license_info: Optional[
        LicenseInfo
    ] = None,
) -> bool:

    info = (
        license_info
        or self._license_info
    )

    if info is None:
        return False

    return (
        info.product.strip().lower()
        == self.expected_product.lower()
    )

# ========================================================
# FEATURE
# ========================================================

def has_feature(
    self,
    feature: str,
) -> bool:

    if self._license_info is None:

        self.load_license()

    if self._license_info is None:
        return False

    requested = (
        str(feature)
        .strip()
        .lower()
    )

    if not requested:
        return False

    available = {
        str(item)
        .strip()
        .lower()
        for item in (
            self._license_info.features
            or []
        )
    }

    # "all" enables every feature.
    if "all" in available:
        return True

    return requested in available

# ========================================================
# VALIDATE
# ========================================================

def validate(
    self,
    license_data: Optional[
        dict[str, Any]
    ] = None,
    require_signature: bool = True,
    require_device_match: bool = True,
) -> LicenseValidationResult:

    if license_data is not None:

        self._license_data = (
            license_data
        )

        self._license_info = (
            self._normalize_license(
                license_data
            )
        )

    elif self._license_data is None:

        self.load_license()

    errors: list[str] = []
    warnings: list[str] = []

    info = self._license_info

    if info is None:

        result = (
            LicenseValidationResult(
                valid=False,
                status="not_found",
                message=(
                    "JarvisOS license was not found."
                ),
                errors=[
                    "License file is missing or invalid."
                ],
                warnings=[],
                features=[],
            )
        )

        self._record_validation(
            result
        )

        return result

    # ----------------------------------------------------
    # Required fields
    # ----------------------------------------------------

    if not info.license_id:

        errors.append(
            "License ID is missing."
        )

    if not info.product:

        errors.append(
            "Product name is missing."
        )

    if not self.is_correct_product(
        info
    ):

        errors.append(
            "License belongs to a different product."
        )

    # ----------------------------------------------------
    # Signature
    # ----------------------------------------------------

    signature_valid = (
        self.verify_signature(
            self._license_data
        )
    )

    if require_signature:

        if not signature_valid:

            errors.append(
                "License signature is invalid."
            )

    elif not signature_valid:

        warnings.append(
            "License signature could not be verified."
        )

    # ----------------------------------------------------
    # Expiration
    # ----------------------------------------------------

    expired = (
        self.is_expired(
            info
        )
    )

    if expired:

        errors.append(
            "License has expired or has an invalid expiry date."
        )

    # ----------------------------------------------------
    # Device
    # ----------------------------------------------------

    device_bound = (
        self.is_device_bound(
            info
        )
    )

    device_match = (
        self.is_device_match(
            info
        )
    )

    if (
        require_device_match
        and device_bound
        and not device_match
    ):

        errors.append(
            "License is bound to another device."
        )

    # ----------------------------------------------------
    # Result
    # ----------------------------------------------------

    valid = (
        len(errors) == 0
    )

    if valid:

        status = "valid"

        message = (
            "JarvisOS license is valid."
        )

    elif expired:

        status = "expired"

        message = (
            "JarvisOS license has expired."
        )

    elif (
        device_bound
        and not device_match
    ):

        status = "device_mismatch"

        message = (
            "This license is activated on another device."
        )

    elif not signature_valid:

        status = "invalid_signature"

        message = (
            "JarvisOS license signature is invalid."
        )

    else:

        status = "invalid"

        message = (
            "JarvisOS license validation failed."
        )

    result = (
        LicenseValidationResult(
            valid=valid,
            status=status,
            message=message,
            license_id=info.license_id,
            license_type=info.license_type,
            customer=info.customer,
            expires_at=info.expires_at,
            device_bound=device_bound,
            device_match=device_match,
            signature_valid=signature_valid,
            expired=expired,
            features=list(
                info.features or []
            ),
            errors=errors,
            warnings=warnings,
        )
    )

    self._record_validation(
        result
    )

    return result

# ========================================================
# VALIDATE KEY
# ========================================================

def validate_license_key(
    self,
    license_key: str,
    require_signature: bool = True,
    require_device_match: bool = True,
) -> LicenseValidationResult:

    """
    Validate a license supplied directly as JSON.

    The license key can be:
    - JSON string
    - Base64 encoded JSON
    """

    if not license_key:

        return LicenseValidationResult(
            valid=False,
            status="invalid",
            message=(
                "License key is empty."
            ),
            errors=[
                "No license key supplied."
            ],
            warnings=[],
            features=[],
        )

    data: Optional[
        dict[str, Any]
    ] = None

    # ----------------------------------------------------
    # Direct JSON
    # ----------------------------------------------------

    try:

        parsed = json.loads(
            license_key
        )

        if isinstance(
            parsed,
            dict,
        ):

            data = parsed

    except (
        json.JSONDecodeError,
        TypeError,
    ):

        pass

    # ----------------------------------------------------
    # Base64 JSON
    # ----------------------------------------------------

    if data is None:

        try:

            decoded = base64.b64decode(
                license_key,
                validate=True,
            ).decode(
                "utf-8"
            )

            parsed = json.loads(
                decoded
            )

            if isinstance(
                parsed,
                dict,
            ):

                data = parsed

        except (
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):

            data = None

    if data is None:

        return LicenseValidationResult(
            valid=False,
            status="invalid_format",
            message=(
                "License key format is invalid."
            ),
            errors=[
                "Expected JSON or Base64 encoded JSON."
            ],
            warnings=[],
            features=[],
        )

    return self.validate(
        license_data=data,
        require_signature=require_signature,
        require_device_match=require_device_match,
    )

# ========================================================
# SAVE LICENSE
# ========================================================

def save_license(
    self,
    license_data: dict[str, Any],
    overwrite: bool = True,
) -> bool:

    if not isinstance(
        license_data,
        dict,
    ):

        return False

    path = (
        self.license_path
    )

    if (
        path.exists()
        and not overwrite
    ):

        return False

    try:

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp_path = path.with_suffix(
            path.suffix + ".tmp"
        )

        temp_path.write_text(
            json.dumps(
                license_data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        os.replace(
            temp_path,
            path,
        )

        self._license_data = (
            license_data
        )

        self._license_info = (
            self._normalize_license(
                license_data
            )
        )

        return True

    except OSError as exc:

        logger.error(
            "Unable to save license: %s",
            exc,
        )

        return False

# ========================================================
# REMOVE LICENSE
# ========================================================

def remove_license(
    self,
    confirm: bool = False,
) -> bool:

    if not confirm:

        raise PermissionError(
            "License removal requires confirm=True."
        )

    try:

        if self.license_path.exists():

            self.license_path.unlink()

        self._license_data = None
        self._license_info = None
        self._last_validation = None

        return True

    except OSError as exc:

        logger.error(
            "Unable to remove license: %s",
            exc,
        )

        return False

# ========================================================
# GET LICENSE
# ========================================================

def get_license(
    self,
) -> Optional[LicenseInfo]:

    if self._license_info is None:

        self.load_license()

    return self._license_info

# ========================================================
# LICENSE STATUS
# ========================================================

def get_status(
    self,
) -> dict[str, Any]:

    info = self.get_license()

    result = (
        self._last_validation
    )

    return {
        "license_file": str(
            self.license_path
        ),
        "license_file_exists": (
            self.license_path.exists()
        ),
        "public_key_configured": bool(
            self._load_public_key_bytes()
        ),
        "device_id": self.get_device_id(),
        "has_license": (
            info is not None
        ),
        "license_id": (
            info.license_id
            if info
            else ""
        ),
        "product": (
            info.product
            if info
            else ""
        ),
        "license_type": (
            info.license_type
            if info
            else ""
        ),
        "customer": (
            info.customer
            if info
            else ""
        ),
        "expires_at": (
            info.expires_at
            if info
            else ""
        ),
        "expired": (
            self.is_expired(info)
            if info
            else True
        ),
        "last_validation": (
            result.to_dict()
            if result
            else None
        ),
    }

# ========================================================
# LAST RESULT
# ========================================================

def get_last_validation(
    self,
) -> Optional[
    LicenseValidationResult
]:

    return self._last_validation

# ========================================================
# HISTORY
# ========================================================

def _record_validation(
    self,
    result: LicenseValidationResult,
) -> None:

    self._last_validation = result

    self.history.append(
        {
            "timestamp": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "status": result.status,
            "valid": result.valid,
            "license_id": result.license_id,
        }
    )

    if len(
        self.history
    ) > 100:

        self.history = (
            self.history[-100:]
        )

def get_history(
    self,
    limit: int = 20,
) -> list[dict[str, Any]]:

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

    return list(
        reversed(
            self.history[-limit:]
        )
    )

# ========================================================
# LICENSE SUMMARY
# ========================================================

def summary(
    self,
) -> dict[str, Any]:

    info = self.get_license()

    if info is None:

        return {
            "active": False,
            "message": (
                "No JarvisOS license is installed."
            ),
        }

    return {
        "active": (
            self._last_validation.valid
            if self._last_validation
            else False
        ),
        "license_id": info.license_id,
        "type": info.license_type,
        "customer": info.customer,
        "expires_at": info.expires_at,
        "device_bound": bool(
            info.device_id
        ),
        "features": list(
            info.features or []
        ),
    }

# ========================================================
# CLOSE
# ========================================================

def close(self) -> None:

    self._license_data = None
    self._license_info = None
    self._last_validation = None

def __enter__(
    self,
) -> "LicenseChecker":

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

_license_checker: Optional[
LicenseChecker
] = None

def get_license_checker() -> LicenseChecker:

global _license_checker

if _license_checker is None:

    _license_checker = (
        LicenseChecker()
    )

return _license_checker

============================================================

CONVENIENCE FUNCTIONS

============================================================

def validate_license(
license_key: Optional[str] = None,
) -> LicenseValidationResult:

checker = (
    get_license_checker()
)

if license_key:

    return checker.validate_license_key(
        license_key
    )

return checker.validate()

def get_license() -> Optional[LicenseInfo]:

return (
    get_license_checker()
    .get_license()
)

def has_license_feature(
feature: str,
) -> bool:

return (
    get_license_checker()
    .has_feature(feature)
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
print(
    "JARVIS OS - LICENSE CHECKER TEST"
)
print("=" * 60)

checker = LicenseChecker()

print(
    "\nDevice ID:"
)

print(
    checker.get_device_id()
)

print(
    "\nStatus:"
)

print(
    json.dumps(
        checker.get_status(),
        indent=2,
        ensure_ascii=False,
        default=str,
    )
)

print(
    "\nLicense:"
)

license_info = (
    checker.get_license()
)

if license_info:

    print(
        json.dumps(
            asdict(license_info),
            indent=2,
            ensure_ascii=False,
        )
    )

else:

    print(
        "No license installed."
    )

print(
    "\nValidation:"
)

result = checker.validate(
    require_signature=True,
    require_device_match=True,
)

print(
    json.dumps(
        result.to_dict(),
        indent=2,
        ensure_ascii=False,
    )
)

checker.close()
