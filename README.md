
## 核心类说明

### WeChatPay 类 (wechat_pay.py)

主要方法：
- `create_jsapi_order()`: 创建JSAPI支付订单
- `create_native_order()`: 创建Native支付订单
- `generate_sign()`: 生成请求签名
- `query_order_status()`: 查询订单状态
- `generate_js_config()`: 生成JSAPI支付配置

### Flask路由 (app.py)

主要接口：
- `/native_pay`: Native支付页面
- `/create_native_order`: 创建Native支付订单
- `/query_order`: 查询订单状态
- `/wx_auth`: 微信授权
- `/wx_callback`: 授权回调
- `/notify`: 支付结果通知

## 使用流程

### JSAPI支付流程

1. 用户访问支付页面
2. 获取用户openid（通过微信授权）
3. 创建支付订单
4. 调起微信支付
5. 用户完成支付
6. 接收支付结果通知

### Native支付流程

1. 访问扫码支付页面
2. 点击生成支付二维码
3. 创建支付订单
4. 生成二维码
5. 用户扫码支付
6. 轮询支付结果
7. 接收支付结果通知

## 安全说明

- 敏感配置信息存放在环境变量中
- 使用 API v3 密钥加密
- 验证支付通知签名
- 使用 HTTPS 传输
- 妥善保管商户私钥

## 开发建议

1. 本地开发：
   - 使用测试商户号
   - 配置小额支付
   - 启用调试日志

2. 生产部署：
   - 使用 HTTPS
   - 配置正确的回调域名
   - 关闭调试输出
   - 添加日志记录
   - 完善错误处理

## 常见问题

1. 签名验证失败
   - 检查私钥文件是否正确
   - 确认签名参数格式

2. 获取openid失败
   - 检查授权配置
   - 确认回调域名设置

3. 支付失败
   - 查看错误码说明
   - 检查订单参数
   - 确认金额格式

## 参考文档

- [微信支付官方文档](https://pay.weixin.qq.com/wiki/doc/apiv3/index.shtml)
- [Flask官方文档](https://flask.palletsprojects.com/)
- [Python-dotenv文档](https://github.com/theskumar/python-dotenv)

## 贡献指南

欢迎提交 Issue 和 Pull Request。在提交代码前，请确保：

1. 代码经过格式化 (`black`)
2. 通过代码检查 (`flake8`)
3. 通过类型检查 (`mypy`)
4. 添加必要的注释和文档

## 许可证

[MIT License](LICENSE)