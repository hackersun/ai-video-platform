"""
安全模块 - API密钥加密/解密
"""
import os
import base64
from cryptography.fernet import Fernet


def get_encryption_key():
    """获取加密密钥"""
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        # 生成新密钥（首次启动时）
        key = Fernet.generate_key().decode()
        print(f"⚠️  新生成加密密钥: {key[:20]}... (请保存到环境变量 ENCRYPTION_KEY)")
    return key


# 初始化加密套件
_cipher_suite = None


def get_cipher():
    """获取加密套件单例"""
    global _cipher_suite
    if _cipher_suite is None:
        key = get_encryption_key()
        # 确保密钥是base64编码的
        if isinstance(key, str):
            key = key.encode() if len(key) == 44 else base64.urlsafe_b64decode(key)
        _cipher_suite = Fernet(key)
    return _cipher_suite


def encrypt_api_key(key: str) -> str:
    """加密API密钥"""
    cipher = get_cipher()
    return cipher.encrypt(key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """解密API密钥"""
    cipher = get_cipher()
    return cipher.decrypt(encrypted_key.encode()).decode()