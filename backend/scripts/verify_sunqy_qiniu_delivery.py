import asyncio
from pathlib import Path

import httpx

from app.core.database import AsyncSessionLocal
from app.services.media_delivery import resolve_provider_media_url


async def main() -> None:
    static_path = Path('static/generated/qiniu-delivery-check/sunqy-check.txt')
    static_path.parent.mkdir(parents=True, exist_ok=True)
    static_path.write_text('ai-video-platform sunqy qiniu delivery check\n', encoding='utf-8')
    async with AsyncSessionLocal() as db:
        result = await resolve_provider_media_url(
            db,
            '56ae84de-951f-4e74-ac79-3550d6f6f3b2',
            '/static/generated/qiniu-delivery-check/sunqy-check.txt',
            media_type='测试文件',
        )
    provider_url = result.get('provider_url')
    print({k: v for k, v in result.items() if k != 'provider_url'})
    print('provider_url_prefix', provider_url[:140] if provider_url else None)
    if not provider_url:
        raise SystemExit(2)
    response = httpx.get(provider_url, timeout=20, follow_redirects=True)
    print('download_status', response.status_code)
    print('download_body', response.text[:120])
    if response.status_code >= 400 or 'sunqy qiniu delivery check' not in response.text:
        raise SystemExit(3)


if __name__ == '__main__':
    asyncio.run(main())
