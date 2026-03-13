"""
加密工具模块 - AES加密用于敏感数据
"""

import base64
import hashlib
import os
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

from app.core.config import settings


class CryptoUtil:
    """AES加密工具类"""

    _fernet: Optional[Fernet] = None

    @classmethod
    def _get_key(cls) -> bytes:
        """从配置生成加密密钥"""
        password = settings.JWT_SECRET.encode()
        salt = b"ai_model_config_salt"
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key

    @classmethod
    def _get_fernet(cls) -> Fernet:
        """获取Fernet实例"""
        if cls._fernet is None:
            cls._fernet = Fernet(cls._get_key())
        return cls._fernet

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """加密字符串"""
        if not plaintext:
            return ""
        fernet = cls._get_fernet()
        encrypted = fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        """解密字符串"""
        if not ciphertext:
            return ""
        try:
            fernet = cls._get_fernet()
            decoded = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted = fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception:
            return ""


crypto_util = CryptoUtil()
