from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class TokenCryptoError(Exception):
    pass


def _fernet(key: str) -> Fernet:
    try:
        return Fernet(key.encode("utf-8"))
    except Exception as e:  # pragma: no cover
        raise TokenCryptoError("Invalid CALENDAR_TOKEN_KEY") from e


def encrypt(*, plaintext: str, key: str) -> bytes:
    return _fernet(key).encrypt(plaintext.encode("utf-8"))


def decrypt(*, ciphertext: bytes, key: str) -> str:
    try:
        return _fernet(key).decrypt(ciphertext).decode("utf-8")
    except InvalidToken as e:
        raise TokenCryptoError("Token decrypt failed") from e

