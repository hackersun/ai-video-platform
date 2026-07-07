# 七牛 Kodo 静态媒体出口配置

本地开发库默认使用 `dev-user-001`。运行下面命令可把七牛 Kodo 域名配置为默认对象存储 / CDN 出口：

```bash
python3 backend/scripts/configure_qiniu_storage.py \
  --db-path backend/ai_video.db \
  --user-id dev-user-001 \
  --public-base-url http://thsbi8hnj.hn-bkt.clouddn.com
```

当前七牛默认域名 `thsbi8hnj.hn-bkt.clouddn.com` 的 HTTPS 证书不匹配，所以使用 HTTP。绑定自定义 HTTPS 域名后，把 `--public-base-url` 替换为正式域名再运行一次即可。

平台会把本地 `/static/...` 资源映射到七牛域名下，例如：

```text
/static/generated/assets/images/example.png
-> http://thsbi8hnj.hn-bkt.clouddn.com/static/generated/assets/images/example.png
```

因此上传到七牛时，对象 key 需要保持 `static/generated/...` 这套路径。
