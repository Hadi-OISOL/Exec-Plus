"""Use case: Protects local passwords using bounded memory-hard hashing.

What it does: Uses fixed scrypt parameters, independent salts and constant-time comparisons.
"""

import hashlib
import hmac
import secrets
from threading import BoundedSemaphore

from execplus.domain.ingestion import IngestionError

_HASH_SLOTS = BoundedSemaphore(2)
_PREFIX = "scrypt-v1$131072$8$1$"


class ScryptPasswords:
    def _derive(self, password: str, salt: bytes) -> bytes:
        if not _HASH_SLOTS.acquire(blocking=False):
            raise IngestionError(
                "authentication_busy", "Sign-in is busy. Please try again shortly.", 503
            )
        try:
            return hashlib.scrypt(
                password.encode("utf-8"),
                salt=salt,
                n=131072,
                r=8,
                p=1,
                maxmem=256 * 1024 * 1024,
                dklen=64,
            )
        finally:
            _HASH_SLOTS.release()

    def hash(self, password: str) -> str:
        salt = secrets.token_bytes(32)
        return _PREFIX + salt.hex() + "$" + self._derive(password, salt).hex()

    def verify(self, password: str, stored: str | None) -> bool:
        salt, expected, valid = b"execplus-dummy-hash-salt-32-bytes!", bytes(64), False
        if stored and stored.startswith(_PREFIX) and len(stored) == len(_PREFIX) + 64 + 1 + 128:
            try:
                raw_salt, raw_hash = stored[len(_PREFIX) :].split("$")
                salt, expected = bytes.fromhex(raw_salt), bytes.fromhex(raw_hash)
                valid = len(salt) == 32 and len(expected) == 64
            except ValueError:
                valid = False
        calculated = self._derive(password, salt)
        return hmac.compare_digest(calculated, expected) and valid
