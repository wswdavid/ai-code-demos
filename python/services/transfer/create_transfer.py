"""创建商家转账API"""
import uuid
import time
from loguru import logger
from services.wechat_pay_base import WeChatPayBase
from .constants import (
    MIN_TRANSFER_AMOUNT, MAX_TRANSFER_AMOUNT, 
    TRANSFER_SCENES, API_CONFIGS
)
from .constants import (
    NEED_CONFIRM_STATES,
    RETRIABLE_STATES, FINAL_STATES, TRANSFER_SCENES,RETRIABLE_ERROR_CODES
)
class CreateTransfer(WeChatPayBase):
    """创建商家转账实现类"""
    
    def __init__(self):
        super().__init__()
        self.api_config = API_CONFIGS["create_transfer"]
    
    def validate_transfer_params(self, transfer_data):
        """
        验证转账参数
        
        Args:
            transfer_data (dict): 完整的转账请求参数
            {
                "appid": "wx8888888888888888",
                "out_bill_no": "BILL123456789",
                "transfer_scene_id": "1001",
                "openid": "o4GgauInH_RCEdvrrNGrntXDuXXX",
                "transfer_amount": 100,
                "transfer_remark": "测试转账",
                "transfer_scene_report_infos": [
                    {"info_type": "活动名称", "info_content": "新年活动"},
                    {"info_type": "奖励说明", "info_content": "抽奖活动奖励"}
                ]
            }
            
        Returns:
            tuple: (is_valid, error_msg)
        """
        # 1. 基础字段校验
        required_fields = {
            "appid", "out_bill_no", "transfer_scene_id", 
            "openid", "transfer_amount", "transfer_remark",
            "transfer_scene_report_infos"
        }
        
        missing_fields = required_fields - set(transfer_data.keys())
        if missing_fields:
            return False, f"缺少必填字段: {', '.join(missing_fields)}"
        
        # 2. 金额校验
        amount = transfer_data["transfer_amount"]
        if not isinstance(amount, int):
            return False, "转账金额必须为整数"
        if amount < MIN_TRANSFER_AMOUNT:
            return False, f"转账金额不能小于{MIN_TRANSFER_AMOUNT/100}元"
        if amount > MAX_TRANSFER_AMOUNT:
            return False, f"转账金额不能大于{MAX_TRANSFER_AMOUNT/100}元"
        
        # 3. 场景校验
        scene_id = transfer_data["transfer_scene_id"]
        scene = None
        for scene_key, scene_config in TRANSFER_SCENES.items():
            if scene_config["scene_id"] == scene_id:
                scene = scene_config
                break
                
        if not scene:
            return False, f"无效的转账场景ID: {scene_id}"
        
        # 4. 报备信息校验
        report_infos = transfer_data["transfer_scene_report_infos"]
        required_configs = scene["report_configs"]
        
        if len(report_infos) != len(required_configs):
            return False, f"报备信息数量不匹配，需要{len(required_configs)}个，实际提供{len(report_infos)}个"
        
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

    def handle_http_status(self, status_code, result):
        """处理HTTP状态码
        
        状态码处理说明：
        1. 2xx (成功):
           - 继续处理业务逻辑
        
        2. 429 (请求频率超限):
           - 实现限流控制
           - 建议使用令牌桶算法
           - 延迟重试，建议等待2-5秒
           - 重要：重试时必须使用原商户订单号，不要更换订单号
        
        3. 5xx (服务器错误):
           - 记录错误日志
           - 使用指数退避算法重试
           - 建议最多重试3次
           - 持续失败时发送告警
           - 重要：重试时必须使用原商户订单号，避免重复转账风险
           - 建议：先查询订单状态，确认订单不存在才重试
        
        4. 其他错误:
           - 记录详细错误信息
           - 检查请求参数是否正确
           - 验证签名是否正确
           - 确认证书是否有效
           - 重要：4xx错误通常表示请求有误，修复问题后可使用原商户订单号重试
        """
        # 获取业务错误码
        error_code = result.get('code', '')
        out_bill_no = result.get('out_bill_no', '')
        
        match status_code:
            case code if 200 <= code < 300:
                return 'continue', None
                
            case 429:
                logger.warning(f"请求频率超限，使用原商户订单号重试，商户单号: {out_bill_no}")
                return 'retry', f"请求频率超限: {result.get('message', '')}，请稍后使用原单号重试"
                
            case code if code in {500, 502, 503, 504}:
                if error_code in RETRIABLE_ERROR_CODES:
                    logger.warning(f"服务端错误(可重试)，错误码: {error_code}，商户单号: {out_bill_no}")
                    return 'retry', f"服务端错误({error_code})，请先查询订单状态，使用原单号重试"
                else:
                    logger.error(f"服务端错误(不可重试)，错误码: {error_code}，商户单号: {out_bill_no}")
                    return 'error', f"服务端错误({error_code})，请检查错误信息并联系技术支持"
                
            case _:
                if error_code in RETRIABLE_ERROR_CODES:
                    logger.warning(f"业务错误(可重试)，错误码: {error_code}，商户单号: {out_bill_no}")
                    return 'retry', f"业务错误({error_code})，请先查询订单状态，使用原单号重试"
                else:
                    logger.error(f"业务错误(不可重试)，错误码: {error_code}，商户单号: {out_bill_no}")
                    return 'error', f"业务错误({error_code})，请修复问题后再重试"


    def handle_transfer_result(self, data:dict):
        """处理转账状态"""
        state = data.get("state", "")
        out_bill_no = data.get("out_bill_no", "")
        
        # 定义不同的失败原因处理策略
        FAIL_REASON_HANDLERS = {
            "ACCOUNT_FROZEN": {
                "level": "error",
                "message": "账户被冻结",
                "action": "contact_support",
                "retry": False,
                "actions": [
                    "记录账户异常",
                    "联系微信支付客服"
                ]
            },
            "REAL_NAME_CHECK_FAIL": {
                "level": "warning",
                "message": "实名校验失败",
                "action": "verify_user",
                "retry": False,
                "actions": [
                    "通知用户完善实名信息",
                    "更新用户实名状态",
                    "等待用户重新实名认证"
                ]
            },
            "TRANSFER_QUOTA_EXCEED": {
                "level": "warning",
                "message": "超出转账额度",
                "action": "quota_exceed",
                "retry": False,
                "actions": [
                    "记录额度超限",
                    "检查转账金额",
                    "考虑分批转账"
                ]
            },
            "PAYEE_ACCOUNT_ABNORMAL": {
                "level": "warning",
                "message": "收款账户异常",
                "action": "check_account",
                "retry": False,
                "actions": [
                    "通知用户检查账户状态",
                    "记录异常账户信息",
                    "考虑更换收款账户"
                ]
            },
            "TRANSFER_RISK": {
                "level": "error",
                "message": "转账存在风险",
                "action": "risk_control",
                "retry": False,
                "actions": [
                    "记录风险信息",
                ]
            },
            "NAME_NOT_CORRECT": {
                "level": "warning",
                "message": "姓名校验不通过",
                "action": "verify_name",
                "retry": False,
                "actions": [
                    "核实用户姓名信息",
                    "通知用户更正姓名",
                    "更新用户信息"
                ]
            }
        }

        match state:
            case "ACCEPTED":
                # 当状态为ACCEPTED时，记录日志并继续处理
                logger.info(f"转账申请已受理，商户单号: {out_bill_no}")
                # 注意：此时需要通过商户单号轮询查询转账状态
                # 需要实现以下逻辑：
                # 1. 将订单信息保存到数据库
                # 2. 使用异步任务定期查询转账状态（设置合理的查询间隔） / 接受回调通知扭转状态
                # 3. 设置最大查询次数，超过后告警提醒
                
            case state if state in NEED_CONFIRM_STATES:
                # 需要用户确认的状态
                logger.info(f"等待用户确认收款，商户单号: {out_bill_no}")
                # 需要实现以下逻辑：
                # 1. 更新订单状态为等待确认
                # 2. 设置确认超时时间
                # 3. 添加定时任务检查确认状态
                # 4. 超时后发送提醒通知
                
            case state if state in RETRIABLE_STATES:
                # 可重试的状态
                logger.warning(f"转账遇到可重试状态: {state}，商户单号: {out_bill_no}")
                # 需要实现以下逻辑：
                # 1. 记录重试次数
                # 2. 使用指数退避算法计算下次重试时间
                # 3. 超过最大重试次数时发送告警
                # 4. 更新订单状态为待重试
                
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
                    # 3. 释放预扣的资金额度
                    # 4. 通知相关业务方
                    # 5. 考虑是否需要重新发起转账
                else:
                    # 获取失败原因
                    fail_reason = data.get("fail_reason", "UNKNOWN")
                    handler = FAIL_REASON_HANDLERS.get(fail_reason, {
                        "level": "error",
                        "message": "未知失败原因",
                        "action": "unknown_error",
                        "retry": False,
                        "actions": [
                            "记录详细错误信息",
                            "人工介入处理",
                            "联系技术支持"
                        ]
                    })
                    logger.error(
                        f"转账失败，状态: {state}，失败原因: {fail_reason}，"
                        f"商户单号: {out_bill_no}，处理建议: {', '.join(handler['actions'])}"
                    )
                    
                    # 需要实现以下逻辑：
                    # 1. 更新订单状态为失败
                    # 2. 记录具体失败原因和处理建议
                    # 3. 根据不同失败原因执行对应的处理流程
                    # 4. 发送失败通知（包含处理建议）
                    # 5. 对于特定失败原因，触发自动化处理流程
                    
                    if handler["retry"]:
                        # 对于可重试的失败原因，设置重试策略
                        # 1. 记录重试次数
                        # 2. 设置下次重试时间
                        # 3. 触发重试任务
                        pass
                    else:
                        # 对于不可重试的失败原因
                        # 1. 标记订单为最终失败
                        # 2. 触发补偿流程
                        # 3. 发送告警通知
                        pass
                    
                    # 根据不同的action执行对应的处理逻辑
                    match handler["action"]:
                        case "contact_support":
                            # 需要联系客服处理的情况
                            pass
                        case "verify_user":
                            # 需要用户重新验证的情况
                            pass
                        case "quota_exceed":
                            # 额度超限的处理
                            pass
                        case "check_account":
                            # 账户异常的处理
                            pass
                        case "risk_control":
                            # 风险控制相关处理
                            pass
                        case "verify_name":
                            # 姓名验证相关处理
                            pass
                        case _:
                            # 其他未知情况的处理
                            pass
            case _:
                # 未知状态处理
                logger.error(f"未知转账状态: {state}，商户单号: {out_bill_no}")
                # 需要实现以下逻辑：
                # 1. 记录异常状态
                # 2. 发送告警通知
                # 3. 人工介入处理
                raise ValueError(f"未知的转账状态: {state}")


    def create_transfer_order(self, openid, amount, batch_name, detail_remark="", scene="CASH_MARKETING",):
        """
        创建商家转账订单
        """

        out_bill_no = f"BILL{int(time.time())}{uuid.uuid4().hex[:8]}"
        scene_config = TRANSFER_SCENES.get(scene)
        scene_id = scene_config["scene_id"]
        
        # 构造完整的请求参数
        transfer_data = {
            "appid": self.app_id,
            "out_bill_no": out_bill_no,
            "transfer_scene_id": scene_id,
            "openid": openid,
            "transfer_amount": amount,
            "transfer_remark": detail_remark or batch_name,
            "transfer_scene_report_infos": [
                {"info_type": "活动名称", "info_content": batch_name},
                {"info_type": "奖励说明", "info_content": detail_remark or "商家转账"},
            ]
        }
        
        # 参数校验
        is_valid, error_msg = self.validate_transfer_params(transfer_data)
        if not is_valid:
            raise 

        # 发送请求
        status_code, result = self._make_request(
            self.api_config["method"],
            self.api_config["path"],
            transfer_data
        )
        
        # 处理HTTP状态
        action_type, error_msg = self.handle_http_status(status_code, result)
        if action_type != 'continue':
            return {
                "msg": error_msg,
                "out_bill_no": out_bill_no,
                "data": result,
                "action_type": action_type
            }
        
        # 处理业务结果
        transfer_result = self.handle_transfer_result(result)
        return transfer_result
