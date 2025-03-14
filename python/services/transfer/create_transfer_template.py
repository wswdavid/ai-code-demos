"""商家转账-发起转账API - 伪代码实现"""

import json
import time
import uuid

import requests
from Crypto.PublicKey import RSA  #  pip install pycryptodome

# 转账场景配置，用于转账时的参数获取和校验
TRANSFER_SCENES = {
    "现金营销": {
        # 在“商户平台-产品中心-商家转账”中申请转账场景权限后，页面上获取到的转账场景ID
        "scene_id": "1000",
        # 用户在客户端收款时感知到的收款原因，不同转账场景配置的传入内容不同，
        # 参考 https://pay.weixin.qq.com/doc/v3/merchant/4012711988#3.3-发起转账
        "user_perceptions": [
            "活动奖励",
            "现金奖励",
        ],
        # 各转账场景下需报备的内容，转账场景下有多个字段时需填写完整，报备内容用户不可见
        # 参考 https://pay.weixin.qq.com/doc/v3/merchant/4012711988#（3）按转账场景报备背景信息
        "report_configs": [
            {
                "info_type": "活动名称",
                "desc": "请在信息内容描述用户参与活动的名称，如新会员有礼",
            },
            {
                "info_type": "奖励说明",
                "desc": "请在信息内容描述用户因为什么奖励获取这笔资金，如注册会员抽奖一等奖",
            },
        ],
    },
    "佣金报酬": {
        "scene_id": "1002",
        "user_perceptions": ["劳务报酬", "报销款", "企业补贴", "开工利是"],
        "report_configs": [
            {
                "info_type": "岗位类型",
                "desc": "请在信息内容描述收款用户的岗位类型，如外卖员、专家顾问",
            },
            {
                "info_type": "报酬说明",
                "desc": "请请在信息内容描述用户接收当前这笔报酬的原因，如7月份配送费，高温补贴",
            },
        ],
    },
    # ... 其他场景配置保持不变 ...
}


class CreateTransfer:
    """商家转账-发起转账实现类"""

    def __init__(self):
        self.host = "https://api.mch.weixin.qq.com"
        self.path = "/v3/fund-app/mch-transfer/transfer-bills"
        self.method = "POST"
        self.mch_id = "XXX"  # 商户号，是由微信支付系统生成并分配给每个商户的唯一标识符，商户号获取方式参考https://pay.weixin.qq.com/doc/v3/merchant/4013070756
        self.private_key_serial_no = "XXX"  # 商户API证书私钥序列号，如何获取请参考https://pay.weixin.qq.com/doc/v3/merchant/4013053053
        self.private_key_filepath = "path/to/wechatpay/xx_cert"  # 商户API证书私钥文件路径
        self.public_key_serial_no = "XXX"  # 微信支付公钥序列号，如何获取请参考https://pay.weixin.qq.com/doc/v3/merchant/4013038816
        self.public_key_filepath = "path/to/wechatpay/certificate.pem"  # 微信支付公钥文件路径

        self._load_keys_from_file()

    def _load_keys_from_file(self):
        """加载商户API私钥和微信支付公钥"""
        self.private_key = RSA.import_key(open(self.private_key_filepath, "r").read())
        self.public_key = RSA.import_key(open(self.public_key_filepath, "r").read())

    def create_transfer_order(
        self,
    ):
        """
        商家转账-发起转账
        https://pay.weixin.qq.com/doc/v3/merchant/4012716434

        商家转账用户确认模式下，用户申请收款时，商户可通过此接口申请创建转账单
        - 接口返回的HTTP状态码及错误码，仅代表本次请求的结果，不能代表订单状态。
        - 接口返回的HTTP状态码为200，且订单状态为ACCEPTED时，可认为发起商家转账成功。
        - 接口返回的HTTP状态码不为200时，请商户务必不要立即更换商户订单号重试。可根据错误码列表中的描述和接口返回的信息进行处理，并在查询原订单结果为失败或者联系客服确认情况后，再更换商户订单号进行重试。否则会有重复转账的资金风险。
        注：单个商户的接口频率限制为100次/s

        重要说明：
            1. 同一笔转账订单的商户订单号（out_bill_no）重入时，请求参数需要保持一致
            2. 当HTTP状态码为5XX或者429时，可以尝试重试，但必须使用原商户订单号
            3. 敏感信息加密时需要使用【微信支付公钥】或【微信支付平台证书公钥】
            4. 建议在调用接口前检查商户账户余额是否充足
        """

        # 1. 构造请求包体
        body = self.make_request_body()

        # 2. 验证请求包体
        self.validate_request_body(body)

        # 3. 发送请求
        http_response = self.send_request(body)

        # 4. 解析HTTP状态码
        self.check_status_code(http_response)

        # 5. 验证HTTP响应结果
        self.validate_response(http_response)

        # 6. 解析HTTP响应结果
        return self.parse_response(http_response)

    def make_request_body(
        self,
    ):
        """
        商家转账-发起转账-构造请求参数

        需要严格按照参数说明要求以及业务实际情况，构造以下请求参数
        必填参数：
        - appid string(32): 申请商户号的AppID或商户号绑定的AppID（企业号corpid即为此AppID）
        - out_bill_no string(32): 商户系统内部的商家单号，要求此参数只能由数字、大小写字母组成，在商户系统内部唯一
        - openid string(64): 用户的openid，商户某Appid下，获取用户openid参考 https://pay.weixin.qq.com/doc/v3/merchant/4012068676#OpenID
        - transfer_amount int: 转账金额，单位为分
        - transfer_scene_id string(32): 转账场景，在"商户平台-产品中心-商家转账"中申请的转账场景，申请权限通过后才可使用。转账场景需配置字段，参考 TRANSFER_SCENES 中的描述
        - transfer_scene_report_infos (Array): 转账报备信息列表。每个场景要求的报备信息不同，参考 TRANSFER_SCENES 中的描述，按照要求传入报备信息
            「现金营销」-转账场景示例（需填入活动名称、奖励说明）：
            [
                {"info_type": "活动名称", "info_content": "新会员有礼"},
                {"info_type": "奖励说明", "info_content": "注册会员抽奖一等奖"}
            ]
        - transfer_remark string(32): 转账备注，用户收款时可见，UTF8编码，最多32个字符。参考 https://pay.weixin.qq.com/doc/v3/merchant/4012711988
        - user_name: transfer_amount >= 200000 时必填，需要使用公钥加密

        选填参数：
        - user_recv_perception string: 用户在客户端收款时感知到的收款原因，参考 TRANSFER_SCENES 中的描述
        - user_name string: 收款用户姓名。当转账金额>=2000元时必填，需要使用【微信支付公钥】或【微信支付平台证书公钥】加密。参考 https://pay.weixin.qq.com/doc/v3/merchant/4013053257
        - notify_url string(256): 回调通知地址，通知URL必须为公网可访问的URL，必须为HTTPS，且不能携带参数。

        备注:
        - 转账场景(transfer_scene_id) | 用户收款感知(user_recv_perception) | 转账报备信息(transfer_scene_report_infos) 存在映射关联关系，可参考文档 https://pay.weixin.qq.com/doc/v3/merchant/4012711988
        - 如果涉及字段加密，需要使用公钥加密，同时请求头部中需要加上使用加密公钥的证书ID

        参考示例:
        >curl -X POST \
            https://api.mch.weixin.qq.com/v3/fund-app/mch-transfer/transfer-bills \
            -H "Authorization: WECHATPAY2-SHA256-RSA2048 mchid=\"1900000001\",..." \
            -H "Accept: application/json" \
            -H "Wechatpay-Serial: 5157F09EFDC096DE15EBE81A47057A7232F1B8E1"  \
            -H "Content-Type: application/json" \
            -d '{
                "appid" : "wxf636efh567hg4356",
                "out_bill_no" : "plfk2020042013",
                "transfer_scene_id" : "1000",
                "openid" : "o-MYE42l80oelYMDE34nYD456Xoy",
                "user_name" : "757b340b45ebef5467rter35gf464344v3542sdf4t6re4tb4f54ty45t4yyry45",
                "transfer_amount" : 400000,
                "transfer_remark" : "2020年4月报销",
                "notify_url" : "https://www.weixin.qq.com/wxpay/pay.php",
                "user_recv_perception" : "现金奖励",
                "transfer_scene_report_infos" : [
                {
                    "info_type" : "活动名称",
                    "info_content" : "新会员有礼"
                },
                {
                    "info_type" : "奖励说明",
                    "info_content" : "注册会员抽奖一等奖"
                }
                ]
            }'
        """
        # 商家转账-发起转账-构造请求参数 生成示例，需选中该注释，通过 @demo 指令触发
        raise NotImplementedError("This method needs to be implemented.")

    def send_request(self, body: dict):
        # 1. 构造请求头（生成签名）
        body_str = json.dumps(body)
        headers = self.make_request_header(body_str)

        # 发送 http 请求 读取 self.method 和 self.url
        http_response = requests.request(
            self.method,
            self.host + self.path,
            headers=headers,
            data=body_str,
        )
        return http_response

    def make_request_header(self, body_str: str):
        """
        商家转账-发起转账-构造请求头
        """
        sign_data = self.generate_sign(
            self.method,
            self.path,
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

    def validate_request_body(
        self,
        transfer_data: dict,
    ):
        """
        商家转账-发起转账-验证请求参数

        必填参数：
        appid
        out_bill_no
        openid
        transfer_amount
        transfer_scene_id
        transfer_remark
        transfer_scene_report_infos
        user_name: transfer_amount >= 200000 时必填，需要加密

        参数类型校验（string 如果指定了长度需要校验）：
        appid: string(32)
        out_bill_no: string(32)
        openid: string(64)
        transfer_amount: int
        transfer_scene_id: string(32)
        transfer_remark: string(32)
        notify_url: string(256)
        transfer_scene_report_infos - info_type: string(15)
        transfer_scene_report_infos - info_content: string(32)

        参数规则：
        out_bill_no: 商户系统内部的商家单号，要求此参数只能由数字、大小写字母组成，在商户系统内部唯一
        notify_url: 必须为HTTPS，且不能携带参数

        请验证 1. 必填参数是否存在，2. 填入的参数类型/长度是否正确，验证不通过则抛出异常 3. 参数值是否符合业务规则
        """
        # 商家转账-发起转账-验证请求参数 生成示例，需选中该注释，通过 @demo 指令触发
        raise NotImplementedError("This method needs to be implemented.")

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
        raise ValueError(f"HTTP 状态码异常: {status_code} response={http_response.json()}")

    def parse_response(
        self,
        http_response: requests.models.Response,
    ):
        """
        商家转账-发起转账-解析回包结果

        返回转账业务结果示例：
        {
            "out_bill_no" : "plfk2020042013",
            "transfer_bill_no" : "1330000071100999991182020050700019480001",
            "create_time" : "2015-05-20T13:29:35.120+08:00",
            "state" : "ACCEPTED",
            "fail_reason" : "PAYEE_ACCOUNT_ABNORMAL",
            "package_info" : "affffddafdfafddffda=="
        }

        转账状态-处理建议:
        - ACCEPTED:
            # 转账已受理
        - PROCESSING:
            # 转账锁定资金中。如果一直停留在该状态，建议检查账户余额是否足够，如余额不足，可充值后再原单重试。
        - TRANSFERING:
            # 转账中，可拉起微信收款确认页面再次重试确认收款
        - WAIT_USER_CONFIRM:
            # 待收款用户确认，可拉起微信收款确认页面进行收款确认
        - SUCCESS:
            # 转账成功
        - FAIL:
            # 转账失败
        - CANCELING:
            # 商户撤销请求受理成功，该笔转账正在撤销中
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


# 使用示例
if __name__ == "__main__":
    create_transfer = CreateTransfer()
    create_transfer.create_transfer_order()
