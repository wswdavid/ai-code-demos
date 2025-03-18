"""商家转账-撤销转账API - 伪代码实现"""

import json
import time
import uuid

import requests
from Crypto.PublicKey import RSA  #  pip install pycryptodome


class CancelTransfer:
    """商家转账-撤销转账实现类"""

    def __init__(self):
        self.host = "https://api.mch.weixin.qq.com"
        self.path = "/v3/fund-app/mch-transfer/transfer-bills/out-bill-no/{out_bill_no}/cancel"
        self.method = "POST"
        self.mch_id = "XXX"  # 商户号，是由微信支付系统生成并分配给每个商户的唯一标识符，商户号获取方式参考https://pay.weixin.qq.com/doc/v3/merchant/4013070756
        self.private_key_serial_no = "XXX"  # 商户API证书私钥序列号，如何获取请参考https://pay.weixin.qq.com/doc/v3/merchant/4013053053
        self.private_key_filepath = "path/to/wechatpay/xx_cert.pem"  # 商户API证书私钥文件路径，本地文件路径
        self.public_key_serial_no = "XXX"  # 微信支付公钥序列号，如何获取请参考https://pay.weixin.qq.com/doc/v3/merchant/4013038816
        self.public_key_filepath = "path/to/wechatpay/certificate.pem"  # 微信支付公钥文件路径，本地文件路径
        self._load_keys_from_file()

    def _load_keys_from_file(self):
        """加载商户API证书私钥和微信支付公钥"""
        self.private_key = RSA.import_key(open(self.private_key_filepath, "r").read())
        self.public_key = RSA.import_key(open(self.public_key_filepath, "r").read())

    def run(self):
        """
        商家转账-撤销转账
        商户通过转账接口发起付款后，在用户确认收款之前可以通过该接口撤销付款。该接口返回成功仅表示撤销请求已受理，系统会异步处理退款等操作，以最终查询单据返回状态为准。
        """

        # 构造请求 path 参数
        path_params = self.make_request_path_params()

        # 验证请求 path 参数
        self.validate_request_path_params(path_params)

        # 发送请求
        http_response = self.send_request(path_params=path_params)

        # 解析HTTP状态码
        self.check_status_code(http_response)

        # 验证HTTP响应结果
        self.validate_response(http_response)

        # 解析HTTP响应结果
        return self.parse_response(http_response)

    def make_request_path_params(self):
        """
        商家转账-撤销转账-构造请求 path 参数

        必填参数：
        - out_bill_no

        参数类型校验（string 如果指定了长度需要校验）：
        - out_bill_no: string(32)

        参数规则：
        - out_bill_no: 此参数只能由数字、大小写字母组成
        """
        # 商家转账-微信单号查询电子回单-构造请求参数 生成示例，需选中该注释，通过 @demo 指令触发
        raise NotImplementedError("This method needs to be implemented.")

    def validate_request_path_params(self, path_params: dict):
        """
        商家转账-撤销转账-验证请求 path 参数

        必填参数：
        - out_bill_no

        参数类型校验（string 如果指定了长度需要校验）：
        - out_bill_no: string(32)

        参数规则：
        - out_bill_no: 此参数只能由数字、大小写字母组成

        请验证
                1. 必填参数是否存在
                2. 填入的参数类型/长度是否正确，验证不通过则抛出异常。string 如果指定了长度需要校验。
                3. 参数值是否符合业务规则，要符合参数中的描述
        """
        # 商家转账-商户单号查询电子回单-验证请求参数 生成示例，需选中该注释，通过 @demo 指令触发
        raise NotImplementedError("This method needs to be implemented.")

    def send_request(self, *, query_params: dict = None, path_params: dict = None, body: dict = None):
        path = self.path.format(**path_params) if path_params else self.path
        # path 拼接 query_params
        path = path + "?" + "&".join([f"{k}={v}" for k, v in query_params.items()]) if query_params else path

        # 拼接 body
        body_str = json.dumps(body) if body else ""

        # 构造请求头（生成签名）
        headers = self.make_request_header(path, body_str)

        # 发送 http 请求
        http_response = requests.request(
            self.method,
            self.host + path,
            headers=headers,
            data=body_str,
        )
        return http_response

    def make_request_header(self, path: str, body_str: str):
        """
        构造请求头
        """
        sign_data = self.generate_sign(
            self.method,
            path,
            body_str,
        )

        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Wechatpay-Serial": self.public_key_serial_no,
            "Authorization": (
                f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mch_id}",'
                f'nonce_str="{sign_data["nonce"]}",'
                f'timestamp="{sign_data["timestamp"]}",'
                f'serial_no="{self.private_key_serial_no}",'
                f'signature="{sign_data["signature"]}"'
            ),
        }

    def check_status_code(
        self,
        http_response: requests.models.Response,
    ):
        """
        解析HTTP响应状态码，如果非 2XX 则抛出异常

        HTTP状态码-处理建议:
            1. 2XX (成功): 继续处理业务逻辑
            2. 400 (PARAM_ERROR): 请根据错误信息调整请求参数
            3. 400（INVALID_REQUEST）: 请求不符合业务规则，请查看文档：https://pay.weixin.qq.com/doc/v3/merchant/4012716434
            4. 401（SIGN_ERROR）: 签名错误，请检查签名是否正确：https://pay.weixin.qq.com/doc/v3/merchant/4012072670
            5. 403（NO_AUTH）: 商户无权限使用该接口，请查看文档：https://pay.weixin.qq.com/doc/v3/merchant/4012716434
            6. 429 (请求频率超限): 请求实现限流控制，延迟重试，重试时必须使用原商户订单号和原参数，请不要更换订单号和修改原参数
            7. 5XX (服务端错误):
                - 系统异常，请稍后重试
                - 重要：查询原订单结果为失败或者联系客服确认情况后，再更换商户订单号进行重试。否则会有重复转账的资金风险。
        """
        status_code = http_response.status_code
        if 200 <= status_code < 300:
            # 2XX 成功
            return
        raise NotImplementedError(f"HTTP 状态码异常: {status_code} response={http_response.json()}")

    def parse_response(
        self,
        http_response: requests.models.Response,
    ):
        """
        返回参数说明：
        - out_bill_no string(32): 商户系统内部的商家单号
        - transfer_bill_no string(64): 微信转账单号，商家转账订单的主键，唯一定义此资源的标识
        - state string: 单据状态，CANCELING: 撤销中；CANCELLED:已撤销
        - update_time string: 最后一次单据状态变更时间，按照使用rfc3339所定义的格式，格式为yyyy-MM-DDThh:mm:ss+TIMEZONE

        返回撤销转账结果示例：
        {
            "out_bill_no" : "plfk2020042013",
            "transfer_bill_no" : "1330000071100999991182020050700019480001",
            "state" : "CANCELING",
            "update_time" : "2015-05-20T13:29:35.120+08:00"
        }

        【state 单据状态】处理建议:
            - CANCELING:
                # 商户撤销请求受理成功，该笔转账正在撤销中（需通过最终查询确认撤销结果）
            - CANCELLED:
                # 转账撤销完成
        """
        # 商家转账-发起转账-解析回包结果 生成示例，需选中该注释，通过 @demo 指令触发
        raise NotImplementedError("This method needs to be implemented.")

    def generate_sign(
        self,
        method: str,
        path: str,
        body_str: str,
    ):
        """生成请求签名"""

        import json
        from base64 import b64encode

        from Crypto.Hash import SHA256
        from Crypto.Signature import pkcs1_15

        timestamp = int(time.time())
        nonce = str(uuid.uuid4())
        message = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_str}\n"

        message_hash = SHA256.new(message.encode("utf-8"))
        signature = pkcs1_15.new(self.private_key).sign(message_hash)
        sign = b64encode(signature).decode("utf-8")
        return {"timestamp": timestamp, "nonce": nonce, "signature": sign}

    def validate_response(
        self,
        http_response: requests.models.Response,
    ):
        """
        验证微信支付回包：使用公钥验证微信支付 API 接口返回的微信支付签名是否正确
        """
        import json
        from base64 import b64decode

        from Crypto.Hash import SHA256
        from Crypto.Signature import pkcs1_15

        header = http_response.headers
        request_id = header.get("Request-Id", "").strip()
        timestamp = int(header.get("Wechatpay-Timestamp", "").strip())
        print("header=", header)
        # 验证时间戳
        if abs(time.time() - timestamp) >= 300:  # 5 minutes
            raise ValueError(f"Timestamp=[{timestamp}] expires, request-id=[{request_id}]")

        # 验证序列号
        serial_no = header.get("Wechatpay-Serial", "").strip()
        if serial_no != self.public_key_serial_no:
            raise ValueError(f"Serial-no=[{serial_no}] is not match, expected=[{self.public_key_serial_no}]")

        # 验证签名
        signature = header.get("Wechatpay-Signature", "").strip()
        nonce = header.get("Wechatpay-Nonce", "").strip()
        body_str = http_response.content.decode("utf-8")
        message = f"{timestamp}\n{nonce}\n{body_str}\n"
        message_hash = SHA256.new(message.encode("utf-8"))
        signature_bytes = b64decode(signature)
        pkcs1_15.new(self.public_key).verify(message_hash, signature_bytes)
        print("签名验证成功")

    def encrypt(self, data):
        """
        使用公钥加密字符串，采用 OAEP padding 方式
        """
        from base64 import b64encode

        from Crypto.Cipher import PKCS1_OAEP
        from Crypto.Hash import SHA1

        cipher = PKCS1_OAEP.new(self.public_key, hashAlgo=SHA1)
        encrypted_data = cipher.encrypt(data.encode("utf-8"))
        return b64encode(encrypted_data).decode("utf-8")
