# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e4]:
    - generic [ref=e5]:
      - img [ref=e7]
      - heading "AI视频平台" [level=1] [ref=e10]
      - paragraph [ref=e11]: 智能创作，触手可及
    - generic [ref=e12]:
      - heading "欢迎回来" [level=2] [ref=e13]
      - generic [ref=e14]:
        - generic [ref=e15]:
          - generic [ref=e16]: 用户名或邮箱
          - textbox "请输入用户名或邮箱" [ref=e17]
        - generic [ref=e18]:
          - generic [ref=e19]: 密码
          - generic [ref=e20]:
            - textbox "请输入密码" [ref=e21]
            - button [ref=e22] [cursor=pointer]:
              - img [ref=e23]
        - button "登录" [ref=e26] [cursor=pointer]
      - generic [ref=e31]: 或
      - paragraph [ref=e32]:
        - text: 还没有账号？
        - link "立即注册" [ref=e33] [cursor=pointer]:
          - /url: /register
    - paragraph [ref=e34]: 登录即表示同意我们的服务条款和隐私政策
  - alert [ref=e35]
```