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
from loguru import logger
from Crypto.Cipher import AES
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from services.wechat_pay_base import WeChatPayBase
# 加载环境变量
load_dotenv()

class WeChatPay(WeChatPayBase):

    def create_jsapi_order(self, openid, total_amount, description):
        """创建JSAPI支付订单"""
        logger.info(f"开始创建JSAPI支付订单 - openid: {openid}, 金额: {total_amount}分")
        url = "https://api.mch.weixin.qq.com/v3/pay/transactions/jsapi"
        
        # 生成商户订单号
        out_trade_no = datetime.now().strftime('%Y%m%d%H%M%S') + str(random.randint(1000, 9999))
        logger.info(f"生成商户订单号: {out_trade_no}")
        
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
        logger.debug(f"JSAPI支付请求参数: {body_str}")
        
        sign_data = self.generate_sign('POST', '/v3/pay/transactions/jsapi', body_str)
        
        # 构建认证头
        token = (f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mch_id}",'
                f'serial_no="{self.serial_no}",'
                f'nonce_str="{sign_data["nonce"]}",'
                f'timestamp="{sign_data["timestamp"]}",'
                f'signature="{sign_data["signature"]}"')
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': token
        }
        
        logger.debug(f"发送JSAPI支付请求 - URL: {url}")
        response = requests.post(url, data=body_str, headers=headers)
        logger.info(f"JSAPI支付响应状态码: {response.status_code}")
        logger.debug(f"JSAPI支付响应内容: {response.text}")
        
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
        logger.info(f"开始创建Native支付订单 - 金额: {total_amount}分")
        url = "https://api.mch.weixin.qq.com/v3/pay/transactions/native"
        
        # 生成商户订单号
        out_trade_no = datetime.now().strftime('%Y%m%d%H%M%S') + str(random.randint(1000, 9999))
        logger.info(f"生成商户订单号: {out_trade_no}")
        
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
        logger.debug(f"Native支付请求参数: {body_str}")
        
        sign_data = self.generate_sign('POST', '/v3/pay/transactions/native', body_str)
        
        # 构建认证头
        token = (f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mch_id}",'
                f'serial_no="{self.serial_no}",'
                f'nonce_str="{sign_data["nonce"]}",'
                f'timestamp="{sign_data["timestamp"]}",'
                f'signature="{sign_data["signature"]}"')
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': token
        }
        
        logger.debug(f"发送Native支付请求 - URL: {url}")
        response = requests.post(url, data=body_str, headers=headers)
        logger.info(f"Native支付响应状态码: {response.status_code}")
        logger.debug(f"Native支付响应内容: {response.text}")
        response_json = response.json()
        response_json['out_trade_no'] = out_trade_no
        return response_json

    def query_order_status(self, out_trade_no):
        """查询订单状态"""
        logger.info(f"开始查询订单状态 - 商户订单号: {out_trade_no}")
        
        # 构建请求URL,注意URL编码
        url_path = f"/v3/pay/transactions/out-trade-no/{out_trade_no}?mchid={self.mch_id}"
        url = f"https://api.mch.weixin.qq.com{url_path}"
        
        # 生成签名,注意这里不要对URL进行编码
        sign_data = self.generate_sign('GET', url_path, '')
        
        # 构建认证头,注意各个字段之间不能有空格
        token = (f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mch_id}",'
                f'serial_no="{self.serial_no}",'
                f'nonce_str="{sign_data["nonce"]}",'
                f'timestamp="{sign_data["timestamp"]}",'
                f'signature="{sign_data["signature"]}"')
        
        headers = {
            'Accept': 'application/json',
            'Authorization': token,
        }
        
        logger.debug(f"发送订单查询请求 - URL: {url}")
        logger.debug(f"请求头: {headers}")
        
        response = requests.get(url, headers=headers)
        logger.info(f"订单查询响应状态码: {response.status_code}")
        logger.debug(f"订单查询响应内容: {response.text}")
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

    def refund_order(self, out_trade_no, amount, reason=""):
        """申请退款"""
        logger.info(f"开始处理退款请求 - 商户订单号: {out_trade_no}, 金额: {amount}分")
        url = "https://api.mch.weixin.qq.com/v3/refund/domestic/refunds"
        
        # 生成退款单号
        out_refund_no = datetime.now().strftime('R%Y%m%d%H%M%S') + str(random.randint(1000, 9999))
        
        body = {
            "out_trade_no": out_trade_no,
            "out_refund_no": out_refund_no,
            "reason": reason,
            "notify_url": os.getenv("NOTIFY_URL"),
            "amount": {
                "refund": amount,
                "total": amount,
                "currency": "CNY"
            }
        }
        
        body_str = json.dumps(body)
        logger.debug(f"退款请求参数: {body_str}")
        
        sign_data = self.generate_sign('POST', '/v3/refund/domestic/refunds', body_str)
        
        # 构建认证头
        token = (f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mch_id}",'
                f'serial_no="{self.serial_no}",'
                f'nonce_str="{sign_data["nonce"]}",'
                f'timestamp="{sign_data["timestamp"]}",'
                f'signature="{sign_data["signature"]}"')
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': token
        }
        
        logger.debug(f"发送退款请求 - URL: {url}")
        response = requests.post(url, data=body_str, headers=headers)
        logger.info(f"退款响应状态码: {response.status_code}")
        logger.debug(f"退款响应内容: {response.text}")
        
        return response.json()

    def verify_notify_sign(self, headers, body):
        """验证回调通知签名"""
        timestamp = headers.get('Wechatpay-Timestamp')
        nonce = headers.get('Wechatpay-Nonce')
        signature = headers.get('Wechatpay-Signature')
        serial_no = headers.get('Wechatpay-Serial')
        body_str = body.decode('utf-8')
        logger.info(f"收到回调通知头部信息: timestamp={timestamp}, nonce={nonce}, "
                    f"signature={signature}, serial_no={serial_no}")     
        
        if not all([timestamp, nonce, signature, serial_no]):
            logger.error("回调通知缺少必要的头部信息")
            return False
   
        # 构造验签名串
        message = f"{timestamp}\n{nonce}\n{body_str}\n"
        logger.debug(f"验签名串: {message}")
        
        try:
            # 从证书管理器获取微信支付平台证书
            wechatpay_cert_path = os.getenv("WECHAT_PAY_PLAT_CERT_PATH")
            with open(wechatpay_cert_path) as f:  # 需要下载微信支付平台证书
                cert = RSA.import_key(f.read())
            # 验证签名
            message_hash = SHA256.new(message.encode('utf-8'))
            signature_bytes = b64decode(signature)
            pkcs1_15.new(cert).verify(message_hash, signature_bytes)
            logger.info("签名验证成功")
            return True
        except Exception as e:
            logger.error(f"验证签名失败: {str(e)}")
            return False

    def decrypt_notify_data(self, body):
        """解密回调通知数据"""
        try:
            data = json.loads(body)
            resource = data.get('resource', {})
            nonce = resource.get('nonce')
            ciphertext = resource.get('ciphertext')
            associated_data = resource.get('associated_data')

            # Base64解码密文
            ciphertext_bytes = b64decode(ciphertext)
            
            # 使用AEAD_AES_256_GCM算法解密
            key_bytes = self.api_v3_key.encode('utf-8')
            nonce_bytes = nonce.encode('utf-8')
            ad_bytes = associated_data.encode('utf-8') if associated_data else b''
            
            aesgcm = AESGCM(key_bytes)
            decrypted_data = aesgcm.decrypt(nonce_bytes, ciphertext_bytes, ad_bytes)
            
            return json.loads(decrypted_data)
        except Exception as e:
            logger.error(f"解密回调数据失败: {str(e)}")
            return None


