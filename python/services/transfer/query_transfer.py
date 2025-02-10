"""查询商家转账API"""
from loguru import logger
from .base import TransferBase
from .constants import API_CONFIGS

class QueryTransfer(TransferBase):
    """查询商家转账实现类"""
    
    def __init__(self):
        super().__init__()
        self.api_config = API_CONFIGS["query_transfer"]
    
    def query_transfer_order(self, out_bill_no):
        """
        查询转账订单状态
        
        Note:
            此接口不支持重试,因为:
            1. 查询接口本身就是用来确认状态的
            2. 查询失败不会影响业务状态
            3. 调用方可以自行决定是否重试查询
        """
        try:
            api_path = self.api_config["path"].format(out_bill_no=out_bill_no)
            status_code, result = self._make_request(
                self.api_config["method"], 
                api_path
            )
            
            if status_code == 200:
                state = result.get("state", "")
                return self.handle_transfer_state(state, result, out_bill_no)
            elif status_code == 404:
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