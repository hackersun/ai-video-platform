"""Qiniu Kodo configuration driver sharing media-delivery validation rules."""

from app.features.model_drivers.adapters._shared import unsupported_poll, unsupported_submit
from app.features.model_drivers.domain import DriverTestResult


def check_qiniu_config(
    *, public_base_url, params, api_key, api_secret, public_url_check,
) -> tuple[str, str]:
    if not public_base_url:
        return "failed", "缺少公网基础地址，请填写 CDN/对象存储公开域名"
    if not public_url_check(public_base_url):
        return "failed", "公网基础地址必须是云端可访问的 http(s) URL，不能使用 localhost、内网或相对路径"
    bucket = str(params.get("bucket") or params.get("bucket_name") or "").strip()
    if not api_key or not api_secret or not bucket:
        return "failed", "七牛对象存储需要配置 Access Key、Secret Key 和 bucket，不能仅映射公网域名"
    upload_url = str(params.get("upload_url") or "https://upload.qiniup.com").strip()
    if not public_url_check(upload_url):
        return "failed", "七牛上传地址必须是云端可访问的 http(s) URL"
    local_prefix = str(params.get("local_static_prefix") or "/static/")
    public_prefix = str(params.get("public_static_prefix") or "/static/")
    if not local_prefix.startswith("/") or not public_prefix.startswith("/"):
        return "failed", "静态路径前缀必须以 / 开头"
    return "success", f"七牛对象存储上传出口可用：{public_base_url.rstrip('/')}{public_prefix.rstrip('/')}/..."


class QiniuKodoDriver:
    key = "qiniu_kodo_v1"
    capabilities = frozenset({"object_storage"})

    async def test_connection(self, context):
        params = context.connection_params
        public_base_url = str(params.get("public_base_url") or context.base_url or "").strip()
        from app.services.media_delivery import is_cloud_accessible_http_url

        status, message = check_qiniu_config(
            public_base_url=public_base_url, params=params,
            api_key=context.api_key, api_secret=context.api_secret,
            public_url_check=is_cloud_accessible_http_url,
        )
        normalized = "connection_verified" if status == "success" else "failed"
        return DriverTestResult(normalized, message, {"bucket_configured": status == "success"})

    async def submit(self, _command, _context):
        return unsupported_submit()

    poll = staticmethod(unsupported_poll)
