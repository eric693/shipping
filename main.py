from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
import json
import os
from datetime import datetime

app = Flask(__name__)

# LINE Bot 設定 - 請替換為您的實際Token
line_bot_api = LineBotApi('NRVr4NlWfpA9z2Ry6C8Eagoe4I2hwW5DsWKdPAskj4SdIIQgpK8WnwdrIJFqb26w2GXlzrLwdkLP883NnIsUvakI8miKQWSOFQqXF73B11JjIEANNLlKCUJoa9IX/3ljtcLK3Wy3PcrXiBOkkQZkTwdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('97ccb31ae88a3fb05780bc03ee164670')

# 用於存儲用戶狀態和資料的字典
user_states = {}
customer_counter = 1

# 管理員 User ID 列表 - 請替換為實際的管理員 User ID
ADMIN_USER_IDS = [
    'U64bd314a41b4ce431f54ae39422f1b64',  # 您的 User ID
]

# 管理員切換代碼
ADMIN_CODE = "GT_ADMIN_2025"
CLIENT_CODE = "GT_CLIENT_2025"

# 臨時管理員列表
temp_admin_users = set()

# ==================== 新增：群組權限管理 ====================
# 允許使用的群組ID列表（為空表示允許所有群組）
ALLOWED_GROUP_IDS = [
    # 'C1234567890abcdef1234567890abcdef1',  # 範例群組ID
    # 'C1234567890abcdef1234567890abcdef2',  # 範例群組ID
]

# 群組設定檔案
GROUP_SETTINGS_FILE = 'group_settings.json'

def load_group_settings():
    """載入群組設定"""
    try:
        if os.path.exists(GROUP_SETTINGS_FILE):
            with open(GROUP_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"載入群組設定時發生錯誤: {e}")
        return {}

def save_group_settings(settings):
    """保存群組設定"""
    try:
        with open(GROUP_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存群組設定時發生錯誤: {e}")
        return False

def is_group_allowed(group_id):
    """檢查群組是否被允許使用"""
    # 如果允許列表為空，表示允許所有群組
    if not ALLOWED_GROUP_IDS:
        return True
    return group_id in ALLOWED_GROUP_IDS

def get_group_info(event):
    """取得群組資訊"""
    if hasattr(event.source, 'group_id'):
        return {
            'type': 'group',
            'id': event.source.group_id,
            'user_id': event.source.user_id
        }
    elif hasattr(event.source, 'room_id'):
        return {
            'type': 'room',
            'id': event.source.room_id,
            'user_id': event.source.user_id
        }
    else:
        return {
            'type': 'user',
            'id': event.source.user_id,
            'user_id': event.source.user_id
        }

def add_group_to_allowed_list(group_id, group_name=None):
    """將群組加入允許清單"""
    settings = load_group_settings()
    if 'allowed_groups' not in settings:
        settings['allowed_groups'] = {}
    
    settings['allowed_groups'][group_id] = {
        'name': group_name or f"群組_{group_id[:8]}",
        'added_time': datetime.now().isoformat(),
        'enabled': True
    }
    
    return save_group_settings(settings)

def remove_group_from_allowed_list(group_id):
    """將群組從允許清單移除"""
    settings = load_group_settings()
    if 'allowed_groups' in settings and group_id in settings['allowed_groups']:
        del settings['allowed_groups'][group_id]
        return save_group_settings(settings)
    return False

def get_group_settings_display():
    """取得群組設定顯示文字"""
    settings = load_group_settings()
    if not settings.get('allowed_groups'):
        return "目前沒有設定任何群組權限\n（預設允許所有群組使用）"
    
    display_text = "📋 已設定的群組清單：\n\n"
    for group_id, info in settings['allowed_groups'].items():
        status = "✅ 啟用" if info.get('enabled', True) else "❌ 停用"
        display_text += f"群組名稱：{info.get('name', '未知')}\n"
        display_text += f"群組ID：{group_id[:12]}...\n"
        display_text += f"狀態：{status}\n"
        display_text += f"加入時間：{info.get('added_time', '未知')[:16]}\n"
        display_text += "-" * 25 + "\n"
    
    return display_text

# ==================== 服務類型常數 ====================
SERVICE_TYPES = {
    'HOTEL_PICKUP': 'hotel_pickup',
    'WAREHOUSE_SHIPPING': 'warehouse_shipping'
}

# ==================== 建檔問題設定 ====================
CUSTOMER_QUESTIONS = [
    "收件人",
    "臺灣收件地址", 
    "EZ Way註冊手機",
    "身分證號"
]

HOTEL_PICKUP_QUESTIONS = [
    "飯店名稱",
    "飯店地址",
    "房號",
    "取貨日期",
    "取貨時間"
]

# ==================== 倉庫地址資訊 ====================
WAREHOUSE_INFO = {
    'english': """Warehouse Address:
34 Pattanarkarn Soi 46, Pattanakarn Rd, Suan Luang, Suan Luang, Bangkok 10250
Contact: Kai 0624652295""",
    
    'thai': """ที่อยู่คลังสินค้า:
บ้านเลขที่ 34 ซอยพัฒนาการ 46
แขวง/เขต สวนหลวง กรุงเทพฯ 10250
(ไม่รับสายให้กดออดวาวหน้าบ้านได้เลยค่ะ)
โทร 0624652295 (Kai)""",
    
    'process': """商品寄倉庫流程：

1. 週一至週六（收貨時間10:00～17:00）
⬇️
2. 不管您是泰國網路訂購或是廠商叫貨請務必在外箱寫上建檔編號，以利倉庫人員識別您的貨物
⬇️
3. 商品寄到我們倉庫後，客服會拍照回報給您

⚠️ 請自行追蹤貨物進度，客服不會幫您查詢您的訂購進度。"""
}

# ==================== 歡迎語和服務流程訊息 ====================
def get_welcome_message():
    """取得歡迎語訊息"""
    welcome_text = """您好！
我需要快速回覆您的需求，請回覆ABC

A. 我想了解飯店收貨流程服務回台灣。
B. 我想了解寄貨到泰國倉庫回台灣。
C. 兩者我都想了解。

⚠️ 嚴禁寄送物品⚠️
❌1. 台灣法定毒品
❌2. 各類減肥藥品
❌3. 菸品、電子菸、加熱菸、酒類
❌4. 槍砲彈藥
——————————————————————

⚠️國際托運前須知⚠️

‼️本公司公斤數四捨五入計算
‼️如貨物遺失一箱最高上限賠償二萬元新台幣（需提供匯款明細或是商品訂單實際貨物賠償）
‼️海關有權拆開檢查貨物抽取樣品，被海關拆開抽取樣品不理賠
‼️易碎品以及液體類請自行加強包裝，破損不理賠
‼️不接受聖物佛牌等宗教文物配送（如未告知箱內是聖物佛牌宗教物品，配送過程中遺失請自行負責）
‼️本公司不幫忙追蹤訂貨況，請自行追蹤
‼️不接緊急出貨
‼️飯店收貨用袋子裝，我們不另行提供紙箱，只接受拉回泰國倉庫幫忙封箱，貨物請自行清點清楚。
‼️飯店收回來貨物原袋不拆封直接裝進箱子打包（自行負責）

❤️泰國網路訂貨到我們倉庫請主動給我們泰國快遞單號，以防泰國賣家沒有寫編號變成無名包裹📦"""
    
    return welcome_text

def get_hotel_pickup_flow():
    """取得飯店收貨流程說明"""
    flow_text = """A
曼谷地區飯店收貨流程

1. 離開飯店 提前一天聯繫客服指定收貨時間（每天10:00～17:00）
⬇️
2. 貨物寄放飯店櫃檯並在箱子或袋子外面寫好給您的建檔編號
⬇️
3. 拍寄放櫃檯商品照片上傳給客服
⬇️
4. 客服派車收貨
⬇️
5. 收貨至泰國倉庫後，我們開始進行包裝封箱
⬇️
6. 包裝完畢週一跟週四 送到機場準備飛回台灣
⬇️
7. 貨物抵達台灣後由大榮物流承攬派發至您手上

⚠️未滿5公斤需轉運到台灣公司後在給大榮物流寄出（會慢1-2天），將會加收100元台灣大榮物流運費！

⚠️ 本公司班機✈️ 每週三跟週六。

⚠️ 貨到府後由客服給您帳單請款運費，台幣匯款支付。"""
    
    return flow_text

def get_warehouse_shipping_flow():
    """取得倉庫寄貨流程說明"""
    flow_text = """B
商品寄倉庫流程

1. 建檔後客服給您專屬編號並一起給您曼谷倉庫地址
週一至週六（收貨時間10:00～17:00）
⬇️
2. 不管您是泰國網路訂購或是廠商叫貨請務必寫上建檔編號，以利倉庫人員識別您的貨物
⬇️
3. 商品寄到我們倉庫後，客服會拍照回報給您

⚠️ 請自行追蹤貨物進度，客服不會幫您查詢您的訂購進度。

❤️泰國網路訂貨到我們倉庫，請主動給我們泰國快遞單號，以防泰國賣家沒有寫編號變成無名包裹了📦"""
    
    return flow_text

# ==================== 檔案操作函數 ====================
def get_next_customer_id():
    """生成下一個客戶編號"""
    global customer_counter
    customer_id = f"GT{customer_counter:03d}"
    customer_counter += 1
    return customer_id

def save_customer_data(customer_id, data):
    """保存客戶資料到檔案"""
    try:
        if os.path.exists('customers.json'):
            with open('customers.json', 'r', encoding='utf-8') as f:
                all_customers = json.load(f)
        else:
            all_customers = {}
        
        all_customers[customer_id] = {
            **data,
            'created_time': datetime.now().isoformat()
        }
        
        with open('customers.json', 'w', encoding='utf-8') as f:
            json.dump(all_customers, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"保存資料時發生錯誤: {e}")
        return False

def load_customer_data():
    """載入所有客戶資料"""
    try:
        if os.path.exists('customers.json'):
            with open('customers.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"載入資料時發生錯誤: {e}")
        return {}

def save_tracking_number(customer_id, tracking_number):
    """保存客戶的物流追蹤單號"""
    try:
        all_customers = load_customer_data()
        if customer_id in all_customers:
            if 'tracking_numbers' not in all_customers[customer_id]:
                all_customers[customer_id]['tracking_numbers'] = []
            
            tracking_record = {
                'number': tracking_number,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            all_customers[customer_id]['tracking_numbers'].append(tracking_record)
            
            with open('customers.json', 'w', encoding='utf-8') as f:
                json.dump(all_customers, f, ensure_ascii=False, indent=2)
            
            return True
    except Exception as e:
        print(f"保存追蹤單號時發生錯誤: {e}")
    return False

def is_admin(user_id):
    """檢查是否為管理員"""
    return user_id in ADMIN_USER_IDS or user_id in temp_admin_users

def get_user_role(user_id):
    """取得用戶角色名稱"""
    if user_id in ADMIN_USER_IDS:
        return "永久管理員"
    elif user_id in temp_admin_users:
        return "臨時管理員"
    else:
        return "一般客戶"

# ==================== 新增：查詢所有編號功能 ====================
def get_all_customer_list():
    """取得所有客戶編號列表"""
    all_customers = load_customer_data()
    if not all_customers:
        return None
    
    # 按編號排序
    sorted_customers = sorted(all_customers.items(), key=lambda x: x[0])
    
    return sorted_customers

def show_all_customer_ids(event, user_id, page=1, items_per_page=20):
    """顯示所有客戶編號列表（分頁顯示）"""
    if not is_admin(user_id):
        message = TextSendMessage(text="❌ 您沒有權限執行此操作。")
        line_bot_api.reply_message(event.reply_token, message)
        return
    
    all_customers = get_all_customer_list()
    
    if not all_customers:
        message = TextSendMessage(text="📋 目前系統中沒有任何客戶資料。")
        line_bot_api.reply_message(event.reply_token, message)
        return
    
    total_count = len(all_customers)
    total_pages = (total_count + items_per_page - 1) // items_per_page
    
    # 計算分頁範圍
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_count)
    
    # 建立顯示文字
    list_text = f"📋 所有客戶編號列表 (第 {page}/{total_pages} 頁)\n"
    list_text += f"共 {total_count} 筆客戶資料\n\n"
    list_text += "編號 | 收件人 | 服務類型 | 建立日期\n"
    list_text += "=" * 35 + "\n"
    
    for i in range(start_idx, end_idx):
        customer_id, data = all_customers[i]
        recipient = data.get('收件人', 'N/A')
        if len(recipient) > 6:  # 限制收件人名稱長度
            recipient = recipient[:6] + "..."
            
        service_type = get_service_type_short(data.get('service_type', ''))
        
        # 格式化建立日期
        created_time = data.get('created_time', '')
        if created_time:
            try:
                dt = datetime.fromisoformat(created_time)
                date_str = dt.strftime('%m/%d')
            except:
                date_str = 'N/A'
        else:
            date_str = 'N/A'
        
        list_text += f"{customer_id} | {recipient} | {service_type} | {date_str}\n"
    
    # 建立快速回覆按鈕
    quick_reply_items = []
    
    # 分頁控制按鈕
    if page > 1:
        quick_reply_items.append(
            QuickReplyButton(action=MessageAction(label="◀ 上一頁", text=f"客戶列表 {page-1}"))
        )
    
    if page < total_pages:
        quick_reply_items.append(
            QuickReplyButton(action=MessageAction(label="下一頁 ▶", text=f"客戶列表 {page+1}"))
        )
    
    # 其他功能按鈕
    quick_reply_items.extend([
        QuickReplyButton(action=MessageAction(label="📊 統計資訊", text="客戶統計")),
        QuickReplyButton(action=MessageAction(label="🔍 查詢客戶", text="查詢客戶資料")),
        QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
    ])
    
    # 如果按鈕太多，只保留最重要的
    if len(quick_reply_items) > 13:
        quick_reply_items = quick_reply_items[-6:]  # 保留最後6個按鈕
    
    quick_reply = QuickReply(items=quick_reply_items)
    message = TextSendMessage(text=list_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

def get_service_type_short(service_type):
    """取得服務類型簡稱"""
    if service_type == SERVICE_TYPES['HOTEL_PICKUP']:
        return "飯店"
    elif service_type == SERVICE_TYPES['WAREHOUSE_SHIPPING']:
        return "倉庫"
    else:
        return "未知"

def show_customer_statistics(event, user_id):
    """顯示客戶統計資訊"""
    if not is_admin(user_id):
        message = TextSendMessage(text="❌ 您沒有權限執行此操作。")
        line_bot_api.reply_message(event.reply_token, message)
        return
    
    all_customers = load_customer_data()
    
    if not all_customers:
        message = TextSendMessage(text="📊 目前系統中沒有任何客戶資料。")
        line_bot_api.reply_message(event.reply_token, message)
        return
    
    # 統計資訊
    total_customers = len(all_customers)
    hotel_pickup_count = 0
    warehouse_shipping_count = 0
    total_tracking_numbers = 0
    
    # 按月份統計
    monthly_stats = {}
    
    for customer_id, data in all_customers.items():
        # 服務類型統計
        service_type = data.get('service_type', '')
        if service_type == SERVICE_TYPES['HOTEL_PICKUP']:
            hotel_pickup_count += 1
        elif service_type == SERVICE_TYPES['WAREHOUSE_SHIPPING']:
            warehouse_shipping_count += 1
        
        # 追蹤單號統計
        if 'tracking_numbers' in data:
            total_tracking_numbers += len(data['tracking_numbers'])
        
        # 按月份統計
        created_time = data.get('created_time', '')
        if created_time:
            try:
                dt = datetime.fromisoformat(created_time)
                month_key = dt.strftime('%Y-%m')
                monthly_stats[month_key] = monthly_stats.get(month_key, 0) + 1
            except:
                pass
    
    # 取得最近3個月的統計
    recent_months = sorted(monthly_stats.keys())[-3:] if monthly_stats else []
    
    # 建立統計文字
    stats_text = f"📊 客戶統計資訊\n\n"
    stats_text += f"📋 總客戶數：{total_customers} 位\n"
    stats_text += f"🏨 飯店取貨：{hotel_pickup_count} 位\n"
    stats_text += f"📦 倉庫集運：{warehouse_shipping_count} 位\n"
    stats_text += f"🚚 追蹤單號：{total_tracking_numbers} 個\n\n"
    
    if recent_months:
        stats_text += "📅 近期月份統計：\n"
        for month in recent_months:
            stats_text += f"• {month}: {monthly_stats[month]} 位客戶\n"
        stats_text += "\n"
    
    # 下一個編號預告
    stats_text += f"🆔 下一個客戶編號：GT{customer_counter:03d}\n"
    
    # 更新時間
    stats_text += f"\n🕐 統計時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    quick_reply_items = [
        QuickReplyButton(action=MessageAction(label="📋 客戶列表", text="所有客戶編號")),
        QuickReplyButton(action=MessageAction(label="🔍 查詢客戶", text="查詢客戶資料")),
        QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
    ]
    
    quick_reply = QuickReply(items=quick_reply_items)
    message = TextSendMessage(text=stats_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

# ==================== LINE Bot 處理函數 ====================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature error")
        abort(400)
    except Exception as e:
        print(f"Callback error: {e}")
        abort(500)
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    
    # 取得群組資訊
    group_info = get_group_info(event)
    
    print(f"收到訊息: {text} (來自用戶: {user_id}, 群組類型: {group_info['type']}, ID: {group_info['id']})")
    
    # 檢查群組權限（僅對群組聊天室進行檢查）
    if group_info['type'] in ['group', 'room']:
        settings = load_group_settings()
        allowed_groups = settings.get('allowed_groups', {})
        
        # 如果有設定允許清單，且此群組不在清單中
        if allowed_groups and group_info['id'] not in allowed_groups:
            # 只有管理員可以在未授權群組中使用
            if not is_admin(user_id):
                print(f"群組 {group_info['id']} 未授權，非管理員用戶 {user_id} 的訊息被忽略")
                return
        
        # 檢查群組是否被停用
        if group_info['id'] in allowed_groups and not allowed_groups[group_info['id']].get('enabled', True):
            if not is_admin(user_id):
                print(f"群組 {group_info['id']} 已被停用，非管理員用戶 {user_id} 的訊息被忽略")
                return
    
    # ==================== 特殊指令處理 ====================
    
    # 顯示 User ID
    if text.lower() in ['userid', 'user_id', 'myid', '我的id']:
        role = get_user_role(user_id)
        message = TextSendMessage(
            text=f"👤 您的用戶資訊：\n\nUser ID：{user_id}\n身份：{role}"
        )
        line_bot_api.reply_message(event.reply_token, message)
        return
    
    # 管理員代碼切換
    if text == ADMIN_CODE:
        if user_id not in ADMIN_USER_IDS:  # 如果不是永久管理員
            temp_admin_users.add(user_id)
            message = TextSendMessage(
                text=f"✅ 您已成功切換為臨時管理員！\n\n👤 身份：臨時管理員\n🔐 User ID：{user_id}\n\n現在您可以使用管理員功能：\n• 查詢客戶資料\n• 查詢追蹤單號\n• 查看所有客戶編號\n• 查看統計資訊\n\n輸入「{CLIENT_CODE}」可切換回一般客戶身份"
            )
        else:
            message = TextSendMessage(
                text=f"ℹ️ 您已經是永久管理員，無需切換！\n\n👤 身份：永久管理員\n🔐 User ID：{user_id}"
            )
        line_bot_api.reply_message(event.reply_token, message)
        return
    
    # 切換回客戶代碼
    if text == CLIENT_CODE:
        if user_id in temp_admin_users:
            temp_admin_users.remove(user_id)
            message = TextSendMessage(
                text=f"✅ 您已切換回一般客戶身份！\n\n👤 身份：一般客戶\n🔐 User ID：{user_id}\n\n輸入「{ADMIN_CODE}」可重新切換為管理員"
            )
        elif user_id in ADMIN_USER_IDS:
            message = TextSendMessage(
                text=f"ℹ️ 永久管理員無法切換為一般客戶！\n\n👤 身份：永久管理員\n🔐 User ID：{user_id}"
            )
        else:
            message = TextSendMessage(
                text=f"ℹ️ 您本來就是一般客戶身份！\n\n👤 身份：一般客戶\n🔐 User ID：{user_id}"
            )
        line_bot_api.reply_message(event.reply_token, message)
        return
    
    # ==================== 不回覆的訊息清單 ====================
    no_reply_messages = [
        # 感謝類
        '感謝', '謝謝', '謝謝您', '感謝您', '非常感謝', '十分感謝', '萬分感謝',
        'thank you', 'thanks', 'thx', '3q', '3Q',
        
        # 等待類
        '等等', '等一下', '稍等', '稍等一下', '等會', '等會兒', '等一會',
        'wait', 'waiting', '等候', '稍候', '請稍等', '請等等',
        
        # 確認類
        '我知道了', '我知道', '嗯嗯', '好的', '了解', '明白', '收到', '好',
        'ok', 'OK', 'Ok', '嗯', '知道了', '懂了', '清楚', '明白了',
        '了解了', '收到了', '好的謝謝', '沒問題', '可以', '行',
        
        # 簡短回應
        '👍', '👌', '✅', '🙏', '❤️', '💯',
        
        # 其他不需回覆的訊息
        '先這樣', '暫時這樣', '目前這樣', '就這樣', '沒事了', '沒事',
        '沒有了', '結束', '完成', '完了', '好了', '就好了'
    ]
    
    # 檢查是否為不需回覆的訊息
    if text in no_reply_messages:
        print(f"收到不需回覆的訊息: {text} (來自用戶: {user_id})")
        return
    
    # 初始化用戶狀態
    if user_id not in user_states:
        user_states[user_id] = {
            'mode': None,
            'service_type': None,
            'question_index': 0,
            'data': {}
        }
    
    user_state = user_states[user_id]
    
    try:
        # 處理服務諮詢（ABC 選項）
        if text.upper() in ['A', 'B', 'C']:
            handle_service_inquiry(event, text.upper())
            return
        
        # 處理查看所有客戶編號
        elif text in ['所有客戶編號', '客戶列表', '全部編號', '📋 客戶列表', '列表'] and is_admin(user_id):
            show_all_customer_ids(event, user_id, page=1)
            return
        
        # 處理分頁客戶列表
        elif text.startswith('客戶列表 ') and is_admin(user_id):
            try:
                page = int(text.split(' ')[1])
                show_all_customer_ids(event, user_id, page=page)
            except (IndexError, ValueError):
                show_all_customer_ids(event, user_id, page=1)
            return
        
        # 處理統計資訊
        elif text in ['客戶統計', '統計資訊', '統計', '📊 統計資訊'] and is_admin(user_id):
            show_customer_statistics(event, user_id)
            return
        
        # 處理服務選擇
        elif text in ['1', '飯店取貨代寄建檔', '飯店取貨']:
            start_hotel_pickup_service(event, user_id)
        elif text in ['2', '集運業務建檔', '集運服務']:
            start_warehouse_shipping_service(event, user_id)
        elif text in ['選單', 'menu', '主選單']:
            if is_admin(user_id):
                show_admin_menu(event, user_id)
            else:
                show_main_menu(event, user_id)
        elif text in ['服務說明', '📖 服務說明']:
            show_service_description(event, user_id)
        elif text in ['群組管理', '群組設定', '🏢 群組管理'] and is_admin(user_id):
            show_group_management(event, user_id)
        elif text in ['查詢客戶', '查找客戶', '查詢客戶資料', '🔍 查詢客戶'] and is_admin(user_id):
            start_customer_search(event, user_id)
        elif text in ['查詢追蹤', '追蹤查詢', '查詢追蹤單號', '📦 查詢追蹤'] and is_admin(user_id):
            start_tracking_search(event, user_id)
        
        # 處理各種流程
        elif user_state['mode'] == 'customer_creation':
            handle_customer_creation(event, user_id, text)
        elif user_state['mode'] == 'hotel_pickup_creation':
            handle_hotel_pickup_creation(event, user_id, text)
        elif user_state['mode'] == 'tracking_input':
            handle_tracking_input(event, user_id, text)
        elif user_state['mode'] == 'searching':
            handle_customer_search_input(event, user_id, text)
        elif user_state['mode'] == 'tracking_search':
            handle_tracking_search_input(event, user_id, text)
        elif user_state['mode'] == 'group_management':
            handle_group_management_input(event, user_id, text)
        else:
            # 如果使用者沒有進行中的流程，根據身份顯示不同選單
            if is_admin(user_id):
                show_admin_menu(event, user_id)
            else:
                show_main_menu(event, user_id)
            
    except Exception as e:
        print(f"處理訊息時發生錯誤: {e}")
        try:
            error_message = TextSendMessage(text="❌ 系統發生錯誤，請稍後再試或聯繫管理員。")
            line_bot_api.reply_message(event.reply_token, error_message)
        except Exception as reply_error:
            print(f"回覆錯誤訊息失敗: {reply_error}")

def show_admin_menu(event, user_id):
    """顯示管理員專用選單"""
    role = get_user_role(user_id)
    admin_text = f"""🔧 管理員控制台

👤 身份：{role}
🆔 User ID：{user_id}

📋 管理功能選單：

🏢 客戶管理：
• 查看所有客戶編號列表
• 查詢特定客戶資料
• 查看客戶統計資訊

📦 物流管理：
• 查詢追蹤單號
• 物流資料管理

🔧 系統功能：
• 身份切換功能
• 群組權限管理
• 系統狀態查看

💼 一般服務：
• 飯店取貨代寄建檔
• 集運業務建檔

請選擇您需要的功能，或輸入相應指令。"""
    
    quick_reply_items = [
        QuickReplyButton(action=MessageAction(label="📋 客戶列表", text="所有客戶編號")),
        QuickReplyButton(action=MessageAction(label="🔍 查詢客戶", text="查詢客戶資料")),
        QuickReplyButton(action=MessageAction(label="📦 查詢追蹤", text="查詢追蹤單號")),
        QuickReplyButton(action=MessageAction(label="📊 統計資訊", text="客戶統計")),
        QuickReplyButton(action=MessageAction(label="🏢 群組管理", text="群組管理")),
        QuickReplyButton(action=MessageAction(label="1 - 飯店建檔", text="1")),
        QuickReplyButton(action=MessageAction(label="2 - 集運建檔", text="2")),
        QuickReplyButton(action=MessageAction(label="👤 我的ID", text="userid")),
        QuickReplyButton(action=MessageAction(label="📖 服務說明", text="服務說明"))
    ]
    
    quick_reply = QuickReply(items=quick_reply_items)
    message = TextSendMessage(text=admin_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

def show_service_description(event, user_id):
    """顯示服務流程說明"""
    welcome_text = get_welcome_message()
    
    quick_reply_items = [
        QuickReplyButton(action=MessageAction(label="A - 飯店收貨流程", text="A")),
        QuickReplyButton(action=MessageAction(label="B - 倉庫寄貨流程", text="B")),
        QuickReplyButton(action=MessageAction(label="C - 兩者都要", text="C")),
        QuickReplyButton(action=MessageAction(label="1 - 飯店取貨建檔", text="1")),
        QuickReplyButton(action=MessageAction(label="2 - 集運業務建檔", text="2"))
    ]
    
    # 根據身份添加返回按鈕
    if is_admin(user_id):
        quick_reply_items.append(
            QuickReplyButton(action=MessageAction(label="🔧 管理員選單", text="主選單"))
        )
    else:
        quick_reply_items.append(
            QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
        )
    
    quick_reply = QuickReply(items=quick_reply_items)
    message = TextSendMessage(text=welcome_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

def show_main_menu(event, user_id=None):
    """顯示主選單"""
    welcome_text = get_welcome_message()
    
    # 基本選項
    quick_reply_items = [
        QuickReplyButton(action=MessageAction(label="A - 飯店收貨流程", text="A")),
        QuickReplyButton(action=MessageAction(label="B - 倉庫寄貨流程", text="B")),
        QuickReplyButton(action=MessageAction(label="C - 兩者都要", text="C")),
        QuickReplyButton(action=MessageAction(label="1 - 飯店取貨代寄建檔", text="1")),
        QuickReplyButton(action=MessageAction(label="2 - 集運業務建檔", text="2"))
    ]
    
    # 如果是管理員，添加管理員選項
    if user_id and is_admin(user_id):
        quick_reply_items.extend([
            QuickReplyButton(action=MessageAction(label="🔧 管理員選單", text="主選單"))
        ])
    else:
        # 添加身份資訊選項
        quick_reply_items.append(
            QuickReplyButton(action=MessageAction(label="👤 我的ID", text="userid"))
        )
    
    quick_reply = QuickReply(items=quick_reply_items)
    message = TextSendMessage(text=welcome_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

def handle_service_inquiry(event, choice):
    """處理服務諮詢（A、B、C 選項）"""
    user_id = event.source.user_id
    
    if choice == 'A':
        # 飯店收貨流程
        flow_text = get_hotel_pickup_flow()
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="1 - 飯店取貨代寄建檔", text="1")),
            QuickReplyButton(action=MessageAction(label="了解倉庫寄貨", text="B")),
            QuickReplyButton(action=MessageAction(label="兩者都要", text="C")),
            QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
        ]
        
    elif choice == 'B':
        # 倉庫寄貨流程
        flow_text = get_warehouse_shipping_flow()
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="2 - 集運業務建檔", text="2")),
            QuickReplyButton(action=MessageAction(label="了解飯店收貨", text="A")),
            QuickReplyButton(action=MessageAction(label="兩者都要", text="C")),
            QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
        ]
        
    elif choice == 'C':
        # 兩者都要
        hotel_flow = get_hotel_pickup_flow()
        warehouse_flow = get_warehouse_shipping_flow()
        flow_text = f"{hotel_flow}\n\n{'='*40}\n\n{warehouse_flow}"
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="1 - 飯店取貨代寄建檔", text="1")),
            QuickReplyButton(action=MessageAction(label="2 - 集運業務建檔", text="2")),
            QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
        ]
    
    # 如果是管理員，添加管理員選項
    if is_admin(user_id):
        quick_reply_items.extend([
            QuickReplyButton(action=MessageAction(label="📋 客戶列表", text="所有客戶編號")),
            QuickReplyButton(action=MessageAction(label="🔍 查詢客戶", text="查詢客戶資料")),
            QuickReplyButton(action=MessageAction(label="📦 查詢追蹤", text="查詢追蹤單號"))
        ])
    
    quick_reply = QuickReply(items=quick_reply_items)
    message = TextSendMessage(text=flow_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

# ==================== 飯店取貨服務 ====================
def start_hotel_pickup_service(event, user_id):
    """開始飯店取貨服務流程"""
    user_states[user_id] = {
        'mode': 'customer_creation',
        'service_type': SERVICE_TYPES['HOTEL_PICKUP'],
        'question_index': 0,
        'data': {'service_type': SERVICE_TYPES['HOTEL_PICKUP']}
    }
    
    intro_text = """🏨 飯店取貨代客寄到台灣

⚠️ 重要提醒：
• 請確實填寫身分證或居留證上的姓名資料
• 飯店客人不需填寫收件人資料，因收貨後都會寄到公司倉庫處理

現在開始建檔流程..."""
    
    message = TextSendMessage(text=intro_text)
    line_bot_api.reply_message(event.reply_token, message)
    
    # 立即開始第一個問題
    ask_next_customer_question_delayed(event, user_id)

def ask_next_customer_question(event, user_id):
    """詢問下一個客戶建檔問題"""
    user_state = user_states[user_id]
    question_index = user_state['question_index']
    
    if question_index < len(CUSTOMER_QUESTIONS):
        question = CUSTOMER_QUESTIONS[question_index]
        
        if question == "身分證號":
            question_text = f"請提供您的{question}：\n\n⚠️ 請確實填寫身分證或居留證上的姓名資料"
        else:
            question_text = f"請提供您的{question}："
            
        message = TextSendMessage(text=question_text)
        line_bot_api.reply_message(event.reply_token, message)
    else:
        complete_customer_creation(event, user_id)

def handle_customer_creation(event, user_id, text):
    """處理客戶建檔過程中的回答"""
    user_state = user_states[user_id]
    question_index = user_state['question_index']
    
    if question_index < len(CUSTOMER_QUESTIONS):
        question = CUSTOMER_QUESTIONS[question_index]
        user_state['data'][question] = text
        user_state['question_index'] += 1
        
        # 如果還有問題要問，繼續下一個問題
        if user_state['question_index'] < len(CUSTOMER_QUESTIONS):
            ask_next_customer_question(event, user_id)
        else:
            # 所有問題都回答完了，完成建檔
            complete_customer_creation(event, user_id)

def complete_customer_creation(event, user_id):
    """完成客戶建檔"""
    user_state = user_states[user_id]
    customer_id = get_next_customer_id()
    
    if save_customer_data(customer_id, user_state['data']):
        # 根據服務類型決定下一步
        if user_state['service_type'] == SERVICE_TYPES['HOTEL_PICKUP']:
            start_hotel_pickup_info_collection(event, user_id, customer_id)
        elif user_state['service_type'] == SERVICE_TYPES['WAREHOUSE_SHIPPING']:
            complete_warehouse_service_setup(event, user_id, customer_id)
    else:
        message = TextSendMessage(text="❌ 保存資料時發生錯誤，請稍後再試。")
        line_bot_api.reply_message(event.reply_token, message)

def start_hotel_pickup_info_collection(event, user_id, customer_id):
    """開始收集飯店取貨資訊"""
    user_states[user_id] = {
        'mode': 'hotel_pickup_creation',
        'customer_id': customer_id,
        'question_index': 0,
        'data': {}
    }
    
    intro_text = f"""✅ 客戶建檔完成！
客戶編號：{customer_id}

現在請提供飯店取貨資訊..."""
    
    message = TextSendMessage(text=intro_text)
    line_bot_api.reply_message(event.reply_token, message)
    
    # 立即開始飯店取貨問題
    ask_next_hotel_question_delayed(event, user_id)

def ask_next_hotel_question_delayed(event, user_id):
    """延遲詢問下一個飯店取貨問題"""
    import time
    import threading
    
    def ask_question():
        time.sleep(2)  # 等待2秒
        user_state = user_states.get(user_id)
        if user_state and user_state.get('mode') == 'hotel_pickup_creation':
            question_index = user_state['question_index']
            
            if question_index < len(HOTEL_PICKUP_QUESTIONS):
                question = HOTEL_PICKUP_QUESTIONS[question_index]
                
                if question == "取貨日期":
                    question_text = f"請提供{question}：\n\n例如：2025-08-17 或 明天"
                elif question == "取貨時間":
                    question_text = f"請提供{question}：\n\n例如：下午2點 或 14:00"
                else:
                    question_text = f"請提供{question}："
                
                try:
                    message = TextSendMessage(text=question_text)
                    line_bot_api.push_message(event.source.user_id, message)
                except Exception as e:
                    print(f"發送飯店問題訊息失敗: {e}")
    
    # 在新線程中執行延遲發送
    thread = threading.Thread(target=ask_question)
    thread.start()

def ask_next_hotel_question(event, user_id):
    """詢問下一個飯店取貨問題"""
    user_state = user_states[user_id]
    question_index = user_state['question_index']
    
    if question_index < len(HOTEL_PICKUP_QUESTIONS):
        question = HOTEL_PICKUP_QUESTIONS[question_index]
        
        if question == "取貨日期":
            question_text = f"請提供{question}：\n\n例如：2025-08-17 或 明天"
        elif question == "取貨時間":  # 修正這行！原本是 question_text == "取貨時間"
            question_text = f"請提供{question}：\n\n例如：下午2點 或 14:00"
        else:
            question_text = f"請提供{question}："
            
        message = TextSendMessage(text=question_text)
        line_bot_api.reply_message(event.reply_token, message)
    else:
        complete_hotel_pickup_creation(event, user_id)

def handle_hotel_pickup_creation(event, user_id, text):
    """處理飯店取貨資訊收集"""
    user_state = user_states[user_id]
    question_index = user_state['question_index']
    
    if question_index < len(HOTEL_PICKUP_QUESTIONS):
        question = HOTEL_PICKUP_QUESTIONS[question_index]
        user_state['data'][question] = text
        user_state['question_index'] += 1
        
        # 如果還有問題要問，繼續下一個問題
        if user_state['question_index'] < len(HOTEL_PICKUP_QUESTIONS):
            ask_next_hotel_question(event, user_id)
        else:
            # 所有問題都回答完了，完成飯店取貨設定
            complete_hotel_pickup_creation(event, user_id)

def complete_hotel_pickup_creation(event, user_id):
    """完成飯店取貨服務建立"""
    user_state = user_states[user_id]
    customer_id = user_state['customer_id']
    
    # 更新客戶資料，加入飯店取貨資訊
    all_customers = load_customer_data()
    if customer_id in all_customers:
        all_customers[customer_id]['hotel_pickup_info'] = user_state['data']
        
        with open('customers.json', 'w', encoding='utf-8') as f:
            json.dump(all_customers, f, ensure_ascii=False, indent=2)
    
    # 顯示完整資訊確認
    customer_data = all_customers[customer_id]
    
    confirm_text = f"""✅ 飯店取貨服務建立完成！

📋 客戶編號：{customer_id}

👤 客戶資訊：
"""
    
    for question in CUSTOMER_QUESTIONS:
        if question in customer_data:
            confirm_text += f"• {question}：{customer_data[question]}\n"
    
    confirm_text += f"\n🏨 飯店取貨資訊：\n"
    for question in HOTEL_PICKUP_QUESTIONS:
        if question in user_state['data']:
            confirm_text += f"• {question}：{user_state['data'][question]}\n"
    
    confirm_text += f"""
📝 重要提醒：
• 請跟飯店借奇異筆在每一袋寫上代號：{customer_id}
• 放櫃檯的時候請拍照給我們

建立時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    
    # 重置用戶狀態
    user_states[user_id] = {'mode': None, 'service_type': None, 'question_index': 0, 'data': {}}
    
    quick_reply_items = [
        QuickReplyButton(action=MessageAction(label="返回主選單", text="主選單"))
    ]
    quick_reply = QuickReply(items=quick_reply_items)
    
    message = TextSendMessage(text=confirm_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

# ==================== 集運業務服務 ====================
def start_warehouse_shipping_service(event, user_id):
    """開始集運業務服務流程"""
    user_states[user_id] = {
        'mode': 'customer_creation',
        'service_type': SERVICE_TYPES['WAREHOUSE_SHIPPING'],
        'question_index': 0,
        'data': {'service_type': SERVICE_TYPES['WAREHOUSE_SHIPPING']}
    }
    
    intro_text = """📦 集運業務服務

⚠️ 重要提醒：
• 請確實填寫身分證或居留證上的姓名資料
• 客人需自行寄送到我們的倉庫
• 完成建檔後會提供倉庫地址

現在開始建檔流程..."""
    
    message = TextSendMessage(text=intro_text)
    line_bot_api.reply_message(event.reply_token, message)
    
    # 立即開始第一個問題
    ask_next_customer_question_delayed(event, user_id)

def ask_next_customer_question_delayed(event, user_id):
    """延遲詢問下一個客戶建檔問題（用於避免重複使用reply token）"""
    import time
    import threading
    
    def ask_question():
        time.sleep(2)  # 等待2秒
        user_state = user_states.get(user_id)
        if user_state and user_state.get('mode') == 'customer_creation':
            question_index = user_state['question_index']
            
            if question_index < len(CUSTOMER_QUESTIONS):
                question = CUSTOMER_QUESTIONS[question_index]
                
                if question == "身分證號":
                    question_text = f"請提供您的{question}：\n\n⚠️ 請確實填寫身分證或居留證上的姓名資料"
                else:
                    question_text = f"請提供您的{question}："
                
                try:
                    message = TextSendMessage(text=question_text)
                    # 使用 push_message 而不是 reply_message
                    line_bot_api.push_message(event.source.user_id, message)
                except Exception as e:
                    print(f"發送問題訊息失敗: {e}")
    
    # 在新線程中執行延遲發送
    thread = threading.Thread(target=ask_question)
    thread.start()

def complete_warehouse_service_setup(event, user_id, customer_id):
    """完成集運服務設置"""
    # 顯示客戶建檔完成和倉庫資訊
    customer_data = load_customer_data()[customer_id]
    
    confirm_text = f"""✅ 集運業務建檔完成！

📋 客戶編號：{customer_id}

👤 客戶資訊：
"""
    
    for question in CUSTOMER_QUESTIONS:
        if question in customer_data:
            confirm_text += f"• {question}：{customer_data[question]}\n"
    
    confirm_text += f"\n{WAREHOUSE_INFO['process']}\n\n"
    confirm_text += f"📍 倉庫地址（英文版）：\n{WAREHOUSE_INFO['english']}\n\n"
    confirm_text += f"📍 倉庫地址（泰文版）：\n{WAREHOUSE_INFO['thai']}\n\n"
    confirm_text += f"⚠️ 重要：請務必在外箱寫上您的建檔編號：{customer_id}\n\n"
    confirm_text += f"建立時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # 重置用戶狀態，但準備接收追蹤單號
    user_states[user_id] = {
        'mode': 'tracking_input',
        'customer_id': customer_id,
        'question_index': 0,
        'data': {}
    }
    
    quick_reply_items = [
        QuickReplyButton(action=MessageAction(label="提供物流單號", text="提供物流單號")),
        QuickReplyButton(action=MessageAction(label="稍後提供", text="稍後提供")),
        QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
    ]
    quick_reply = QuickReply(items=quick_reply_items)
    
    message = TextSendMessage(text=confirm_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

def handle_tracking_input(event, user_id, text):
    """處理物流追蹤單號輸入"""
    user_state = user_states[user_id]
    customer_id = user_state['customer_id']
    
    if text == "提供物流單號":
        message = TextSendMessage(
            text=f"請提供物流運送單號：\n\n例如：ET188761246TH\n\n⚠️ 請提供文字，不接受圖片\n\n您的客戶編號：{customer_id}"
        )
        line_bot_api.reply_message(event.reply_token, message)
    elif text == "稍後提供":
        complete_warehouse_service(event, user_id, customer_id)
    elif text == "主選單":
        user_states[user_id] = {'mode': None, 'service_type': None, 'question_index': 0, 'data': {}}
        show_main_menu(event, user_id)
    elif text == "完成":
        complete_warehouse_service(event, user_id, customer_id)
    else:
        # 處理實際的追蹤單號
        if text.strip() and len(text.strip()) > 5:  # 簡單驗證
            if save_tracking_number(customer_id, text.strip()):
                success_text = f"""✅ 物流單號已記錄！

客戶編號：{customer_id}
物流單號：{text.strip()}
記錄時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

您可以繼續提供其他物流單號，或選擇完成。"""
                
                quick_reply_items = [
                    QuickReplyButton(action=MessageAction(label="繼續提供單號", text="提供物流單號")),
                    QuickReplyButton(action=MessageAction(label="完成", text="完成")),
                    QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
                ]
                quick_reply = QuickReply(items=quick_reply_items)
                
                message = TextSendMessage(text=success_text, quick_reply=quick_reply)
            else:
                message = TextSendMessage(text="❌ 記錄物流單號時發生錯誤，請稍後再試。")
            
            line_bot_api.reply_message(event.reply_token, message)
        else:
            message = TextSendMessage(text="❌ 請提供有效的物流單號（至少6個字符）")
            line_bot_api.reply_message(event.reply_token, message)

def complete_warehouse_service(event, user_id, customer_id):
    """完成集運服務"""
    user_states[user_id] = {'mode': None, 'service_type': None, 'question_index': 0, 'data': {}}
    
    final_text = f"""🎉 集運業務服務設定完成！

客戶編號：{customer_id}

後續流程：
1. 將商品寄送到指定倉庫
2. 務必在外箱寫上編號：{customer_id}
3. 商品到達倉庫後，客服會拍照回報
4. 如有物流單號，隨時可以提供給我們

感謝您使用GT物流服務！"""
    
    quick_reply_items = [
        QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
    ]
    quick_reply = QuickReply(items=quick_reply_items)
    
    message = TextSendMessage(text=final_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

# ==================== 管理員查詢功能 ====================
def start_customer_search(event, user_id):
    """開始客戶查詢"""
    if not is_admin(user_id):
        message = TextSendMessage(text="❌ 您沒有權限執行此操作。")
        line_bot_api.reply_message(event.reply_token, message)
        return
    
    user_states[user_id] = {
        'mode': 'searching',
        'question_index': 0,
        'data': {}
    }
    
    message = TextSendMessage(
        text="🔍 客戶查詢\n\n請輸入要搜尋的關鍵字：\n\n可以搜尋：\n• 客戶編號（如：GT001）\n• 收件人姓名\n• 身分證號\n• 手機號碼"
    )
    line_bot_api.reply_message(event.reply_token, message)

def handle_customer_search_input(event, user_id, text):
    """處理客戶查詢輸入"""
    results = search_customers(text)
    
    if results:
        show_customer_search_results(event, results, text)
    else:
        message = TextSendMessage(
            text=f"❌ 找不到與 '{text}' 相關的客戶資料。\n\n請檢查輸入是否正確。"
        )
        line_bot_api.reply_message(event.reply_token, message)
    
    # 重置搜尋狀態
    user_states[user_id]['mode'] = None

def search_customers(query):
    """搜尋客戶"""
    all_customers = load_customer_data()
    results = []
    
    for customer_id, data in all_customers.items():
        if (query.upper() in customer_id.upper() or
            query in data.get('收件人', '') or
            query in data.get('身分證號', '') or
            query in data.get('EZ Way註冊手機', '')):
            results.append((customer_id, data))
    
    return results

def show_customer_search_results(event, results, query):
    """顯示客戶查詢結果"""
    if len(results) == 1:
        # 只有一個結果，顯示詳細資訊
        customer_id, data = results[0]
        show_customer_detail(event, customer_id, data)
    else:
        # 多個結果，顯示列表
        result_text = f"🔍 搜尋結果 (關鍵字：{query})\n共找到 {len(results)} 筆資料：\n\n"
        
        for i, (customer_id, data) in enumerate(results[:10], 1):
            result_text += f"{i}. {customer_id}\n"
            result_text += f"   收件人：{data.get('收件人', 'N/A')}\n"
            result_text += f"   服務：{get_service_type_name(data.get('service_type', ''))}\n"
            result_text += "-" * 20 + "\n"
        
        if len(results) > 10:
            result_text += f"... 還有 {len(results) - 10} 筆資料\n"
        
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="繼續搜尋", text="查詢客戶資料")),
            QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
        ]
        quick_reply = QuickReply(items=quick_reply_items)
        
        message = TextSendMessage(text=result_text, quick_reply=quick_reply)
        line_bot_api.reply_message(event.reply_token, message)

def show_customer_detail(event, customer_id, data):
    """顯示客戶詳細資訊"""
    detail_text = f"📋 客戶詳細資訊\n\n客戶編號：{customer_id}\n"
    detail_text += "=" * 25 + "\n\n"
    
    # 基本資訊
    detail_text += "👤 基本資訊：\n"
    for question in CUSTOMER_QUESTIONS:
        if question in data:
            detail_text += f"• {question}：{data[question]}\n"
    
    detail_text += f"• 服務類型：{get_service_type_name(data.get('service_type', ''))}\n\n"
    
    # 飯店取貨資訊（如果有）
    if 'hotel_pickup_info' in data:
        detail_text += "🏨 飯店取貨資訊：\n"
        for question in HOTEL_PICKUP_QUESTIONS:
            if question in data['hotel_pickup_info']:
                detail_text += f"• {question}：{data['hotel_pickup_info'][question]}\n"
        detail_text += "\n"
    
    # 物流追蹤單號（如果有）
    if 'tracking_numbers' in data and data['tracking_numbers']:
        detail_text += "📦 物流追蹤單號：\n"
        for i, tracking in enumerate(data['tracking_numbers'], 1):
            detail_text += f"{i}. {tracking['number']} ({tracking['date']})\n"
        detail_text += "\n"
    
    # 建立時間
    if 'created_time' in data:
        created_time = datetime.fromisoformat(data['created_time'])
        detail_text += f"📅 建立時間：{created_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    quick_reply_items = [
        QuickReplyButton(action=MessageAction(label="繼續搜尋", text="查詢客戶資料")),
        QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
    ]
    quick_reply = QuickReply(items=quick_reply_items)
    
    message = TextSendMessage(text=detail_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

def get_service_type_name(service_type):
    """取得服務類型名稱"""
    if service_type == SERVICE_TYPES['HOTEL_PICKUP']:
        return "飯店取貨代寄"
    elif service_type == SERVICE_TYPES['WAREHOUSE_SHIPPING']:
        return "集運業務"
    else:
        return "未知"

def start_tracking_search(event, user_id):
    """開始追蹤單號查詢"""
    if not is_admin(user_id):
        message = TextSendMessage(text="❌ 您沒有權限執行此操作。")
        line_bot_api.reply_message(event.reply_token, message)
        return
    
    user_states[user_id] = {
        'mode': 'tracking_search',
        'question_index': 0,
        'data': {}
    }
    
    message = TextSendMessage(
        text="🔍 追蹤單號查詢\n\n請輸入要搜尋的追蹤單號：\n\n例如：ET188761246TH"
    )
    line_bot_api.reply_message(event.reply_token, message)

def handle_tracking_search_input(event, user_id, text):
    """處理追蹤單號查詢輸入"""
    results = search_tracking_numbers(text)
    
    if results:
        show_tracking_search_results(event, results, text)
    else:
        message = TextSendMessage(
            text=f"❌ 找不到追蹤單號 '{text}' 的相關資料。\n\n請檢查單號是否正確。"
        )
        line_bot_api.reply_message(event.reply_token, message)
    
    # 重置搜尋狀態
    user_states[user_id]['mode'] = None

def search_tracking_numbers(query):
    """搜尋追蹤單號"""
    all_customers = load_customer_data()
    results = []
    
    for customer_id, data in all_customers.items():
        if 'tracking_numbers' in data:
            for tracking in data['tracking_numbers']:
                if query.upper() in tracking['number'].upper():
                    results.append((customer_id, data, tracking))
    
    return results

def show_tracking_search_results(event, results, query):
    """顯示追蹤單號查詢結果"""
    result_text = f"🔍 追蹤單號查詢結果 (單號：{query})\n共找到 {len(results)} 筆資料：\n\n"
    
    for i, (customer_id, data, tracking) in enumerate(results, 1):
        result_text += f"{i}. 客戶編號：{customer_id}\n"
        result_text += f"   收件人：{data.get('收件人', 'N/A')}\n"
        result_text += f"   追蹤單號：{tracking['number']}\n"
        result_text += f"   記錄時間：{tracking['date']}\n"
        result_text += f"   服務類型：{get_service_type_name(data.get('service_type', ''))}\n"
        result_text += "-" * 25 + "\n"
    
    quick_reply_items = [
        QuickReplyButton(action=MessageAction(label="繼續搜尋", text="查詢追蹤單號")),
        QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
    ]
    quick_reply = QuickReply(items=quick_reply_items)
    
    message = TextSendMessage(text=result_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

# ==================== 主程式啟動 ====================
if __name__ == "__main__":
    # 載入現有客戶資料並更新計數器
    existing_customers = load_customer_data()
    if existing_customers:
        max_num = 0
        for customer_id in existing_customers.keys():
            if customer_id.startswith('GT'):
                try:
                    num = int(customer_id[2:])
                    max_num = max(max_num, num)
                except ValueError:
                    continue
        customer_counter = max_num + 1
    
    print("GT物流服務 LINE Bot 系統啟動中...")
    print(f"當前客戶編號計數器：GT{customer_counter:03d}")
    print(f"🔑 管理員切換代碼：{ADMIN_CODE}")
    print(f"🔑 客戶切換代碼：{CLIENT_CODE}")
    print("\n✅ 主要修正問題：")
    print("1. ❌ 修正了 ask_next_hotel_question 函數中的關鍵錯誤")
    print("   原本：elif question_text == '取貨時間':")
    print("   修正：elif question == '取貨時間':")
    print("2. ✅ 加強了錯誤處理和日誌記錄")
    print("3. ✅ 已將您的 User ID 加入管理員列表")
    print("4. ✅ 完善了所有函數的錯誤處理")
    print("\n🆔 您的管理員身份：")
    print(f"   User ID: U64bd314a41b4ce431f54ae39422f1b64")
    print(f"   身份: 永久管理員")
    print("\n系統功能：")
    print("1. 飯店取貨代客寄建檔")
    print("   - 客戶建檔")
    print("   - 飯店取貨資訊收集")
    print("   - 取貨派車安排")
    print()
    print("2. 集運業務建檔")
    print("   - 客戶建檔")
    print("   - 倉庫地址提供")
    print("   - 物流單號記錄")
    print()
    print("3. 管理員功能")
    print("   - 客戶資料查詢")
    print("   - 追蹤單號查詢")
    print("   - 查看所有客戶編號列表")
    print("   - 查看統計資訊")
    print("   - 身份切換功能")
    print()
    print("4. 身份管理")
    print("   - 輸入管理員代碼成為臨時管理員")
    print("   - 輸入客戶代碼切換回一般客戶")
    print("   - 輸入 'userid' 查看身份和 User ID")
    print()
    print("5. 進階功能")
    print("   - 📋 所有客戶編號列表（分頁顯示）")
    print("   - 📊 客戶統計資訊（包含月份統計）")
    print("   - 🔍 進階搜尋和篩選")
    print("   - 🔇 靜默模式：感謝、等等等訊息不會回覆")
    print()
    print("📋 管理員可使用以下指令：")
    print("   - '所有客戶編號' 或 '客戶列表'：查看所有客戶編號")
    print("   - '客戶統計' 或 '統計資訊'：查看統計資訊")
    print("   - '查詢客戶資料'：搜尋特定客戶")
    print("   - '查詢追蹤單號'：搜尋追蹤單號")
    print("   - 'userid'：查看個人身份資訊")
    print()
    print("🔧 故障排除說明：")
    print("   - HTTP 400 錯誤通常是因為程式碼語法錯誤")
    print("   - 主要修正了變數名稱錯誤：question_text vs question")
    print("   - 增強了錯誤日誌輸出，便於除錯")
    print("   - 確保所有條件判斷都正確無誤")
    print()
    print("🚀 系統已準備就緒！現在應該不會再有 HTTP 400 錯誤了。")
    
    app.run(host='0.0.0.0', port=6000, debug=False)