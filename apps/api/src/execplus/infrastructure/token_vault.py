"""Use case: Encrypts Google refresh tokens and short-lived sign-in state at rest and in transit.

What it does: Wraps authenticated encryption so callers never handle keys or ciphertext formats.
"""

from cryptography.fernet import Fernet, InvalidToken


class FernetTokenVault:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode())

    def seal(self, text: str) -> str:
        return self._fernet.encrypt(text.encode()).decode()

    def unseal(self, sealed: str, max_age_seconds: int | None = None) -> str:
        try:
            return self._fernet.decrypt(sealed.encode(), ttl=max_age_seconds).decode()
        except (InvalidToken, ValueError):
            raise ValueError("The sealed value is invalid or expired") from None
