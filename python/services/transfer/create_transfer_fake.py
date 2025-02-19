"""创建商家转账API - 伪代码实现"""

# 转账场景配置，用于转账时的参数获取和校验
TRANSFER_SCENES = {
    "现金营销": {
        # 在“商户平台-产品中心-商家转账”中申请转账场景权限后，页面上获取到的转账场景ID
        "scene_id": "1000",
        # 用户在客户端收款时感知到的收款原因，不同转账场景配置的传入内容不同，
        # 参考 https://pay.weixin.qq.com/doc/v3/merchant/4012711988#3.3-%E5%8F%91%E8%B5%B7%E8%BD%AC%E8%B4%A6
        "user_perceptions": [
            "活动奖励",
            "现金奖励",
        ],
        # 各转账场景下需报备的内容，转账场景下有多个字段时需填写完整，报备内容用户不可见
        # 参考 https://pay.weixin.qq.com/doc/v3/merchant/4012711988#%EF%BC%883%EF%BC%89%E6%8C%89%E8%BD%AC%E8%B4%A6%E5%9C%BA%E6%99%AF%E6%8A%A5%E5%A4%87%E8%83%8C%E6%99%AF%E4%BF%A1%E6%81%AF
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
    """创建商家转账实现类"""

    def __init__(self):
        """
        初始化方法
        - 设置API配置
        """
        self.API_CONFIG = {
            # 接口请求方法
            "method": "POST",
            # 接口请求路径
            "path": "/v3/fund-app/mch-transfer/transfer-bills",
            # 接口描述
            "desc": "商家转账-发起转账",
        }
        pass

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

        # ! 1. 构造请求参数
        transfer_data: dict = self._get_request_data()

        # ! 2. 验证请求参数
        is_valid = self.validate_request_params(transfer_data)

        # ! 3. 生成签名，构造请求头，发送API请求
        http_response = self._make_request(transfer_data)

        # ! 4. 处理HTTP状态码
        http_result = self.handle_http_result(http_response)

        # ! 5. 处理业务响应结果
        transfer_result = self.handle_transfer_result(http_result)

        return

    def _get_request_data(
        self,
    ):
        """
        需要严格按照参数说明要求以及业务实际情况，构造以下请求参数
            必填参数：
                - appid string(32): 申请商户号的AppID或商户号绑定的AppID（企业号corpid即为此AppID）
                - out_bill_no (str): 商户系统内部的商家单号，要求此参数只能由数字、大小写字母组成，在商户系统内部唯一
                - openid (str): 用户的openid，商户某Appid下，获取用户openid参考 https://pay.weixin.qq.com/doc/v3/merchant/4012068676#OpenID
                - amount (int): 转账金额，单位为分
                - transfer_scene_id (int): 转账场景，在“商户平台-产品中心-商家转账”中申请的转账场景，申请权限通过后才可使用。转账场景需配置字段，参考 TRANSFER_SCENES 中的描述
                - transfer_scene_report_infos (Array): 转账报备信息列表。每个场景要求的报备信息不同，参考 TRANSFER_SCENES 中的描述，按照要求传入报备信息
                    「现金营销」-转账场景示例（需填入活动名称、奖励说明）：
                    [
                        {"info_type": "活动名称", "info_content": "新会员有礼"},
                        {"info_type": "奖励说明", "info_content": "注册会员抽奖一等奖"}
                    ]
                - transfer_remark (str): 转账备注，用户收款时可见，UTF8编码，最多32个字符。参考 https://pay.weixin.qq.com/doc/v3/merchant/4012711988
            选填参数：
                - user_recv_perception (str): 用户在客户端收款时感知到的收款原因，参考 TRANSFER_SCENES 中的描述
                - user_name (str): 收款用户姓名。当转账金额>=2000元时必填，需要使用【微信支付公钥】或【微信支付平台证书公钥】加密。参考 https://pay.weixin.qq.com/doc/v3/merchant/4013053257
                - notify_url (str): 回调通知地址，通知URL必须为公网可访问的URL，必须为HTTPS，且不能携带参数。

        备注:
        - 转账场景(transfer_scene_id) | 用户收款感知(user_recv_perception) | 转账报备信息(transfer_scene_report_infos) 存在映射关联关系，可参考 TRANSFER_SCENES 中的配置
        - 如果涉及字段加密，需要使用公钥加密，同时请求头部中需要加上使用加密公钥的证书ID
        """

    def validate_request_params(self, transfer_data: dict):
        """
        验证请求参数

        建议验证场景:
            1. 检查必填字段是否存在
            2. 验证转账金额范围
                - 单笔金额限额
            3. 验证大额转账的用户姓名
                - 如果转账金额大于2000元，需要传入可选参数 user_name，传入时且需要使用公钥加密
            4. 验证转账备注格式
                - UTF8编码，最多允许32个字符
            5. 验证转账场景
                - 转账场景(transfer_scene_id) | 用户收款感知(user_recv_perception) | 转账报备信息(transfer_scene_report_infos) 存在映射关联关系，需根据转账场景按照规则填入
        """

    def handle_http_result(self):
        """
        处理HTTP请求结果

        HTTP状态码-处理建议:
            1. 2XX (成功):
                - 继续处理业务逻辑
            2. 429 (请求频率超限):
                - 请求实现限流控制
                - 延迟重试
                - 重要：重试时必须使用原商户订单号和原参数，请不要更换订单号和修改原参数
            3. 5XX (服务端错误):
                - 记录错误日志
                - 建议：先查询订单状态，确认订单不存在才重试
                - 重要：重试时必须使用原商户订单号，避免重复转账风险
            4. 其他错误:
                - 记录详细错误信息
                - 检查请求参数是否正确
                - 验证签名是否正确
                - 确认证书是否有效
                - 重要：4XX错误通常表示请求有误，修复问题后可使用原商户订单号和原参数重试

        验证微信支付签名:
            - 使用公钥验证微信支付API接口返回的微信支付签名是否正确
            - 文件下载接口需要跳过验签流程
        """

    def handle_transfer_result(self, data: dict):
        """
        处理转账业务结果

        转账状态-处理建议:
            - ACCEPTED:
                # 注意：此时需要通过商户单号轮询查询转账状态
                # 1. 将订单信息保存到数据库
                # 2. 使用异步任务定期查询转账状态（设置合理的查询间隔） / 接受回调通知扭转状态
                # 3. 订单状态扭转至 WAIT_USER_CONFIRM/待收款用户确认 时，可进行后续的转账操作
            - PROCESSING | TRANSFERING:
                # 1. 如一直处于此状态，建议检查账户余额是否足够，如果足够，则尝试原单重试
            - WAIT_USER_CONFIRM:
                # 1. 更新订单状态为等待确认
                # 2. 设置确认超时时间
                # 3. 添加定时任务查询 或 接受回调通知 确认状态
                # 4. 超时后发送提醒通知
            - SUCCESS:
                # 1. 更新订单状态为成功
                # 2. 记录转账完成时间
                # 3. 触发后续业务流程
            - FAIL:
                # 1. 更新订单状态为失败
                # 2. 记录具体失败原因和处理建议
                # 3. 根据不同失败原因执行对应的处理流程
            - CANCELING:
                # 1. 更新订单状态为撤销中
                # 1. 使用异步任务定期查询转账状态（设置合理的查询间隔） / 接受回调通知扭转状态
            - CANCELLED:
                # 1. 更新订单状态为已取消
                # 2. 记录取消时间和原因
        """
