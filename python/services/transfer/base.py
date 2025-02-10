"""微信转账基础类"""
import time
from loguru import logger
from services.wechat_pay_base import WeChatPayBase
from .constants import (
    HTTP_STATUS_MAP, STATE_MAP, NEED_CONFIRM_STATES,
    RETRIABLE_STATES, FINAL_STATES, TRANSFER_SCENES
)

class TransferBase(WeChatPayBase):
    """微信商家转账基础类"""
    def __init__(self):
        super().__init__()

    def handle_transfer_state(self, state, result, out_bill_no):
        """处理转账状态"""
        try:
            state_msg = STATE_MAP.get(state, "未知状态")
            
            base_response = {
                "code": 0,
                "data": result,
                "out_bill_no": out_bill_no,
                "state": state,
                "state_msg": state_msg,
                "need_confirm": False
            }

            if not state:
                logger.warning(f"转账状态为空，商户单号: {out_bill_no}")
                return {**base_response, "code": -1, "msg": "转账状态未知"}

            match state:
                case "ACCEPTED":
                    return {**base_response, "msg": "转账申请已受理"}
                    
                case state if state in NEED_CONFIRM_STATES:
                    return {**base_response, "msg": "请在微信中确认收款", "need_confirm": True}
                    
                case state if state in RETRIABLE_STATES:
                    return {**base_response, "code": -1, "msg": state_msg}
                    
                case state if state in FINAL_STATES:
                    is_success = state == "SUCCESS"
                    return {**base_response, "code": 0 if is_success else -2, "msg": state_msg}
                    
                case _:
                    return {**base_response, "code": -1, "msg": f"未知状态: {state}"}
                    
        except Exception as e:
            logger.exception(f"处理转账状态异常: {str(e)}")
            return {
                "code": -1,
                "msg": f"处理状态异常: {str(e)}",
                "out_bill_no": out_bill_no,
                "state": "未知状态",
                "data": result,
            }

    def handle_http_status(self, status_code, result):
        """处理HTTP状态码"""
        status_msg = HTTP_STATUS_MAP.get(status_code, "未知HTTP状态")
        
        match status_code:
            case code if 200 <= code < 300:
                return False, None
            case 429:
                return True, f"请求频率超限: {result.get('message', status_msg)}"
            case code if code in {500, 502, 503, 504}:
                return True, f"服务端错误({code}): {result.get('message', status_msg)}"
            case _:
                return False, f"请求失败({status_code}): {result.get('message', status_msg)}" 