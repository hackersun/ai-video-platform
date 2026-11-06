# Upload limits and compatibility

Uploads are copied to disk in 1 MiB chunks. Actual bytes, not multipart size metadata, enforce limits. Empty, oversized, interrupted and cancelled uploads remove partial files. Assets retain the existing response and 400 validation contract and limits: image/thumbnail 20 MiB, video 300 MiB, audio 80 MiB, other artifacts 20 MiB. Voice samples retain the 30 MiB limit and 413/422 errors.

Novel import is capped at 10 MiB and staged on disk; its encoding-detecting parser still requires a bounded byte allocation after the streaming copy. Multipart parsing is handled by Starlette (spooled file); deployments should also enforce a request-size limit at the gateway to bound multipart parsing and disk usage before the endpoint runs.

S3 uses an asynchronous file iterator and a known Content-Length with the existing unsigned-payload presigned PUT. Qiniu passes a file handle to HTTPX's bounded 64 KiB multipart encoder. Both retain the existing single-request protocol, not resumable multipart uploads. No live bucket was exercised; real HTTPX request streams are tested with an in-memory transport.
