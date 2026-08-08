"""Verified-account columns shared by the user mapping."""

from sqlalchemy import Column, DateTime, String


class VerifiedAccountColumns:
    account_status = Column(String(32), nullable=False, default="active", server_default="active")
    email_verified_at = Column(DateTime, nullable=True)
    email_verification_token_hash = Column(String(64), nullable=True, unique=True)
    email_verification_token_expires_at = Column(DateTime, nullable=True)
