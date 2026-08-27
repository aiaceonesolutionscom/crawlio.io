"""SQLAlchemy column type that transparently encrypts/decrypts through
app.core.crypto — used for OAuth tokens so every read/write path is covered
automatically instead of relying on each service function to remember to
encrypt before saving and decrypt before using.
"""
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core.crypto import decrypt_token, encrypt_token


class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_token(value)

    def process_result_value(self, value, dialect):
        return decrypt_token(value)
