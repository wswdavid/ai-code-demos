"""创建商家转账API - 伪代码实现"""

# 转账场景配置，用于转账时的参数获取和校验
from loguru import logger

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
        transfer_data = {
            "appid": "wxf636efh567hg4356",
            "out_bill_no": "plfk2020042013",
            "transfer_scene_id": "1000",
            "openid": "o-MYE42l80oelYMDE34nYD456Xoy",
            "user_name": "757b340b45ebef5467rter35gf464344v3542sdf4t6re4tb4f54ty45t4yyry45",
            "transfer_amount": 400000,
            "transfer_remark": "2020年4月报销",
            "notify_url": "https://www.weixin.qq.com/wxpay/pay.php",
            "user_recv_perception": "现金奖励",
            "transfer_scene_report_infos": [
                {"info_type": "活动名称", "info_content": "新会员有礼"},
                {"info_type": "奖励说明", "info_content": "注册会员抽奖一等奖"},
            ],
        }
        return transfer_data

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
        # 1. 基础字段校验
        required_fields = {
            "appid",
            "out_bill_no",
            "transfer_scene_id",
            "openid",
            "transfer_amount",
            "transfer_remark",
            "transfer_scene_report_infos",
        }

        missing_fields = required_fields - set(transfer_data.keys())
        if missing_fields:
            return False, f"缺少必填字段: {', '.join(missing_fields)}"

        # 2. 金额校验
        # 转账金额限制(单位:分)
        MIN_TRANSFER_AMOUNT = 30  # 最小转账金额0.3元
        MAX_TRANSFER_AMOUNT = 2000000  # 最大转账金额2万元
        amount = transfer_data["transfer_amount"]
        if not isinstance(amount, int):
            return False, "转账金额必须为整数"
        if amount < MIN_TRANSFER_AMOUNT:
            return False, f"转账金额不能小于{MIN_TRANSFER_AMOUNT / 100}元"
        if amount > MAX_TRANSFER_AMOUNT:
            return False, f"转账金额不能大于{MAX_TRANSFER_AMOUNT / 100}元"

        # 3. 大额转账校验用户姓名
        if amount >= 200000:  # 2000元 = 200000分
            if "user_name" not in transfer_data or not transfer_data["user_name"]:
                return False, "转账金额大于等于2000元时，必须提供加密后的用户姓名"

        # 4. 转账备注校验
        remark = transfer_data["transfer_remark"]
        if not isinstance(remark, str):
            return False, "转账备注必须为字符串"
        if len(remark.encode("utf-8")) > 32:
            return False, "转账备注不能超过32个字符"

        # 5. 场景校验
        scene_id = transfer_data["transfer_scene_id"]
        scene = None
        for scene_key, scene_config in TRANSFER_SCENES.items():
            if scene_config["scene_id"] == scene_id:
                scene = scene_config
                break
        if not scene:
            return False, f"无效的转账场景ID: {scene_id}"

        # 6. 用户收款感知校验
        if "user_recv_perception" in transfer_data:
            if transfer_data["user_recv_perception"] not in scene["user_perceptions"]:
                return False, f"当前场景({scene_key})下收款感知可选值为: {', '.join(scene['user_perceptions'])}"

        # 7. 报备信息校验
        report_infos = transfer_data["transfer_scene_report_infos"]
        if not isinstance(report_infos, list):
            return False, "报备信息必须为列表格式"
        required_configs = scene["report_configs"]
        if len(report_infos) != len(required_configs):
            return (
                False,
                f"报备信息数量不匹配，需要{len(required_configs)}个，实际提供{len(report_infos)}个",
            )
        for config, info in zip(required_configs, report_infos):
            if not isinstance(info, dict):
                return False, "报备信息格式错误"
            if "info_type" not in info or "info_content" not in info:
                return False, "报备信息缺少必填字段"
            if info["info_type"] != config["info_type"]:
                return False, f"报备信息类型不匹配: {info['info_type']}"
            if config["required"] and not info["info_content"]:
                return False, f"缺少必填的报备信息: {config['info_type']}"

        return True, ""

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
        # 可重试的业务错误码
        RETRIABLE_BIZ_CODES = {
            "SYSTEM_ERROR",  # 系统错误
            "NETWORK_ERROR",  # 网络错误
            "FREQUENCY_LIMITED",  # 频率限制
            "RESOURCE_INSUFFICIENT",  # 资源不足
            "BANK_ERROR",  # 银行系统异常
        }

        # 获取业务错误码
        result: dict
        status_code: int
        error_code = result.get("code", "")
        out_bill_no = result.get("out_bill_no", "")

        match status_code:
            case code if 200 <= code < 300:
                return "continue", None

            case 429:
                logger.warning(f"请求频率超限，使用原商户订单号重试，商户单号: {out_bill_no}")
                return (
                    "retry",
                    f"请求频率超限: {result.get('message', '')}，请稍后使用原单号重试",
                )

            case code if code in {500, 502, 503, 504}:
                if error_code in RETRIABLE_BIZ_CODES:
                    logger.warning(f"服务端错误(可重试)，错误码: {error_code}，商户单号: {out_bill_no}")
                    return (
                        "retry",
                        f"服务端错误({error_code})，请先查询订单状态，使用原单号重试",
                    )
                else:
                    logger.error(f"服务端错误(不可重试)，错误码: {error_code}，商户单号: {out_bill_no}")
                    return (
                        "error",
                        f"服务端错误({error_code})，请检查错误信息并联系技术支持",
                    )
            case _:
                if error_code in RETRIABLE_BIZ_CODES:
                    logger.warning(f"业务错误(可重试)，错误码: {error_code}，商户单号: {out_bill_no}")
                    return (
                        "retry",
                        f"业务错误({error_code})，请先查询订单状态，使用原单号重试",
                    )
                else:
                    logger.error(f"业务错误(不可重试)，错误码: {error_code}，商户单号: {out_bill_no}")
                    return "error", f"业务错误({error_code})，请修复问题后再重试"

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
        state = data.get("state", "")
        out_bill_no = data.get("out_bill_no", "")

        # 状态流转参考 https://pay.weixin.qq.com/doc/v3/merchant/4012715191#%E5%95%86%E5%AE%B6%E8%BD%AC%E8%B4%A6%E8%AE%A2%E5%8D%95%E7%8A%B6%E6%80%81
        match state:
            case "ACCEPTED":
                # 当状态为ACCEPTED时，记录日志并继续处理
                logger.info(f"转账申请已受理，商户单号: {out_bill_no}")
                # 注意：此时需要通过商户单号轮询查询转账状态
                # 需要实现以下逻辑：
                # 1. 将订单信息保存到数据库
                # 2. 使用异步任务定期查询转账状态（设置合理的查询间隔） / 接受回调通知扭转状态
                # 3. 订单状态扭转至 WAIT_USER_CONFIRM/待收款用户确认 时，可进行后续的转账操作

            case "WAIT_USER_CONFIRM":
                # 需要用户确认的状态
                logger.info(f"等待用户确认收款，商户单号: {out_bill_no}")
                # 需要实现以下逻辑：
                # 1. 更新订单状态为等待确认
                # 2. 设置确认超时时间
                # 3. 添加定时任务查询 或 接受回调通知 确认状态
                # 4. 超时后发送提醒通知

            case state if state in {"PROCESSING", "TRANSFERING"}:
                # 可重试的状态
                logger.warning(f"转账遇到可重试状态: {state}，商户单号: {out_bill_no}")
                # 需要实现以下逻辑：
                # 1. 如一直处于此状态，建议检查账户余额是否足够，如果足够，则尝试原单重试

            case "SUCCESS":
                logger.info(f"转账成功，商户单号: {out_bill_no}")
                # 需要实现以下逻辑：
                # 1. 更新订单状态为成功
                # 2. 记录转账完成时间
                # 3. 触发后续业务流程
            case "CANCELING":
                logger.warning(f"转账已取消，商户单号: {out_bill_no}")
                # 需要实现以下逻辑：
                # 1. 更新订单状态为已取消
                # 2. 记录取消时间和原因

            case "FAIL":
                # 获取失败原因
                fail_reason = data.get("fail_reason")
                logger.error(f"转账失败，商户单号: {out_bill_no}，失败原因: {fail_reason}")
                # 需要实现以下逻辑：
                # 1. 更新订单状态为失败
                # 2. 记录具体失败原因和处理建议
                # 3. 根据不同失败原因执行对应的处理流程

            case _:
                # 未知状态处理
                logger.error(f"未知转账状态: {state}，商户单号: {out_bill_no}")
                # 需要实现以下逻辑：
                # 1. 记录异常状态
                # 2. 根据异常状态执行对应的处理流程
