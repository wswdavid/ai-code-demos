from flask import Flask, request, jsonify, render_template, redirect, session
from wechat_pay import WeChatPay
import requests
from urllib.parse import quote
from flask_session import Session
import qrcode
import io
import base64

app = Flask(__name__)
wechat_pay = WeChatPay()

app.secret_key = 'your_secret_key'  # session需要密钥
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create_order', methods=['POST'])
def create_order():
    try:
        data = request.get_json()
        openid = data.get('openid')
        amount = data.get('amount')  # 金额（单位：分）
        description = data.get('description', '商品描述')
        
        # 创建订单
        order_result = wechat_pay.create_jsapi_order(openid, amount, description)
        
        if 'prepay_id' in order_result:
            # 生成JSAPI调起支付所需的参数
            js_config = wechat_pay.generate_js_config(order_result['prepay_id'])
            return jsonify({'code': 0, 'data': js_config})
        else:
            return jsonify({'code': -1, 'msg': '创建订单失败', 'error': order_result})
            
    except Exception as e:
        return jsonify({'code': -1, 'msg': str(e)})

@app.route('/notify', methods=['POST'])
def notify():
    """支付结果通知处理"""
    # 验证签名等安全处理
    # 处理支付结果
    return jsonify({'code': 'SUCCESS', 'message': 'OK'})

@app.route('/wx_auth')
def wx_auth():
    """发起微信授权"""
    # 授权后回调地址
    redirect_uri = quote('https://你的域名/wx_callback')
    
    # 构造授权URL
    auth_url = (
        f"https://open.weixin.qq.com/connect/oauth2/authorize?"
        f"appid={wechat_pay.app_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=snsapi_base&"  # snsapi_base仅获取openid，snsapi_userinfo获取用户信息
        f"state=STATE#wechat_redirect"
    )
    return redirect(auth_url)

@app.route('/wx_callback')
def wx_callback():
    """微信授权回调"""
    code = request.args.get('code')
    if not code:
        return '授权失败'
    
    # 通过code获取access_token和openid
    url = (
        f"https://api.weixin.qq.com/sns/oauth2/access_token?"
        f"appid={wechat_pay.app_id}&"
        f"secret={wechat_pay.app_secret}&"  # 需要在WeChatPay类中添加app_secret
        f"code={code}&"
        f"grant_type=authorization_code"
    )
    
    resp = requests.get(url)
    result = resp.json()
    
    if 'openid' in result:
        # 将openid存入session
        session['openid'] = result['openid']
        return redirect('/pay')  # 重定向到支付页面
    else:
        return '获取openid失败'

@app.route('/pay')
def pay():
    """支付页面"""
    openid = session.get('openid')
    if not openid:
        return redirect('/wx_auth')
    return render_template('pay.html', openid=openid)

@app.route('/native_pay')
def native_pay():
    """Native支付页面"""
    return render_template('native_pay.html')

@app.route('/create_native_order', methods=['POST'])
def create_native_order():
    try:
        data = request.get_json()
        amount = data.get('amount')  # 金额（单位：分）
        description = data.get('description', '商品描述')
        
        # 创建订单
        order_result = wechat_pay.create_native_order(amount, description)
        
        if 'code_url' in order_result:
            # 生成二维码
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(order_result['code_url'])
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # 转换为base64
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            qr_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            return jsonify({
                'code': 0, 
                'data': {
                    'qr_code': qr_base64,
                    'out_trade_no': order_result.get('out_trade_no')
                }
            })
        else:
            return jsonify({'code': -1, 'msg': '创建订单失败', 'error': order_result})
            
    except Exception as e:
        return jsonify({'code': -1, 'msg': str(e)})

@app.route('/query_order', methods=['POST'])
def query_order():
    """查询订单状态"""
    try:
        data = request.get_json()
        out_trade_no = data.get('out_trade_no')
        
        if not out_trade_no:
            return jsonify({'code': -1, 'msg': '缺少订单号'})
            
        result = wechat_pay.query_order_status(out_trade_no)
        
        if 'trade_state' in result:
            return jsonify({'code': 0, 'data': result})
        else:
            return jsonify({'code': -1, 'msg': '查询失败', 'error': result})
            
    except Exception as e:
        return jsonify({'code': -1, 'msg': str(e)})

if __name__ == '__main__':
    app.run(debug=True) 