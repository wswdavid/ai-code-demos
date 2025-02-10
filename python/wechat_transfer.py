import json
import time
import uuid

import requests
from loguru import logger

from wechat_pay import WeChatPayBase


class WeChatTransfer(WeChatPayBase):
    """微信商家转账实现类"""

    def __init__(self):
        super().__init__()
        self.transfer_url = (
            "https://api.mch.weixin.qq.com/v3/fund-app/mch-transfer/transfer-bills"
        )
        # 状态映射表
        self.state_map = {
            "ACCEPTED": "转账已受理",
            "PROCESSING": "转账处理中",
            "WAIT_USER_CONFIRM": "待收款用户确认",
            "TRANSFERING": "转账处理中",
            "SUCCESS": "转账成功",
            "FAIL": "转账失败",
            "CANCELING": "转账撤销中",
            "CANCELLED": "转账已撤销",
        }
        # 需要用户确认的状态
        self.need_confirm_states = {
            "WAIT_USER_CONFIRM",
        }
        # 可以重试的状态
        self.retriable_states = {
            "PROCESSING",
            "TRANSFERING",
        }
        # 终态状态
        self.final_states = {
            "SUCCESS",
            "FAIL",
            "CANCELLED",
        }

    def handle_transfer_state(self, state, result, out_bill_no):
        """
        处理转账状态

        Args:
            state (str): 转账状态
            result (dict): API返回的原始结果
            out_bill_no (str): 商户单号

        Returns:
            dict: 处理后的结果
        """
        try:
            # 获取状态描述, 默认为 未知状态
            state_msg = self.state_map.get(state, "未知状态")
            
            # 基础返回数据
            base_response = {
                "code": 0,  # 默认成功
                "data": result,
                "out_bill_no": out_bill_no,
                "state": state,
                "state_msg": state_msg,
                "need_confirm": False
            }

            if not state:  # 如果状态为空
                logger.warning(f"转账状态为空，商户单号: {out_bill_no}")
                return {
                    **base_response,
                    "code": -1,
                    "msg": "转账状态未知",
                }

            match state:
                case "ACCEPTED":
                    logger.info(f"转账申请成功，商户单号: {out_bill_no}")
                    return {
                        **base_response,
                        "msg": "转账申请已受理",
                    }

                case state if state in self.need_confirm_states:
                    logger.info(f"转账需要用户确认，商户单号: {out_bill_no}, 状态: {state}")
                    return {
                        **base_response,
                        "msg": "请在微信中确认收款",
                        "need_confirm": True,
                    }

                case state if state in self.retriable_states:
                    logger.info(f"转账处理中，商户单号: {out_bill_no}, 状态: {state}")
                    return {
                        **base_response,
                        "code": -1,  # 可重试
                        "msg": state_msg,
                    }

                case state if state in self.final_states:
                    is_success = state == "SUCCESS"
                    logger.info(f"转账完成，商户单号: {out_bill_no}, 状态: {state}")
                    return {
                        **base_response,
                        "code": 0 if is_success else -2,
                        "msg": state_msg,
                    }

                case _:  # 默认情况
                    logger.warning(f"未知转账状态，商户单号: {out_bill_no}, 状态: {state}")
                    return {
                        **base_response,
                        "code": -1,
                        "msg": f"未知状态: {state}",
                    }
        except Exception as e:
            logger.exception(f"处理转账状态异常: {str(e)}")
            return {
                "code": -1,
                "msg": f"处理状态异常: {str(e)}",
                "out_bill_no": out_bill_no,
                "state": "未知状态",
                "data": result,
            }

    def create_transfer_order(self, openid, amount, batch_name, detail_remark=""):
        """
        创建商家转账订单

        Args:
            openid (str): 接收转账用户的openid
            amount (int): 转账金额，单位为分
            batch_name (str): 转账批次名称
            detail_remark (str): 转账备注

        Returns:
            dict: 转账结果
            {
                'code': 0/-1/-2,  # 0成功，-1失败可重试，-2失败不可重试
                'data': {...},     # API返回的原始数据
                'msg': '...',      # 错误信息
                'out_bill_no': '...',  # 商户单号
                'state': '...',    # 转账状态
                'need_confirm': bool  # 是否需要用户确认
            }
        """
        try:
            # 生成商户单号
            out_bill_no = f"BILL{int(time.time())}{uuid.uuid4().hex[:8]}"

            # 在发送请求前，先查询该商户单号是否已存在
            # query_result = self.query_transfer_order(out_bill_no)
            # if query_result and query_result.get('data'):
            #     logger.info(f"商户单号 {out_bill_no} 已存在，返回查询结果")
            #     return query_result

            # 构造请求数据
            transfer_data = {
                "appid": self.app_id,
                "out_bill_no": out_bill_no,
                "transfer_scene_id": "1000",  # 例如：1000-现金营销
                "openid": openid,
                "transfer_amount": amount,
                "transfer_remark": detail_remark or batch_name,
                "transfer_scene_report_infos": [
                    {"info_type": "活动名称", "info_content": batch_name,},
                    {
                        "info_type": "奖励说明",
                        "info_content": detail_remark or "商家转账",
                    },
                ],
            }

            # 生成请求签名
            sign_data = self.generate_sign(
                "POST",
                "/v3/fund-app/mch-transfer/transfer-bills",
                json.dumps(transfer_data),
            )

            # 构造请求头
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": (
                    f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mch_id}",'
                    f'nonce_str="{sign_data["nonce"]}",'
                    f'timestamp="{sign_data["timestamp"]}",'
                    f'serial_no="{self.serial_no}",'
                    f'signature="{sign_data["signature"]}"'
                ),
            }

            # 发送请求
            response = requests.post(
                self.transfer_url, headers=headers, json=transfer_data
            )

            # 记录响应结果
            logger.info(f"转账请求响应状态码: {response.status_code}")
            result = response.json() if response.content else {}
            logger.info(f"转账请求响应内容: {result}")

            if response.status_code == 200:
                # 检查转账状态
                state = result.get("state", "")
                return self.handle_transfer_state(
                    state,
                    result,
                    out_bill_no,
                )
            else:
                error_code = result.get("code")
                error_msg = result.get("message", "未知错误")

                # 根据错误码判断是否可以重试
                retriable_codes = {
                    "SYSTEM_ERROR",      # 系统错误
                    "NETWORK_ERROR",     # 网络错误
                    "FREQUENCY_LIMITED", # 频率限制
                    "RESOURCE_INSUFFICIENT", # 资源不足
                    "BANK_ERROR",        # 银行系统异常
                }

                # 添加重试次数限制
                MAX_RETRY_TIMES = 3
                retry_count = 0

                if error_code in retriable_codes and retry_count < MAX_RETRY_TIMES:
                    logger.warning(f"转账请求失败(可重试 {retry_count + 1}/{MAX_RETRY_TIMES})，错误码: {error_code}, 信息: {error_msg}",)
                    return {
                        "code": -1,  # 可重试
                        "data": result,
                        "out_bill_no": out_bill_no,
                        "msg": f"转账失败(可重试): {error_msg}",
                    }
                else:
                    logger.error(
                        f"转账请求失败(不可重试)，错误码: {error_code}, 信息: {error_msg}"
                    )
                    return {
                        "code": -2,  # 不可重试
                        "data": result,
                        "out_bill_no": out_bill_no,
                        "msg": f"转账失败(不可重试): {error_msg}",
                    }
        except Exception as e:
            logger.exception(f"转账处理异常: {str(e)}")
            return {
                "code": -1,  # 异常情况下建议可重试
                "msg": f"转账异常: {str(e)}",
                "out_bill_no": out_bill_no if "out_bill_no" in locals() else None,
            }

    def query_transfer_order(self, out_bill_no):
        """
        查询转账订单状态
        
        Args:
            out_bill_no (str): 商户单号
            
        Returns:
            dict: 查询结果，格式与 create_transfer_order 返回结果相同
        """
        try:
            query_url = f"https://api.mch.weixin.qq.com/v3/fund-app/mch-transfer/transfer-bills/out-bill-no/{out_bill_no}"
            
            # 生成请求签名
            sign_data = self.generate_sign(
                "GET",
                f"/v3/fund-app/mch-transfer/transfer-bills/out-bill-no/{out_bill_no}",
                ""
            )
            
            # 构造请求头
            headers = {
                "Accept": "application/json",
                "Authorization": (
                    f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mch_id}",'
                    f'nonce_str="{sign_data["nonce"]}",'
                    f'timestamp="{sign_data["timestamp"]}",'
                    f'serial_no="{self.serial_no}",'
                    f'signature="{sign_data["signature"]}"'
                ),
            }
            
            # 发送请求
            response = requests.get(query_url, headers=headers)
            
            # 记录响应结果
            logger.info(f"查询转账订单响应状态码: {response.status_code}")
            result = response.json() if response.content else {}
            logger.info(f"查询转账订单响应内容: {result}")
            
            if response.status_code == 200:
                # 检查转账状态
                state = result.get("state", "")
                return self.handle_transfer_state(state, result, out_bill_no)
            elif response.status_code == 404:
                logger.info(f"转账订单不存在，商户单号: {out_bill_no}")
                return {
                    "code": -2,
                    "msg": "转账订单不存在",
                    "out_bill_no": out_bill_no,
                    "state": "NOT_FOUND",
                    "state_msg": "订单不存在",
                    "data": result
                }
            else:
                error_msg = result.get("message", "未知错误")
                logger.error(f"查询转账订单失败，错误信息: {error_msg}")
                return {
                    "code": -1,
                    "msg": f"查询失败: {error_msg}",
                    "out_bill_no": out_bill_no,
                    "state": "QUERY_ERROR",
                    "state_msg": "查询异常",
                    "data": result
                }
                
        except Exception as e:
            logger.exception(f"查询转账订单异常: {str(e)}")
            return {
                "code": -1,
                "msg": f"查询异常: {str(e)}",
                "out_bill_no": out_bill_no,
                "state": "SYSTEM_ERROR",
                "state_msg": "系统异常",
                "data": {}
            }
