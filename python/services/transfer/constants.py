"""微信转账相关常量配置"""

# 转账金额限制(单位:分)
MIN_TRANSFER_AMOUNT = 30  # 最小转账金额0.3元
MAX_TRANSFER_AMOUNT = 2000000  # 最大转账金额2万元

# 转账状态映射表
STATE_MAP = {
    "ACCEPTED": "转账已受理",
    "PROCESSING": "转账处理中",
    "WAIT_USER_CONFIRM": "待收款用户确认",
    "TRANSFERING": "转账处理中",
    "SUCCESS": "转账成功",
    "FAIL": "转账失败",
    "CANCELING": "转账撤销中",
    "CANCELLED": "转账已撤销",
}

# 已受理状态
ACCEPTED_STATES = {
    "ACCEPTED",
}

# 需要用户确认的状态
NEED_CONFIRM_STATES = {
    "WAIT_USER_CONFIRM",
}

# 可以重试的状态
RETRIABLE_STATES = {
    "PROCESSING",
    "TRANSFERING",
}

# 终态状态
FINAL_STATES = {
    "SUCCESS",
    "FAIL",
    "CANCELLED",
}

# 转账场景配置
TRANSFER_SCENES = {
    "现金营销": {  # 现金营销
        "scene_id": "1000",
        "user_perceptions": ["活动奖励", "现金奖励"],
        "report_configs": [
            {"info_type": "活动名称", "required": True, "desc": "请在信息内容描述用户参与活动的名称，如新会员有礼"},
            {"info_type": "奖励说明", "required": True, "desc": "请在信息内容描述用户因为什么奖励获取这笔资金，如注册会员抽奖一等奖"}
        ]
    },
    # ... 其他场景配置保持不变 ...
}


# 可重试的业务错误码
RETRIABLE_BIZ_CODES = {
    "SYSTEM_ERROR",         # 系统错误
    "NETWORK_ERROR",        # 网络错误
    "FREQUENCY_LIMITED",    # 频率限制
    "RESOURCE_INSUFFICIENT",# 资源不足
    "BANK_ERROR",          # 银行系统异常
}

# API配置
API_CONFIGS = {
    "create_transfer": {
        "method": "POST",
        "path": "/v3/fund-app/mch-transfer/transfer-bills",
        "desc": "创建商家转账API",
    },
    "query_transfer": {
        "method": "GET",
        "path": "/v3/fund-app/mch-transfer/transfer-bills/out-bill-no/{out_bill_no}",
        "desc": "查询商家转账API",
    }
}
