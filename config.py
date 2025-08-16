# config.py
# GT物流服務系統設定檔

# LINE Bot 設定
LINE_BOT_CONFIG = {
    'CHANNEL_ACCESS_TOKEN': 'NRVr4NlWfpA9z2Ry6C8Eagoe4I2hwW5DsWKdPAskj4SdIIQgpK8WnwdrIJFqb26w2GXlzrLwdkLP883NnIsUvakI8miKQWSOFQqXF73B11JjIEANNLlKCUJoa9IX/3ljtcLK3Wy3PcrXiBOkkQZkTwdB04t89/1O/w1cDnyilFU=',
    'CHANNEL_SECRET': '97ccb31ae88a3fb05780bc03ee164670'
}

# 管理員設定
ADMIN_USERS = [
    'YOUR_ADMIN_USER_ID_1',  # 請替換為實際的管理員 User ID
    'YOUR_ADMIN_USER_ID_2',  # 可以添加多個管理員
]

# 服務設定
SERVICE_CONFIG = {
    'CUSTOMER_ID_PREFIX': 'GT',  # 客戶編號前綴
    'WAREHOUSE_HOURS': '10:00～17:00',  # 倉庫收貨時間
    'WAREHOUSE_DAYS': '週一至週六'  # 倉庫收貨日期
}

# 倉庫資訊
WAREHOUSE_ADDRESS = {
    'ENGLISH': {
        'address': '34 Pattanarkarn Soi 46, Pattanakarn Rd, Suan Luang, Suan Luang, Bangkok 10250',
        'contact_name': 'Kai',
        'contact_phone': '0624652295'
    },
    'THAI': {
        'address': 'บ้านเลขที่ 34 ซอยพัฒนาการ 46\nแขวง/เขต สวนหลวง กรุงเทพฯ 10250',
        'contact_note': '(ไม่รับสายให้กดออดวาวหน้าบ้านได้เลยค่ะ)',
        'contact_name': 'Kai',
        'contact_phone': '0624652295'
    }
}

# 客戶建檔欄位設定
CUSTOMER_FIELDS = [
    {
        'field': '收件人',
        'required': True,
        'validation': 'text',
        'note': '請確實填寫身分證或居留證上的姓名'
    },
    {
        'field': '收件地址',
        'required': True,
        'validation': 'text',
        'note': None
    },
    {
        'field': 'EZ Way註冊手機',
        'required': True,
        'validation': 'phone',
        'note': None
    },
    {
        'field': '身分證號',
        'required': True,
        'validation': 'id_number',
        'note': '請確實填寫身分證或居留證上的資料'
    }
]

# 飯店取貨欄位設定
HOTEL_PICKUP_FIELDS = [
    {
        'field': '飯店名稱',
        'required': True,
        'validation': 'text',
        'note': None
    },
    {
        'field': '飯店地址',
        'required': True,
        'validation': 'text',
        'note': None
    },
    {
        'field': '房號',
        'required': True,
        'validation': 'text',
        'note': None
    },
    {
        'field': '取貨日期',
        'required': True,
        'validation': 'date',
        'note': '例如：2025-08-17 或 明天'
    },
    {
        'field': '取貨時間',
        'required': True,
        'validation': 'time',
        'note': '例如：下午2點 或 14:00'
    }
]

# 系統訊息設定
SYSTEM_MESSAGES = {
    'WELCOME': """🚚 GT物流服務系統

請選擇您需要的服務：

1️⃣ 飯店取貨代客寄到台灣
   - 我們到飯店取貨
   - 代為寄送到台灣

2️⃣ 集運業務
   - 客人自行寄送到倉庫
   - 統一寄送到台灣

請回覆數字 1 或 2 選擇服務""",

    'HOTEL_PICKUP_INTRO': """🏨 飯店取貨代客寄到台灣

⚠️ 重要提醒：
• 請確實填寫身分證或居留證上的姓名資料
• 飯店客人不需填寫收件人資料，因收貨後都會寄到公司倉庫處理

現在開始建檔流程...""",

    'WAREHOUSE_INTRO': """📦 集運業務服務

⚠️ 重要提醒：
• 請確實填寫身分證或居留證上的姓名資料
• 客人需自行寄送到我們的倉庫
• 完成建檔後會提供倉庫地址

現在開始建檔流程...""",

    'SHIPPING_PROCESS': """商品寄倉庫流程：

1. 週一至週六（收貨時間10:00～17:00）
⬇️
2. 不管您是泰國網路訂購或是廠商叫貨請務必在外箱寫上建檔編號，以利倉庫人員識別您的貨物
⬇️
3. 商品寄到我們倉庫後，客服會拍照回報給您

⚠️ 請自行追蹤貨物進度，客服不會幫您查詢您的訂購進度。""",

    'HOTEL_REMINDER': """📝 重要提醒：
• 請跟飯店借奇異筆在每一袋寫上代號：{customer_id}
• 放櫃檯的時候請拍照給我們""",

    'TRACKING_INSTRUCTION': """如無法填寫外箱代碼請提供物流運送單號：
Ex: ET188761246TH（不接受圖片）""",

    'ERROR_GENERAL': '❌ 系統發生錯誤，請稍後再試或聯繫管理員。',
    'ERROR_PERMISSION': '❌ 您沒有權限執行此操作。',
    'ERROR_SAVE_DATA': '❌ 保存資料時發生錯誤，請稍後再試。',
    'ERROR_INVALID_INPUT': '❌ 輸入格式不正確，請重新輸入。',
    'ERROR_NOT_FOUND': '❌ 找不到相關資料，請檢查輸入是否正確。'
}

# 資料檔案設定
DATA_FILES = {
    'CUSTOMERS': 'customers.json',
    'TRACKING_LOG': 'tracking_log.json',
    'SYSTEM_LOG': 'system_log.json'
}

# 日誌設定
LOGGING_CONFIG = {
    'LEVEL': 'INFO',
    'FORMAT': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'FILE': 'gt_logistics.log'
}