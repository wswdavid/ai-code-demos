import os
import time
import random
import string
import logging
from base64 import b64decode, b64encode
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import json
logger = logging.getLogger(__name__)

class WeChatPayBase:
    """微信支付基础类，处理公共功能"""
    
    def __init__(self):
        # 从环境变量获取配置信息
        self.mch_id = os.getenv("WECHAT_MCH_ID")
        self.app_id = os.getenv("WECHAT_APP_ID")
        self.app_secret = os.getenv("WECHAT_APP_SECRET")
        self.api_key = os.getenv("WECHAT_API_KEY")
        self.api_v3_key = os.getenv("WECHAT_API_V3_KEY")
        self.private_key_path = os.getenv("WECHAT_PRIVATE_KEY_PATH")
        self.serial_no = os.getenv("WECHAT_CERT_SERIAL_NO")
        self.platform_cert_path = os.getenv("WECHAT_PAY_PLAT_CERT_PATH")
        self.platform_cert = None
        self.private_key = None
        logger.info("初始化微信支付配置")
        # 验证必要的配置是否存在
        self._validate_config()
        
        # 加载商户私钥
        self._load_private_key()
        
        # 加载微信支付平台证书
        self._load_platform_cert()

    def _load_platform_cert(self):
        """加载微信支付平台证书"""
        try:
            platform_cert_path = os.getenv("WECHAT_PAY_PLAT_CERT_PATH")
            if not platform_cert_path:
                error_msg = "缺少微信支付平台证书路径配置: WECHAT_PAY_PLAT_CERT_PATH"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            with open(platform_cert_path) as f:
                self.platform_cert = RSA.import_key(f.read())
            logger.info("成功加载微信支付平台证书")
        except Exception as e:
            error_msg = f"加载微信支付平台证书失败: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

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
            error_msg = f"缺少必要的配置项: {', '.join(missing_configs)}\n请确保在.env文件中配置了所有必要的环境变量"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def _load_private_key(self):
        """加载商户私钥"""
        try:
            with open(self.private_key_path) as f:
                self.private_key = RSA.import_key(f.read())
            logger.info("成功加载商户私钥")
        except Exception as e:
            error_msg = f"加载商户私钥失败: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def generate_sign(self, method, url_path, body):
        """生成请求签名"""
        timestamp = str(int(time.time()))
        nonce = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
        
        body_str = body if body else ''
        message = f"{method}\n{url_path}\n{timestamp}\n{nonce}\n{body_str}\n"
        
        logger.debug(f"待签名字符串: {message}")
        
        message_hash = SHA256.new(message.encode('utf-8'))
        signature = pkcs1_15.new(self.private_key).sign(message_hash)
        sign = b64encode(signature).decode('utf-8')
        
        return {
            'timestamp': timestamp,
            'nonce': nonce,
            'signature': sign
        }

    def decrypt_sensitive_data(self, ciphertext, nonce, associated_data):
        """解密微信支付敏感数据
        
        Args:
            ciphertext (str): Base64编码的密文
            nonce (str): 加密使用的随机串
            associated_data (str): 附加数据
            
        Returns:
            dict: 解密后的明文数据
        """
        try:
            # 将密文、随机串、附加数据转换为bytes
            key_bytes = self.api_v3_key.encode('utf-8')
            nonce_bytes = nonce.encode('utf-8')
            associated_data_bytes = associated_data.encode('utf-8') if associated_data else b''
            ciphertext_bytes = b64decode(ciphertext)

            # 使用AEAD_AES_256_GCM算法解密
            aesgcm = AESGCM(key_bytes)
            plaintext_bytes = aesgcm.decrypt(
                nonce_bytes,
                ciphertext_bytes,
                associated_data_bytes
            )
            
            # 将明文转换为字典
            plaintext = plaintext_bytes.decode('utf-8')
            logger.debug(f"解密得到明文: {plaintext}")
            return json.loads(plaintext)
            
        except Exception as e:
            error_msg = f"解密敏感数据失败: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def encrypt_sensitive_data(self, plaintext):
        """加密敏感数据
        
        Args:
            plaintext (str): 需要加密的明文数据
            
        Returns:
            dict: 包含密文、随机串、附加数据的字典
        """
        try:
            # 生成随机串
            nonce = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
            
            # 将明文、密钥、随机串转换为bytes
            plaintext_bytes = plaintext.encode('utf-8')
            key_bytes = self.api_v3_key.encode('utf-8')
            nonce_bytes = nonce.encode('utf-8')
            
            # 使用AEAD_AES_256_GCM算法加密
            aesgcm = AESGCM(key_bytes)
            ciphertext = aesgcm.encrypt(
                nonce_bytes,
                plaintext_bytes,
                None
            )
            
            # Base64编码密文
            ciphertext_b64 = b64encode(ciphertext).decode('utf-8')
            
            result = {
                'ciphertext': ciphertext_b64,
                'nonce': nonce,
                'associated_data': None
            }
            
            logger.debug(f"加密结果: {result}")
            return result
            
        except Exception as e:
            error_msg = f"加密敏感数据失败: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
