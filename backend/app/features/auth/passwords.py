"""Password hashing and legacy verification compatibility."""

import hashlib

from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["sha256_crypt", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if hashed_password.startswith("$5$"):
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            pass
    try:
        import bcrypt

        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        pass
    if len(hashed_password) == 64:
        try:
            import secrets

            return secrets.compare_digest(
                hashlib.sha256(plain_password.encode()).hexdigest(),
                hashed_password,
            )
        except Exception:
            pass
    return False
