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
                "required": True,
                "desc": "请在信息内容描述用户参与活动的名称，如新会员有礼",
            },
            {
                "info_type": "奖励说明",
                "required": True,
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
                "required": True,
                "desc": "请在信息内容描述收款用户的岗位类型，如外卖员、专家顾问",
            },
            {
                "info_type": "报酬说明",
                "required": True,
                "desc": "请请在信息内容描述用户接收当前这笔报酬的原因，如7月份配送费，高温补贴",
            },
        ],
    },
    # ... 其他场景配置保持不变 ...
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
