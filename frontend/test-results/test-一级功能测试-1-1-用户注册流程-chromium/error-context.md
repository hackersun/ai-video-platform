# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e4]:
    - generic [ref=e5]:
      - img [ref=e7]
      - heading "AI视频平台" [level=1] [ref=e10]
      - paragraph [ref=e11]: 创建账号，开始创作之旅
    - generic [ref=e12]:
      - heading "注册新账号" [level=2] [ref=e13]
      - generic [ref=e14]:
        - generic [ref=e15]:
          - generic [ref=e16]: 邮箱
          - textbox "your@email.com" [ref=e17]
        - generic [ref=e18]:
          - generic [ref=e19]: 用户名
          - textbox "3-20个字符" [ref=e20]
        - generic [ref=e21]:
          - generic [ref=e22]: 昵称 (可选)
          - textbox "显示名称" [ref=e23]
        - generic [ref=e24]:
          - generic [ref=e25]: 密码
          - generic [ref=e26]:
            - textbox "至少8个字符" [ref=e27]
            - button [ref=e28] [cursor=pointer]:
              - img [ref=e29]
        - generic [ref=e32]:
          - generic [ref=e33]: 确认密码
          - textbox "再次输入密码" [ref=e34]
        - button "创建账号" [ref=e35] [cursor=pointer]
      - paragraph [ref=e36]:
        - text: 已有账号？
        - link "立即登录" [ref=e37] [cursor=pointer]:
          - /url: /login
  - alert [ref=e38]
```