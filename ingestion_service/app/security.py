"""
Security utilities for encryption and API key validation.
"""
from base64 import b64encode
from cryptography.fernet import Fernet
from typing import Optional
import hashlib

from app.config import get_settings


def get_fernet_key(key: str) -> bytes:
    """
    Convert a key string to Fernet-compatible key.

    Args:
        key: Raw encryption key (any string)

    Returns:
        URL-safe base64-encoded key suitable for Fernet
    """
    # Hash the key to get 32 bytes (256 bits)
    hashed = hashlib.sha256(key.encode()).digest()
    # Base64 encode to get 44 bytes (Fernet requires 32-byte key, base64 encoded)
    return b64encode(hashed)


def get_cipher() -> Fernet:
    """Get Fernet cipher instance from settings."""
    settings = get_settings()
    key = get_fernet_key(settings.encryption_key)
    return Fernet(key)


def decrypt_payload(encrypted_data: str) -> dict:
    """
    Decrypt encrypted payload from SAP middleware.

    Args:
        encrypted_data: Base64-encoded encrypted JSON string

    Returns:
        Decrypted data as dictionary

    Raises:
        ValueError: If decryption fails
    """
    try:
        cipher = get_cipher()
        decrypted_bytes = cipher.decrypt(encrypted_data.encode())
        import json
        return json.loads(decrypted_bytes.decode())
    except Exception as e:
        raise ValueError(f"Failed to decrypt payload: {e}")


def encrypt_payload(data: dict) -> str:
    """
    Encrypt data payload (for testing/debugging).

    Args:
        data: Dictionary to encrypt

    Returns:
        Encrypted string (base64-encoded)
    """
    cipher = get_cipher()
    import json
    json_str = json.dumps(data)
    encrypted_bytes = cipher.encrypt(json_str.encode())
    return encrypted_bytes.decode()


def validate_api_key(api_key: Optional[str]) -> bool:
    """
    Validate API key from request headers.

    Args:
        api_key: API key from X-API-Key header

    Returns:
        True if valid, False otherwise
    """
    if not api_key:
        return False

    settings = get_settings()
    return api_key in settings.api_keys_list


def hash_api_key(api_key: str) -> str:
    """
    Hash API key for logging (don't log actual keys).

    Args:
        api_key: Raw API key

    Returns:
        Hashed version (first 8 chars of SHA256)
    """
    return hashlib.sha256(api_key.encode()).hexdigest()[:8]
