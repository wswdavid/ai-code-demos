import requests
from wechat_pay import WeChatPayBase
from loguru import logger
import json
import time
import uuid

class WeChatTransfer(WeChatPayBase):
    """微信商家转账实现类"""
    
    def __init__(self):
        super().__init__()
        self.transfer_url = "https://api.mch.weixin.qq.com/v3/fund-app/mch-transfer/transfer-bills"
        # 状态映射表
        self.state_map = {
            'ACCEPTED': '转账已受理',
            'PROCESSING': '转账处理中',
            'WAIT_USER_CONFIRM': '待收款用户确认',
            'TRANSFERING': '转账处理中',
            'SUCCESS': '转账成功',
            'FAIL': '转账失败',
            'CANCELING': '转账撤销中',
            'CANCELLED': '转账已撤销'
        }
        # 需要用户确认的状态
        self.need_confirm_states = {'WAIT_USER_CONFIRM', 'TRANSFERING'}
        # 可以重试的状态
        self.retriable_states = {'PROCESSING', 'TRANSFERING'}
        # 终态状态
        self.final_states = {'SUCCESS', 'FAIL', 'CANCELLED'}
    
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
        # 获取状态描述
        state_msg = self.state_map.get(state, '未知状态')
        
        # 基础返回数据
        base_response = {
            "data": result,
            "out_bill_no": out_bill_no,
            "state": state,
            "state_msg": state_msg
        }
        
        match state:
            case 'ACCEPTED':
                logger.info(f"转账申请成功，商户单号: {out_bill_no}")
                return {
                    **base_response,
                    "code": 0,
                    "msg": "转账申请已受理",
                    "need_confirm": False
                }
            
            case state if state in self.need_confirm_states:
                logger.info(f"转账需要用户确认，商户单号: {out_bill_no}, 状态: {state}")
                return {
                    **base_response,
                    "code": 0,
                    "msg": "请在微信中确认收款",
                    "need_confirm": True
                }
            
            case state if state in self.retriable_states:
                logger.info(f"转账处理中，商户单号: {out_bill_no}, 状态: {state}")
                return {
                    **base_response,
                    "code": -1,  # 可重试
                    "msg": state_msg,
                    "need_confirm": False
                }
            
            case state if state in self.final_states:
                is_success = state == 'SUCCESS'
                logger.info(f"转账完成，商户单号: {out_bill_no}, 状态: {state}")
                return {
                    **base_response,
                    "code": 0 if is_success else -2,
                    "msg": state_msg,
                    "need_confirm": False
                }
            
            case _:  # 默认情况
                logger.warning(f"未知转账状态，商户单号: {out_bill_no}, 状态: {state}")
                return {
                    **base_response,
                    "code": -1,
                    "msg": f"未知状态: {state}",
                    "need_confirm": False
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
            
            # 构造请求数据
            transfer_data = {
                "appid": self.app_id,
                "out_bill_no": out_bill_no,
                "transfer_scene_id": "1000",  # 例如：1000-现金营销
                "openid": openid,
                "transfer_amount": amount,
                "transfer_remark": detail_remark or batch_name,
                "transfer_scene_report_infos": [
                    {
                        "info_type": "活动名称",
                        "info_content": batch_name
                    },
                    {
                        "info_type": "奖励说明",
                        "info_content": detail_remark or "商家转账"
                    }
                ]
            }
            
            # 生成请求签名
            sign_data = self.generate_sign(
                "POST",
                "/v3/fund-app/mch-transfer/transfer-bills",
                json.dumps(transfer_data)
            )
            
            # 构造请求头
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': (
                    f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mch_id}",'
                    f'nonce_str="{sign_data["nonce"]}",'
                    f'timestamp="{sign_data["timestamp"]}",'
                    f'serial_no="{self.serial_no}",'
                    f'signature="{sign_data["signature"]}"'
                )
            }
            
            # 发送请求
            response = requests.post(
                self.transfer_url,
                headers=headers,
                json=transfer_data
            )
            
            # 记录响应结果
            logger.info(f"转账请求响应状态码: {response.status_code}")
            result = response.json() if response.content else {}
            logger.info(f"转账请求响应内容: {result}")
            
            if response.status_code == 200:
                # 检查转账状态
                state = result.get('state', '')
                return self.handle_transfer_state(state, result, out_bill_no,)
            else:
                error_code = result.get('code')
                error_msg = result.get('message', '未知错误')
                
                # 根据错误码判断是否可以重试
                retriable_codes = [
                    'SYSTEM_ERROR',           # 系统错误
                    'NETWORK_ERROR',          # 网络错误
                    'FREQUENCY_LIMITED',      # 频率限制
                    'RESOURCE_INSUFFICIENT',  # 资源不足
                ]
                
                if error_code in retriable_codes:
                    logger.warning(f"转账请求失败(可重试)，错误码: {error_code}, 信息: {error_msg}")
                    return {
                        "code": -1,  # 可重试
                        "data": result,
                        "out_bill_no": out_bill_no,
                        "msg": f"转账失败(可重试): {error_msg}"
                    }
                else:
                    logger.error(f"转账请求失败(不可重试)，错误码: {error_code}, 信息: {error_msg}")
                    return {
                        "code": -2,  # 不可重试
                        "data": result,
                        "out_bill_no": out_bill_no,
                        "msg": f"转账失败(不可重试): {error_msg}"
                    }
                
        except Exception as e:
            logger.exception(f"转账处理异常: {str(e)}")
            return {
                "code": -1,  # 异常情况下建议可重试
                "msg": f"转账异常: {str(e)}",
                "out_bill_no": out_bill_no if 'out_bill_no' in locals() else None
            }
    