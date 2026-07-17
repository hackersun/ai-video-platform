"""Existing external-capability connection checks, moved out of the API route."""

from app.features.model_drivers.adapters.local_ffmpeg import check_local_ffmpeg
from app.features.model_drivers.adapters.qiniu_kodo import check_qiniu_config


def _test_object_storage(config, base_url, extra, public_url_check) -> tuple[str, str]:
    public_base_url = (extra.get("public_base_url") or base_url).strip()
    storage_provider = str(extra.get("storage_provider") or extra.get("provider") or "").strip().lower()
    if storage_provider in {"qiniu", "kodo", "qiniu_kodo"}:
        return check_qiniu_config(
            public_base_url=public_base_url, params=extra,
            api_key=config.get_api_key_decrypted(), api_secret=config.get_api_secret_decrypted(),
            public_url_check=public_url_check,
        )
    if not public_base_url:
        return "failed", "缺少公网基础地址，请填写 CDN/对象存储公开域名"
    if not public_url_check(public_base_url):
        return "failed", "公网基础地址必须是云端可访问的 http(s) URL，不能使用 localhost、内网或相对路径"
    local_prefix = extra.get("local_static_prefix") or "/static/"
    public_prefix = extra.get("public_static_prefix") or "/static/"
    if not str(local_prefix).startswith("/") or not str(public_prefix).startswith("/"):
        return "failed", "静态路径前缀必须以 / 开头"
    return "success", f"对象存储/CDN公网出口可用：{public_base_url.rstrip('/')}{str(public_prefix).rstrip('/')}/..."


async def test_external_connection(
    config, provider, *, http_client_factory, dev_mode, which, public_url_check,
) -> tuple[str, str]:
    provider_key = provider.name
    extra = config.extra_config or {}
    base_url = (config.custom_base_url or provider.base_url or "").rstrip("/")

    if provider_key == "local_ffmpeg":
        binary = extra.get("binary_path") or "ffmpeg"
        return check_local_ffmpeg(binary, which)

    if provider_key == "comfyui":
        if not base_url:
            return "failed", "ComfyUI 需要配置服务地址"
        health_path = extra.get("health_path") or "/system_stats"
        try:
            async with http_client_factory(timeout=min(config.timeout or 20, 20)) as client:
                response = await client.get(f"{base_url}{health_path}")
            if response.status_code < 400:
                return "success", "ComfyUI 服务可访问"
            return "failed", f"ComfyUI 健康检查失败：HTTP {response.status_code}"
        except Exception as exc:
            if dev_mode():
                return "configured", f"配置已保存，但 DEV_MODE 未连通 ComfyUI：{exc}"
            return "failed", f"ComfyUI 连接失败：{exc}"

    if provider_key in {"ffmpeg_cloud", "lip_sync"} and base_url:
        health_path = extra.get("health_path") or "/health"
        try:
            headers = {}
            api_key = config.get_api_key_decrypted()
            if api_key and provider.auth_type != "none":
                header = provider.auth_header or "Authorization"
                headers[header] = f"Bearer {api_key}" if provider.auth_type == "bearer" else api_key
            async with http_client_factory(timeout=min(config.timeout or 20, 20)) as client:
                response = await client.get(f"{base_url}{health_path}", headers=headers)
            if response.status_code < 400:
                return "success", f"{provider.name_cn or provider.name} 服务可访问"
            return "failed", f"健康检查失败：HTTP {response.status_code}"
        except Exception as exc:
            if dev_mode():
                return "configured", f"配置已保存，但 DEV_MODE 未连通远端服务：{exc}"
            return "failed", f"连接失败：{exc}"

    if provider_key in {"openai", "google", "runway", "qwen"}:
        if provider.auth_type != "none" and not config.get_api_key_decrypted():
            return "failed", "缺少 API Key"
        if extra.get("validate_live"):
            if not base_url:
                return "failed", "缺少基础 URL"
            return "configured", "已开启真实验证，但该提供商需在提交任务时按具体模型接口验证权限"
        return "configured", "配置完整；真实任务提交时会按供应商接口验证权限和额度"

    if provider_key == "object_storage":
        return _test_object_storage(config, base_url, extra, public_url_check)

    return "configured", "配置完整；该适配器将在任务提交时验证"
