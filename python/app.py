import base64
import io
import sys
from urllib.parse import quote

import qrcode
import requests
from flask import Flask, jsonify, redirect, render_template, request, session
from loguru import logger

from flask_session import Session
from services.pay.wechat_pay import WeChatPay
from services.transfer.create_transfer import CreateTransfer

# 配置日志
logger.remove()  # 清除默认的控制台输出
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    "logs/wechat_pay_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO",
    encoding="utf-8",
)

app = Flask(__name__)
wechat_pay = WeChatPay()


app.secret_key = "your_secret_key"  # session需要密钥
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/create_order", methods=["POST"])
def create_order():
    try:
        data = request.get_json()
        logger.info(f"收到JSAPI支付请求: {data}")
        openid = data.get("openid")
        amount = data.get("amount")  # 金额（单位：分）
        description = data.get("description", "商品描述")

        if not openid or not amount:
            logger.warning("JSAPI支付请求缺少必要参数")
            return jsonify({"code": -1, "msg": "缺少必要参数"})

        # 创建订单
        order_result = wechat_pay.create_jsapi_order(openid, amount, description)
        logger.info(f"JSAPI支付创建订单结果: {order_result}")

        if "prepay_id" in order_result:
            # 生成JSAPI调起支付所需的参数
            js_config = wechat_pay.generate_js_config(order_result["prepay_id"])
            logger.info(f"JSAPI支付配置生成成功: {js_config}")
            return jsonify({"code": 0, "data": js_config})
        else:
            logger.error(f"JSAPI支付创建订单失败: {order_result}")
            return jsonify({"code": -1, "msg": "创建订单失败", "error": order_result})

    except Exception as e:
        logger.exception(f"JSAPI支付处理异常: {str(e)}")
        return jsonify({"code": -1, "msg": str(e)})


@app.route("/wxpay/notify", methods=["POST"])
def notify():
    """支付结果通知处理"""
    logger.info("收到支付结果通知")
    try:
        # 获取原始请求数据
        body = request.get_data()
        logger.info(f"收到原始通知数据: {body}")

        # 验证签名
        if not wechat_pay.verify_notify_sign(request.headers, body):
            logger.error("回调通知验签失败")
            return jsonify({"code": "FAIL", "message": "验签失败"}), 401

        # 解密通知数据
        decoded_data = wechat_pay.decrypt_notify_data(body)
        if not decoded_data:
            logger.error("解密回调数据失败")
            return jsonify({"code": "FAIL", "message": "解密失败"}), 401

        logger.info(f"解密后的通知数据: {decoded_data}")

        # 处理支付结果
        event_type = decoded_data.get("event_type")
        if event_type == "TRANSACTION.SUCCESS":
            # 支付成功
            trade_state = decoded_data.get("trade_state")
            out_trade_no = decoded_data.get("out_trade_no")
            transaction_id = decoded_data.get("transaction_id")
            trade_type = decoded_data.get("trade_type")
            amount = decoded_data.get("amount", {}).get("total")

            logger.info(
                f"支付成功 - 商户订单号: {out_trade_no}, 微信支付单号: {transaction_id}, "
                f"交易状态: {trade_state}"
            )
            logger.info(f"支付方式: {trade_type}, 支付金额: {amount}分")
            logger.info(f"解密后的通知数据: {decoded_data}")
            # TODO: 在这里处理您的业务逻辑
            # 例如：更新订单状态、发货等

        return jsonify({"code": "SUCCESS", "message": "成功"})
    except Exception as e:
        logger.exception(f"处理支付通知异常: {str(e)}")
        return jsonify({"code": "FAIL", "message": str(e)}), 500


@app.route("/wx_auth")
def wx_auth():
    """发起微信授权"""
    logger.info("开始微信授权流程")
    # 授权后回调地址
    redirect_uri = quote("https://你的域名/wx_callback")

    # 构造授权URL
    auth_url = (
        f"https://open.weixin.qq.com/connect/oauth2/authorize?"
        f"appid={wechat_pay.app_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=snsapi_base&"
        f"state=STATE#wechat_redirect"
    )
    logger.debug(f"构造的授权URL: {auth_url}")
    return redirect(auth_url)


@app.route("/wx_callback")
def wx_callback():
    """微信授权回调"""
    logger.info("收到微信授权回调")
    code = request.args.get("code")
    if not code:
        logger.warning("未收到授权code")
        return "授权失败"

    logger.info(f"收到授权code: {code}")
    # 通过code获取access_token和openid
    url = (
        f"https://api.weixin.qq.com/sns/oauth2/access_token?"
        f"appid={wechat_pay.app_id}&"
        f"secret={wechat_pay.app_secret}&"
        f"code={code}&"
        f"grant_type=authorization_code"
    )

    resp = requests.get(url)
    result = resp.json()
    logger.info(f"获取access_token响应: {result}")

    if "openid" in result:
        # 将openid存入session
        session["openid"] = result["openid"]
        logger.info(f"授权成功，获取到openid: {result['openid']}")
        return redirect("/pay")
    else:
        logger.error(f"获取openid失败: {result}")
        return "获取openid失败"


@app.route("/pay")
def pay():
    """支付页面"""
    openid = session.get("openid")
    if not openid:
        return redirect("/wx_auth")
    return render_template("pay.html", openid=openid)


@app.route("/native_pay")
def native_pay():
    """Native支付页面"""
    return render_template("native_pay.html")


@app.route("/create_native_order", methods=["POST"])
def create_native_order():
    try:
        data = request.get_json()
        logger.info(f"收到Native支付请求: {data}")
        amount = data.get("amount")
        description = data.get("description", "商品描述")

        if not amount:
            logger.warning("Native支付请求缺少必要参数")
            return jsonify({"code": -1, "msg": "缺少必要参数"})

        # 创建订单
        order_result = wechat_pay.create_native_order(amount, description)
        logger.info(f"Native支付创建订单结果: {order_result}")

        if "code_url" in order_result:
            # 生成二维码
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(order_result["code_url"])
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            # 转换为base64
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            qr_base64 = base64.b64encode(buffered.getvalue()).decode()

            logger.info(
                f"Native支付二维码生成成功，订单号: {order_result.get('out_trade_no')}"
            )
            return jsonify(
                {
                    "code": 0,
                    "data": {
                        "qr_code": qr_base64,
                        "out_trade_no": order_result.get("out_trade_no"),
                    },
                }
            )
        else:
            logger.error(f"Native支付创建订单失败: {order_result}")
            return jsonify({"code": -1, "msg": "创建订单失败", "error": order_result})

    except Exception as e:
        logger.exception(f"Native支付处理异常: {str(e)}")
        return jsonify({"code": -1, "msg": str(e)})


@app.route("/query_order", methods=["POST"])
def query_order():
    """查询订单状态"""
    try:
        data = request.get_json()
        logger.info(f"收到订单查询请求: {data}")
        out_trade_no = data.get("out_trade_no")

        if not out_trade_no:
            logger.warning("订单查询缺少订单号")
            return jsonify({"code": -1, "msg": "缺少订单号"})

        result = wechat_pay.query_order_status(out_trade_no)
        logger.info(f"订单查询结果: {result}")

        if "trade_state" in result:
            logger.info(
                f"订单查询成功，订单号: {out_trade_no}, 状态: {result['trade_state']}"
            )
            return jsonify({"code": 0, "data": result})
        else:
            logger.error(f"订单查询失败，订单号: {out_trade_no}, 错误信息: {result}")
            return jsonify({"code": -1, "msg": "查询失败", "error": result})

    except Exception as e:
        logger.exception(f"订单查询异常: {str(e)}")
        return jsonify({"code": -1, "msg": str(e)})


@app.route("/refund")
def refund_page():
    """退款页面"""
    return render_template("refund.html")


@app.route("/do_refund", methods=["POST"])
def do_refund():
    """处理退款请求"""
    try:
        data = request.get_json()
        logger.info(f"收到退款请求: {data}")

        out_trade_no = data.get("out_trade_no")
        amount = data.get("amount")
        reason = data.get("reason", "")

        if not out_trade_no or not amount:
            logger.warning("退款请求缺少必要参数")
            return jsonify({"code": -1, "msg": "缺少必要参数"})

        result = wechat_pay.refund_order(out_trade_no, amount, reason)
        logger.info(f"退款结果: {result}")

        if "status" in result:
            logger.info(
                f"退款申请成功，订单号: {out_trade_no}, 金额: {amount}分, 状态: {result['status']}"
            )
            return jsonify({"code": 0, "data": result})
        else:
            logger.error(f"退款失败，订单号: {out_trade_no}, 错误信息: {result}")
            return jsonify({"code": -1, "msg": "退款失败", "error": result})

    except Exception as e:
        logger.exception(f"退款处理异常: {str(e)}")
        return jsonify({"code": -1, "msg": str(e)})


@app.route("/transfer")
def transfer_page():
    """转账页面"""
    return render_template("transfer.html")


@app.route("/create_transfer", methods=["POST"])
def create_transfer():
    """创建转账订单"""
    try:
        data = request.get_json()
        logger.info(f"收到转账请求: {data}")

        openid = data.get("openid")
        amount = data.get("amount")
        remark = data.get("remark", "")
        if not openid or not amount:
            logger.warning("转账请求缺少必要参数")
            return jsonify({"code": -1, "msg": "缺少必要参数"})
        wechat_transfer = CreateTransfer()
        result = wechat_transfer.create_transfer_order(
            openid=openid,
            amount=amount,
            remark=remark,
            # user_recv_perception=user_recv_perception,
            # user_name=user_name,
            # notify_url=notify_url
        )
        logger.info(f"转账结果: {result}")
        return jsonify(result)

    except Exception as e:
        logger.exception(f"转账处理异常: {str(e)}")
        return jsonify({"code": -1, "msg": str(e)})


@app.route("/query_transfer", methods=["POST"])
def query_transfer():
    """查询转账状态"""
    try:
        data = request.get_json()
        logger.info(f"收到转账查询请求: {data}")

        out_bill_no = data.get("out_bill_no")

        if not out_bill_no:
            logger.warning("转账查询缺少商户单号")
            return jsonify({"code": -1, "msg": "缺少商户单号"})

        wechat_transfer = CreateTransfer()
        result = wechat_transfer.query_transfer_order(out_bill_no)
        logger.info(f"转账查询结果: {result}")
        return jsonify(result)

    except Exception as e:
        logger.exception(f"转账查询异常: {str(e)}")
        return jsonify({"code": -1, "msg": str(e)})


if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",  # 只监听本地
        port=5000,
    )
