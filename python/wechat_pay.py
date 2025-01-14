import json
import time
import random
import string
import hashlib
import requests
from datetime import datetime
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from base64 import b64decode, b64encode
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class WeChatPay:
    def __init__(self):
        # 从环境变量获取配置信息
        self.mch_id = os.getenv("WECHAT_MCH_ID")
        self.app_id = os.getenv("WECHAT_APP_ID")
        self.app_secret = os.getenv("WECHAT_APP_SECRET")
        self.api_key = os.getenv("WECHAT_API_KEY")
        self.api_v3_key = os.getenv("WECHAT_API_V3_KEY")
        self.private_key_path = os.getenv("WECHAT_PRIVATE_KEY_PATH")
        self.serial_no = os.getenv("WECHAT_CERT_SERIAL_NO")
        
        # 验证必要的配置是否存在
        self._validate_config()
        
        # 加载商户私钥
        try:
            with open(self.private_key_path) as f:
                self.private_key = RSA.import_key(f.read())
        except Exception as e:
            raise ValueError(f"加载商户私钥失败: {str(e)}")

    def _validate_config(self):
        """验证配置是否完整"""
        required_configs = [
            ("WECHAT_MCH_ID", self.mch_id),
            ("WECHAT_APP_ID", self.app_id),
            ("WECHAT_API_KEY", self.api_key),
            ("WECHAT_API_V3_KEY", self.api_v3_key),
            ("WECHAT_PRIVATE_KEY_PATH", self.private_key_path),
            ("WECHAT_CERT_SERIAL_NO", self.serial_no)
        ]
        
        missing_configs = [name for name, value in required_configs if not value]
        
        if missing_configs:
            raise ValueError(
                f"缺少必要的配置项: {', '.join(missing_configs)}\n"
                "请确保在.env文件中配置了所有必要的环境变量") # type: ignore

    def generate_sign(self, method, url_path, body):
        """生成请求签名
        签名规则参考: https://pay.weixin.qq.com/wiki/doc/apiv3/wechatpay/wechatpay4_0.shtml
        """
        timestamp = str(int(time.time()))
        nonce = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
        
        # 1. 获取HTTP请求的方法、URL、请求报文主体
        url_parts = url_path.split('?')
        canonical_url = url_parts[0]
        
        # 2. 按照顺序拼接成字符串
        # 注意：如果请求体为空，则使用空字符串""
        body_str = body if body else ''
        message = f"{method}\n{canonical_url}\n{timestamp}\n{nonce}\n{body_str}\n"
        
        print("待签名字符串:", message)  # 调试用
        
        # 3. 使用商户私钥对待签名串进行SHA256 with RSA签名
        message_hash = SHA256.new(message.encode('utf-8'))
        signature = pkcs1_15.new(self.private_key).sign(message_hash)
        sign = b64encode(signature).decode('utf-8')
        
        # 4. 设置HTTP头Authorization
        # 注意：这里返回的是构建Authorization所需的所有参数
        return {
            'timestamp': timestamp,
            'nonce': nonce,
            'signature': sign
        }

    def create_jsapi_order(self, openid, total_amount, description):
        """创建JSAPI支付订单"""
        url = "https://api.mch.weixin.qq.com/v3/pay/transactions/jsapi"
        
        # 生成商户订单号
        out_trade_no = datetime.now().strftime('%Y%m%d%H%M%S') + str(random.randint(1000, 9999))
        
        body = {
            "appid": self.app_id,
            "mchid": self.mch_id,
            "description": description,
            "out_trade_no": out_trade_no,
            "notify_url": "https://your.domain.com/notify",
            "amount": {
                "total": total_amount,
                "currency": "CNY"
            },
            "payer": {
                "openid": openid
            }
        }
        body_str = json.dumps(body)
        sign_data = self.generate_sign('POST', '/v3/pay/transactions/jsapi', body_str)
        
        # 构建认证头
        token = f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mch_id}",'
        token += f'serial_no="{self.serial_no}",'
        token += f'nonce_str="{sign_data["nonce"]}",'
        token += f'timestamp="{sign_data["timestamp"]}",'
        token += f'signature="{sign_data["signature"]}"'
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': token
        }
        
        print("Request Headers:", headers)  # 调试用
        print("Request Body:", body_str)    # 调试用
        
        response = requests.post(url, data=body_str, headers=headers)
        print("Response:", response.text)    # 调试用
        return response.json()

    def generate_js_config(self, prepay_id):
        """生成JSAPI调起支付所需的参数"""
        timestamp = str(int(time.time()))
        nonce = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
        
        message = f"{self.app_id}\n{timestamp}\n{nonce}\n{prepay_id}\n"
        message_hash = SHA256.new(message.encode('utf-8'))
        signature = pkcs1_15.new(self.private_key).sign(message_hash)
        sign = b64encode(signature).decode('utf-8')
        
        return {
            'appId': self.app_id,
            'timeStamp': timestamp,
            'nonceStr': nonce,
            'package': f'prepay_id={prepay_id}',
            'signType': 'RSA',
            'paySign': sign
        } 

    def create_native_order(self, total_amount, description):
        """创建Native支付订单"""
        url = "https://api.mch.weixin.qq.com/v3/pay/transactions/native"
        
        # 生成商户订单号
        out_trade_no = datetime.now().strftime('%Y%m%d%H%M%S') + str(random.randint(1000, 9999))
        
        body = {
            "appid": self.app_id,
            "mchid": self.mch_id,
            "description": description,
            "out_trade_no": out_trade_no,
            "notify_url": os.getenv("NOTIFY_URL"),
            "amount": {
                "total": total_amount,
                "currency": "CNY"
            }
        }
        
        body_str = json.dumps(body)
        sign_data = self.generate_sign('POST', '/v3/pay/transactions/native', body_str)
        
        # 构建认证头
        token = f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mch_id}",'
        token += f'serial_no="{self.serial_no}",'
        token += f'nonce_str="{sign_data["nonce"]}",'
        token += f'timestamp="{sign_data["timestamp"]}",'
        token += f'signature="{sign_data["signature"]}"'
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': token
        }
        
        print("Request Headers:", headers)  # 调试用
        print("Request Body:", body_str)    # 调试用
        
        response = requests.post(url, data=body_str, headers=headers)
        print("Response:", response.text)    # 调试用
        return response.json()

    def query_order_status(self, out_trade_no):
        """查询订单状态"""
        url = f"https://api.mch.weixin.qq.com/v3/pay/transactions/out-trade-no/{out_trade_no}?mchid={self.mch_id}"
        
        sign_data = self.generate_sign('GET', f'/v3/pay/transactions/out-trade-no/{out_trade_no}?mchid={self.mch_id}', '')
        
        # 构建认证头
        token = f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mch_id}",'
        token += f'serial_no="{self.serial_no}",'
        token += f'nonce_str="{sign_data["nonce"]}",'
        token += f'timestamp="{sign_data["timestamp"]}",'
        token += f'signature="{sign_data["signature"]}"'
        
        headers = {
            'Accept': 'application/json',
            'Authorization': token
        }
        
        response = requests.get(url, headers=headers)
        return response.json()

    def test_native_pay(self):
        """测试Native支付功能"""
        try:
            # 测试创建订单
            order_result = self.create_native_order(
                total_amount=1,  # 1分钱
                description="测试商品"
            )
            
            print("\n=== 创建订单响应 ===")
            print(json.dumps(order_result, indent=2, ensure_ascii=False))
            
            if 'code_url' not in order_result:
                print("创建订单失败")
                return
            
            print("\n=== 支付二维码链接 ===")
            print(order_result['code_url'])
            
            # 获取订单号用于查询
            out_trade_no = order_result.get('out_trade_no')
            
            print("\n=== 等待扫码支付 ===")
            print("请使用微信扫描二维码完成支付...")
            
            # 循环查询订单状态
            for _ in range(10):  # 最多查询10次
                time.sleep(3)  # 每3秒查询一次
                
                query_result = self.query_order_status(out_trade_no)
                status = query_result.get('trade_state', 'UNKNOWN')
                
                print(f"\n当前支付状态: {status}")
                print(json.dumps(query_result, indent=2, ensure_ascii=False))
                
                if status == 'SUCCESS':
                    print("\n=== 支付成功！===")
                    break
                
        except Exception as e:
            print(f"测试过程发生错误: {str(e)}")



# wechat_pay = WeChatPay()
# wechat_pay.test_native_pay()