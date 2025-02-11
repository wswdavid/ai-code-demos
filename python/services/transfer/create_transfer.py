"""创建商家转账API"""

import time
import uuid

from loguru import logger

from services.wechat_pay_base import WeChatPayBase

from .constants import (
    ACCEPTED_STATES,
    API_CONFIGS,
    FINAL_STATES,
    MAX_TRANSFER_AMOUNT,
    MIN_TRANSFER_AMOUNT,
    NEED_CONFIRM_STATES,
    RETRIABLE_BIZ_CODES,
    RETRIABLE_STATES,
    TRANSFER_SCENES,
)


class CreateTransfer(WeChatPayBase):
    """创建商家转账实现类"""

    def __init__(self):
        super().__init__()
        self.api_config = API_CONFIGS["create_transfer"]

    def validate_transfer_params(self, transfer_data: dict) -> tuple[bool, str]:
        """
        验证转账参数

        Args:
            transfer_data (dict): 完整的转账请求参数
            {
                "appid": "wx8888888888888888",
                "out_bill_no": "BILL123456789",
                "transfer_scene_id": "1000",
                "openid": "o4GgauInH_RCEdvrrNGrntXDuXXX",
                "transfer_amount": 100,
                "transfer_remark": "测试转账",
                "transfer_scene_report_infos": [
                    {"info_type": "活动名称", "info_content": "新年活动"},
                    {"info_type": "奖励说明", "info_content": "抽奖活动奖励"}
                ],
                "user_name": "加密的用户姓名",  # 可选
                "user_recv_perception": "现金奖励"  # 可选
            }

        Returns:
            tuple: (is_valid, error_msg)
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

    def handle_http_status(self, status_code: int, result: dict) -> tuple[str, str | None]:
        """处理HTTP状态码

        Args:
            status_code (int): HTTP响应状态码
            result (dict): API响应结果，包含以下字段:
                - code: 业务错误码
                - message: 错误信息
                - out_bill_no: 商户订单号

        Returns:
            tuple[str, str | None]: 返回一个元组，包含:
                - 第一个元素为处理动作类型，可能的值:
                    - "continue": 继续处理
                    - "retry": 需要重试
                    - "error": 发生错误
                - 第二个元素为错误信息，如果没有错误则为None

        Suggestion:
            1. 2XX (成功):
                - 继续处理业务逻辑
            2. 429 (请求频率超限):
                - 请求实现限流控制
                - 延迟重试，建议等待2-5秒
                - 重要：重试时必须使用原商户订单号，不要更换订单号
            3. 5XX (服务端错误):
                - 记录错误日志
                - 可尝试使用指数退避算法重试
                - 持续失败时发送告警
                - 重要：重试时必须使用原商户订单号，避免重复转账风险
                - 建议：先查询订单状态，确认订单不存在才重试
            4. 其他错误:
                - 记录详细错误信息
                - 检查请求参数是否正确
                - 验证签名是否正确
                - 确认证书是否有效
                - 重要：4XX错误通常表示请求有误，修复问题后可使用原商户订单号重试
        """
        # 获取业务错误码
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
        """处理转账状态"""
        state = data.get("state", "")
        out_bill_no = data.get("out_bill_no", "")

        # 状态流转参考 https://pay.weixin.qq.com/doc/v3/merchant/4012715191#%E5%95%86%E5%AE%B6%E8%BD%AC%E8%B4%A6%E8%AE%A2%E5%8D%95%E7%8A%B6%E6%80%81
        match state:
            case state if state in ACCEPTED_STATES:
                # 当状态为ACCEPTED时，记录日志并继续处理
                logger.info(f"转账申请已受理，商户单号: {out_bill_no}")
                # 注意：此时需要通过商户单号轮询查询转账状态
                # 需要实现以下逻辑：
                # 1. 将订单信息保存到数据库
                # 2. 使用异步任务定期查询转账状态（设置合理的查询间隔） / 接受回调通知扭转状态
                # 3. 订单状态扭转至 WAIT_USER_CONFIRM/待收款用户确认 时，可进行后续的转账操作。

            case state if state in NEED_CONFIRM_STATES:
                # 需要用户确认的状态
                logger.info(f"等待用户确认收款，商户单号: {out_bill_no}")
                # 需要实现以下逻辑：
                # 1. 更新订单状态为等待确认
                # 2. 设置确认超时时间
                # 3. 添加定时任务查询 或 接受回调通知 确认状态
                # 4. 超时后发送提醒通知

            case state if state in RETRIABLE_STATES:
                # 可重试的状态
                logger.warning(f"转账遇到可重试状态: {state}，商户单号: {out_bill_no}")
                # 需要实现以下逻辑：
                # 1. 如一直处于此状态，建议检查账户余额是否足够，如果足够，则尝试原单重试

            case state if state in FINAL_STATES:
                if state == "SUCCESS":
                    logger.info(f"转账成功，商户单号: {out_bill_no}")
                    # 需要实现以下逻辑：
                    # 1. 更新订单状态为成功
                    # 2. 记录转账完成时间
                    # 3. 触发后续业务流程
                elif state == "CANCELLED":
                    logger.warning(f"转账已取消，商户单号: {out_bill_no}")
                    # 需要实现以下逻辑：
                    # 1. 更新订单状态为已取消
                    # 2. 记录取消时间和原因
                else:
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

    def create_transfer_order(
        self,
        openid: str,
        amount: int,
        transfer_scene_report_infos: list,
        scene: str,
        transfer_remark: str,
        user_recv_perception: str = None,
        user_name: str = None,
        notify_url: str = None,
    ):
        """
        创建商家转账订单

        重要说明：
            1. 同一笔转账订单的商户订单号（out_bill_no）重入时，请求参数需要保持一致
            2. 当HTTP状态码为5XX或者429时，可以尝试重试，但必须使用原商户订单号
            3. 敏感信息加密时需要使用【微信支付公钥】或【微信支付平台证书公钥】
            4. 建议在调用接口前检查商户账户余额是否充足

        错误处理：
            - 参数校验：通过 validate_transfer_params 处理
            - HTTP请求: 通过 handle_http_status 处理
            - 业务结果：通过 handle_transfer_result 处理

        Args:
            openid (str): 用户的openid，商户某Appid下，获取用户openid参考 https://pay.weixin.qq.com/doc/v3/merchant/4012068676#OpenID
            amount (int): 转账金额，单位为分
            scene (str): 转账场景，在“商户平台-产品中心-商家转账”中申请的转账场景，申请权限通过后才可使用。转账场景需配置字段，参考 TRANSFER_SCENES 中的描述
            transfer_scene_report_infos (list): 转账报备信息列表。每个场景要求的报备信息不同，参考 TRANSFER_SCENES 中的描述，按照要求传入报备信息
                「现金营销」-转账场景示例（需填入活动名称、奖励说明）：
                [
                    {"info_type": "活动名称", "info_content": "新会员有礼"},
                    {"info_type": "奖励说明", "info_content": "注册会员抽奖一等奖"}
                ]
            transfer_remark (str): 转账备注，用户收款时可见，UTF8编码，最多32个字符。参考 https://pay.weixin.qq.com/doc/v3/merchant/4012711988
            user_recv_perception (str, optional): 用户在客户端收款时感知到的收款原因，参考 TRANSFER_SCENES 中的描述
            user_name (str, optional): 收款用户姓名。当转账金额>=2000元时必填，需要使用【微信支付公钥】或【微信支付平台证书公钥】加密
            notify_url (str, optional): 回调通知地址，通知URL必须为公网可访问的URL，必须为HTTPS，且不能携带参数。

        Returns:
            dict: 转账结果
        """
        out_bill_no = f"BILL{int(time.time())}{uuid.uuid4().hex[:8]}"
        scene_config = TRANSFER_SCENES.get(scene)
        scene_id = scene_config["scene_id"]

        # 构造请求参数
        transfer_data = {
            "appid": self.app_id,
            "out_bill_no": out_bill_no,
            "transfer_scene_id": scene_id,
            "openid": openid,
            "transfer_amount": amount,
            "transfer_remark": transfer_remark,
            "transfer_scene_report_infos": transfer_scene_report_infos,
        }

        # 添加可选参数
        additional_headers = {}
        if user_recv_perception:
            transfer_data["user_recv_perception"] = user_recv_perception
        if user_name:
            # 加密敏感信息
            serial_no = self.serial_no
            # TDOO 需要支持自动获取最新的平台证书来加密, 加密时支持传入证书序列号
            encrypted_user_name = self.encrypt_sensitive_data(user_name)
            additional_headers["Wechatpay-Serial"] = serial_no
            transfer_data["user_name"] = encrypted_user_name
        if notify_url:
            transfer_data["notify_url"] = notify_url

        # 参数校验
        is_valid, error_msg = self.validate_transfer_params(transfer_data)
        if not is_valid:
            raise ValueError(error_msg)

        # 发送请求
        status_code, result = self._make_request(
            self.api_config["method"],
            self.api_config["path"],
            transfer_data,
            additional_headers=additional_headers,
        )

        # 处理HTTP状态
        action_type, error_msg = self.handle_http_status(status_code, result)
        if action_type != "continue":
            return {
                "msg": error_msg,
                "out_bill_no": out_bill_no,
                "data": result,
                "action_type": action_type,
            }

        # 处理业务结果, 需自行实现逻辑
        transfer_result = self.handle_transfer_result(result)
        return transfer_result
