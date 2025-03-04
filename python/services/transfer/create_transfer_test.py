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
)

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
        # 1. 金额校验
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
        return True, ""

    def handle_http_status(self, status_code: int, result: dict) -> tuple[str, str | None]:
        """处理HTTP状态码"""
        # 获取业务错误码
        error_code = result.get("code", "")
        out_bill_no = result.get("out_bill_no", "")
        match status_code:
            case code if 200 <= code < 300:
                return "continue", None
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
                logger.info(f"转账申请已受理，商户单号: {out_bill_no}")

            case state if state in NEED_CONFIRM_STATES:
                logger.info(f"等待用户确认收款，商户单号: {out_bill_no}")
            case state if state in FINAL_STATES:
                if state == "SUCCESS":
                    logger.info(f"转账成功，商户单号: {out_bill_no}")
                elif state == "CANCELLED":
                    logger.warning(f"转账已取消，商户单号: {out_bill_no}")
                else:
                    # 获取失败原因
                    fail_reason = data.get("fail_reason")
                    logger.error(f"转账失败，商户单号: {out_bill_no}，失败原因: {fail_reason}")
            case _:
                # 未知状态处理
                logger.error(f"未知转账状态: {state}，商户单号: {out_bill_no}")
                raise

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
        创建转账订单
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
            "transfer_scene_report_infos": transfer_scene_report_infos,
        }

        # 添加可选参数
        additional_headers = {}
        if user_recv_perception:
            transfer_data["user_recv_perception"] = user_recv_perception
        if user_name:
            # 加密敏感信息
            serial_no = self.serial_no
            encrypted_user_name = self.encrypt_sensitive_data(user_name)
            transfer_data["user_name"] = encrypted_user_name
        if notify_url:
            transfer_data["notify_url"] = notify_url

        # * 参数校验
        is_valid, error_msg = self.validate_transfer_params(transfer_data)
        if not is_valid:
            raise ValueError(error_msg)
        # * 发送请求, API配置信息参考 API_CONFIGS 中的内容
        status_code, result = self._make_request(
            self.api_config["method"],
            self.api_config["path"],
            transfer_data,
            additional_headers=additional_headers,
        )
        # * 处理HTTP状态
        action_type, error_msg = self.handle_http_status(status_code, result)
        if action_type != "continue":
            raise
        # * 处理业务结果
        transfer_result = self.handle_transfer_result(result)
        return transfer_result
