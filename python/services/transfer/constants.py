"""商家转账相关常量配置"""

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



# 可重试的业务错误码
RETRIABLE_BIZ_CODES = {
    "SYSTEM_ERROR",  # 系统错误
    "NETWORK_ERROR",  # 网络错误
    "FREQUENCY_LIMITED",  # 频率限制
    "RESOURCE_INSUFFICIENT",  # 资源不足
    "BANK_ERROR",  # 银行系统异常
}

# API配置
API_CONFIGS = {
    "create_transfer": {
        # 接口请求方法
        "method": "POST",
        # 接口请求路径
        "path": "/v3/fund-app/mch-transfer/transfer-bills",
        # 接口描述
        "desc": "创建商家转账API",
    },
    "query_transfer": {
        "method": "GET",
        "path": "/v3/fund-app/mch-transfer/transfer-bills/out-bill-no/{out_bill_no}",
        "desc": "查询商家转账API",
    },
}
