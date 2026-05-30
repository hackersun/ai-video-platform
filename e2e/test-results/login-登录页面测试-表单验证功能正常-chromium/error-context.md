# Page snapshot

```yaml
- generic [ref=e1]:
  - generic [ref=e3]:
    - generic [ref=e4]:
      - generic [ref=e5]:
        - img [ref=e7]
        - generic [ref=e9]: AI视频平台
      - paragraph [ref=e10]: 欢迎回来，继续创作之旅
    - generic [ref=e11]:
      - heading "用户登录" [level=3] [ref=e13]
      - generic [ref=e14]:
        - generic [ref=e15]:
          - generic [ref=e16]:
            - generic [ref=e17]: 用户名
            - generic [ref=e18]:
              - img [ref=e19]
              - textbox "请输入用户名" [ref=e22]
          - generic [ref=e23]:
            - generic [ref=e24]: 密码
            - generic [ref=e25]:
              - img [ref=e26]
              - textbox "请输入密码" [ref=e29]
          - generic [ref=e30]:
            - img [ref=e31]
            - generic [ref=e35]: 请填写用户名和密码
          - button "登录" [active] [ref=e36] [cursor=pointer]:
            - text: 登录
            - img [ref=e37]
        - paragraph [ref=e40]:
          - text: 还没有账号？
          - link "立即注册" [ref=e41] [cursor=pointer]:
            - /url: /register
    - link "← 返回首页" [ref=e43] [cursor=pointer]:
      - /url: /
  - alert [ref=e44]
```