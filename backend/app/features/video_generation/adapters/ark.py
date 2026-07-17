"""Volcano ARK client construction."""

from typing import Optional


def create_ark_client(api_key: str, base_url: Optional[str] = None):
    from volcenginesdkarkruntime import Ark

    return Ark(
        base_url=base_url or "https://ark.cn-beijing.volces.com/api/v3",
        api_key=api_key,
    )
