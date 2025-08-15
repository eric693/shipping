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

# LINE Bot 設定
line_bot_api = LineBotApi('NHv54nNB1d2yFR5rhfjvRIcKR8DtM+g/H2kXkVrPRJeeQrOKoM5ezA8HnnoGIm+iUHRYTLtMxa10Lr5Irems1wb6YQSOMCkJb+8oSwyOt5DdJs/gmuaC5gTz689eCXoCJFJIYLiQY/9EeYB+Ox+WHQdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('0a486d77dd9aea4bb56500ca7d0661be')

# 派車群組 ID - 請替換為實際群組 ID
DISPATCH_GROUP_ID = 'C336c58b3f698fffbe565c256589f193f'

# 用於存儲用戶狀態和資料的字典
user_states = {}
customer_data = {}
customer_counter = 1

# 管理員 User ID 列表 (請替換為實際的管理員 User ID)
ADMIN_USER_IDS = [
    'U215dfe5f0cdc8c5ddd970a5d2fb4b288',  # 請替換為實際的管理員 User ID
    'your_admin_user_id_2',  # 可以添加多個管理員
]

# 叫車狀態常數
RIDE_STATUS = {
    'PENDING': '等待派車',
    'ASSIGNED': '已指派司機',
    'PICKED_UP': '已接客',
    'COMPLETED': '行程完成',
    'CANCELLED': '已取消'
}

# ==================== 檔案操作函數 ====================
def load_completed_users():
    """載入已完成建立的使用者列表"""
    try:
        if os.path.exists('completed_users.json'):
            with open('completed_users.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"載入已完成使用者列表時發生錯誤: {e}")
        return []

def save_completed_user(user_id):
    """保存已完成建立的使用者"""
    try:
        completed_users = load_completed_users()
        if user_id not in completed_users:
            completed_users.append(user_id)
            with open('completed_users.json', 'w', encoding='utf-8') as f:
                json.dump(completed_users, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存已完成使用者時發生錯誤: {e}")
        return False

def load_user_customer_mapping():
    """載入用戶與客戶的對應關係"""
    try:
        if os.path.exists('user_customer_mapping.json'):
            with open('user_customer_mapping.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"載入用戶對應關係時發生錯誤: {e}")
        return {}

def save_user_customer_mapping(user_id, customer_id):
    """保存用戶與客戶的對應關係"""
    try:
        mapping = load_user_customer_mapping()
        mapping[user_id] = customer_id
        
        with open('user_customer_mapping.json', 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"保存用戶對應關係時發生錯誤: {e}")
        return False

def load_ride_requests():
    """載入所有叫車需求"""
    try:
        if os.path.exists('ride_requests.json'):
            with open('ride_requests.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"載入叫車需求時發生錯誤: {e}")
        return {}

def save_ride_request(request_id, data):
    """保存叫車需求"""
    try:
        all_requests = load_ride_requests()
        all_requests[request_id] = {
            **data,
            'created_time': datetime.now().isoformat(),
            'status': RIDE_STATUS['PENDING']
        }
        
        with open('ride_requests.json', 'w', encoding='utf-8') as f:
            json.dump(all_requests, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"保存叫車需求時發生錯誤: {e}")
        return False

# ==================== 權限檢查函數 ====================
def is_admin(user_id):
    """檢查是否為管理員"""
    return user_id in ADMIN_USER_IDS

def has_completed_creation(user_id):
    """檢查使用者是否已完成建立"""
    if is_admin(user_id):
        return True  # 管理員視為已完成
    return user_id in load_completed_users()

def get_customer_info(user_id):
    """根據 user_id 查找客戶資料"""
    all_customers = load_customer_data()
    user_customer_mapping = load_user_customer_mapping()
    
    if user_id in user_customer_mapping:
        customer_id = user_customer_mapping[user_id]
        if customer_id in all_customers:
            return customer_id, all_customers[customer_id]
    
    return None, None

# ==================== 客戶相關函數 ====================
QUESTIONS = [
    "姓名",
    "電話",
    "收件人",
    "收件地址",
    "EZway",
    "註冊手機",
    "身分證"
]

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

# ==================== 叫車相關函數 ====================
def get_next_ride_id():
    """生成下一個叫車編號"""
    try:
        all_requests = load_ride_requests()
        if not all_requests:
            return "R001"
        
        max_num = 0
        for request_id in all_requests.keys():
            if request_id.startswith('R'):
                try:
                    num = int(request_id[1:])
                    max_num = max(max_num, num)
                except ValueError:
                    continue
        
        return f"R{max_num + 1:03d}"
    except Exception as e:
        print(f"生成叫車編號時發生錯誤: {e}")
        return f"R{len(load_ride_requests()) + 1:03d}"

def send_dispatch_notification(ride_id, ride_data):
    """發送派車通知到群組"""
    if DISPATCH_GROUP_ID == 'your_dispatch_group_id_here':
        print("警告：尚未設置派車群組 ID，跳過群組通知")
        return
        
    notification_text = f"🚨 新的叫車需求\n\n"
    notification_text += f"🚗 編號：{ride_id}\n"
    notification_text += f"👤 乘客：{ride_data['customer_name']}\n"
    notification_text += f"📱 電話：{ride_data['customer_phone']}\n"
    notification_text += f"📍 上車：{ride_data['pickup_location']}\n"
    notification_text += f"🎯 目的地：{ride_data['destination']}\n"
    notification_text += f"⏰ 時間：{ride_data['pickup_time']}\n"
    notification_text += f"👥 人數：{ride_data['passenger_count']}人\n"
    
    if ride_data.get('special_requirements'):
        notification_text += f"📝 需求：{ride_data['special_requirements']}\n"
    
    notification_text += f"\n⏱️ 需求時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    notification_text += f"\n📊 狀態：{RIDE_STATUS['PENDING']}"
    notification_text += f"\n\n請指派司機處理此需求 🚗💨"
    
    try:
        message = TextSendMessage(text=notification_text)
        line_bot_api.push_message(DISPATCH_GROUP_ID, message)
        print(f"派車通知已發送到群組: {ride_id}")
    except Exception as e:
        print(f"發送派車通知失敗: {e}")

# ==================== LINE Bot 處理函數 ====================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    source = event.source
    
    # 獲取訊息來源資訊並顯示相應的 ID
    if hasattr(source, 'type') and source.type == 'group':
        group_id = source.group_id
        print(f"群組訊息 - Group ID: {group_id}, User ID: {user_id}, 訊息: {text}")
        
        # 當管理員在群組中發送特定指令時，回覆群組 ID
        if text.lower() in ['groupid', 'group_id', '群組id', '群組編號'] and is_admin(user_id):
            message = TextSendMessage(text=f"此群組的 ID 是：\n{group_id}\n\n請將此 ID 更新到程式中的 DISPATCH_GROUP_ID")
            line_bot_api.reply_message(event.reply_token, message)
            return
            
    elif hasattr(source, 'type') and source.type == 'user':
        print(f"私人訊息 - User ID: {user_id}, 訊息: {text}")
    
    # 特殊指令：顯示 User ID
    if text.lower() in ['userid', 'user_id', 'myid', '我的id']:
        message = TextSendMessage(text=f"您的 User ID 是：\n{user_id}")
        line_bot_api.reply_message(event.reply_token, message)
        return
    
    # 初始化用戶狀態
    if user_id not in user_states:
        user_states[user_id] = {
            'mode': None,
            'question_index': 0,
            'data': {}
        }
    
    user_state = user_states[user_id]
    
    try:
        # 處理主選單命令
        if text in ['建立新客需求', '新增客戶', '建立']:
            if has_completed_creation(user_id) and not is_admin(user_id):
                message = TextSendMessage(
                    text="❌ 您已經完成新客需求建立，無法重複建立。\n\n如有問題請聯繫管理員。"
                )
                line_bot_api.reply_message(event.reply_token, message)
            else:
                start_new_customer_flow(event, user_id)
        
        # 叫車服務相關指令
        elif text in ['叫車服務', '叫車', '預約用車', '用車需求']:
            print(f"用戶 {user_id} 請求叫車服務")
            if has_completed_creation(user_id):
                print(f"用戶 {user_id} 已完成註冊，開始叫車流程")
                start_ride_booking_flow(event, user_id)
            else:
                print(f"用戶 {user_id} 尚未完成註冊")
                message = TextSendMessage(
                    text="❌ 請先完成新客需求建立後才能使用叫車服務。\n\n請選擇「建立新客需求」完成註冊。"
                )
                line_bot_api.reply_message(event.reply_token, message)
        
        # 查詢新客需求（管理員功能）
        elif text in ['查找新客需求', '查詢客戶', '查找', '搜尋'] and is_admin(user_id):
            start_search_flow(event, user_id)
        
        # 查詢叫車需求（管理員功能）
        elif text in ['查詢叫車', '叫車查詢', '派車查詢'] and is_admin(user_id):
            start_ride_search_flow(event, user_id)
        
        elif text in ['選單', 'menu', '主選單']:
            show_main_menu(event, user_id)
        
        # 處理各種狀態的回應
        elif user_state['mode'] == 'creating':
            handle_customer_creation(event, user_id, text)
        elif user_state['mode'] == 'ride_booking':
            handle_ride_booking_flow(event, user_id, user_state, text)
        elif user_state['mode'] == 'searching':
            if is_admin(user_id):
                handle_customer_search(event, user_id, text)
            else:
                message = TextSendMessage(text="❌ 您沒有權限執行此操作。")
                line_bot_api.reply_message(event.reply_token, message)
        elif user_state['mode'] == 'searching_rides':
            if is_admin(user_id):
                handle_ride_search(event, user_id, text)
            else:
                message = TextSendMessage(text="❌ 您沒有權限執行此操作。")
                line_bot_api.reply_message(event.reply_token, message)
        else:
            show_main_menu(event, user_id)
            
    except Exception as e:
        print(f"處理訊息時發生錯誤: {e}")
        error_message = TextSendMessage(text="❌ 系統發生錯誤，請稍後再試或聯繫管理員。")
        line_bot_api.reply_message(event.reply_token, error_message)

def show_main_menu(event, user_id):
    """顯示主選單"""
    is_user_admin = is_admin(user_id)
    has_completed = has_completed_creation(user_id)
    
    quick_reply_items = []
    menu_text = "歡迎使用智慧物流系統！\n\n"
    
    if is_user_admin:
        menu_text += "👨‍💼 管理員功能：\n"
        quick_reply_items.extend([
            QuickReplyButton(action=MessageAction(label="建立新客需求", text="建立新客需求")),
            QuickReplyButton(action=MessageAction(label="查找新客需求", text="查找新客需求")),
            QuickReplyButton(action=MessageAction(label="叫車服務", text="叫車服務")),
            QuickReplyButton(action=MessageAction(label="查詢叫車", text="查詢叫車"))
        ])
    else:
        if has_completed:
            menu_text += "✅ 您已完成新客需求建立\n\n可使用的服務：\n"
            quick_reply_items.append(
                QuickReplyButton(action=MessageAction(label="叫車服務", text="叫車服務"))
            )
        else:
            menu_text += "請先完成新客需求建立：\n"
            quick_reply_items.append(
                QuickReplyButton(action=MessageAction(label="建立新客需求", text="建立新客需求"))
            )
    
    if quick_reply_items:
        quick_reply = QuickReply(items=quick_reply_items)
        message = TextSendMessage(text=menu_text, quick_reply=quick_reply)
    else:
        message = TextSendMessage(text=menu_text)
    
    line_bot_api.reply_message(event.reply_token, message)

# ==================== 客戶建立流程 ====================
def start_new_customer_flow(event, user_id):
    """開始建立新客戶流程"""
    user_states[user_id] = {
        'mode': 'creating',
        'question_index': 0,
        'data': {}
    }
    ask_next_question(event, user_id)

def ask_next_question(event, user_id):
    """詢問下一個問題"""
    user_state = user_states[user_id]
    question_index = user_state['question_index']
    
    if question_index < len(QUESTIONS):
        question = QUESTIONS[question_index]
        message = TextSendMessage(text=f"請提供您的{question}：")
        line_bot_api.reply_message(event.reply_token, message)
    else:
        complete_customer_creation(event, user_id)

def handle_customer_creation(event, user_id, text):
    """處理客戶建立過程中的回答"""
    user_state = user_states[user_id]
    question_index = user_state['question_index']
    
    if question_index < len(QUESTIONS):
        question = QUESTIONS[question_index]
        user_state['data'][question] = text
        user_state['question_index'] += 1
        ask_next_question(event, user_id)

def complete_customer_creation(event, user_id):
    """完成客戶建立流程"""
    user_state = user_states[user_id]
    customer_id = get_next_customer_id()
    
    if save_customer_data(customer_id, user_state['data']):
        save_user_customer_mapping(user_id, customer_id)
        
        if not is_admin(user_id):
            save_completed_user(user_id)
        
        confirm_text = f"✅ 新客需求建立完成！\n\n客戶編號：{customer_id}\n"
        confirm_text += "=" * 20 + "\n"
        
        for question, answer in user_state['data'].items():
            confirm_text += f"{question}：{answer}\n"
        
        confirm_text += "=" * 20 + "\n"
        confirm_text += f"建立時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        if not is_admin(user_id):
            confirm_text += "\n\n🎉 恭喜！您現在可以使用叫車服務了！"
        
        user_states[user_id] = {'mode': None, 'question_index': 0, 'data': {}}
        
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="叫車服務", text="叫車服務")),
            QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
        ]
        quick_reply = QuickReply(items=quick_reply_items)
        message = TextSendMessage(text=confirm_text, quick_reply=quick_reply)
    else:
        message = TextSendMessage(text="❌ 保存資料時發生錯誤，請稍後再試。")
    
    line_bot_api.reply_message(event.reply_token, message)

# ==================== 叫車流程 ====================
def start_ride_booking_flow(event, user_id):
    """開始叫車流程"""
    customer_id, customer_info = get_customer_info(user_id)
    
    if not customer_info:
        message = TextSendMessage(
            text="❌ 找不到您的客戶資料。\n\n請先完成新客需求建立後才能使用叫車服務。"
        )
        line_bot_api.reply_message(event.reply_token, message)
        return
    
    # 初始化叫車流程
    user_states[user_id] = {
        'mode': 'ride_booking',
        'step': 'pickup_location',
        'data': {
            'customer_id': customer_id,
            'customer_name': customer_info.get('姓名', ''),
            'customer_phone': customer_info.get('電話', '')
        }
    }
    
    message = TextSendMessage(text="🚗 叫車服務\n\n請輸入上車地點：")
    line_bot_api.reply_message(event.reply_token, message)

def handle_ride_booking_flow(event, user_id, user_state, text):
    """處理叫車流程中的步驟"""
    step = user_state.get('step')
    
    # 添加調試輸出
    print(f"🚗 叫車流程 - 用戶: {user_id}, 當前步驟: {step}, 輸入: {text}")
    
    if step == 'pickup_location':
        user_state['data']['pickup_location'] = text
        user_state['step'] = 'destination'
        
        message = TextSendMessage(text="請輸入目的地：")
        line_bot_api.reply_message(event.reply_token, message)
        
    elif step == 'destination':
        user_state['data']['destination'] = text
        user_state['step'] = 'pickup_time'
        
        message = TextSendMessage(text="請輸入用車時間：\n\n例如：\n• 立即\n• 今天下午3點\n• 2025-08-16 14:30")
        line_bot_api.reply_message(event.reply_token, message)
        
    elif step == 'pickup_time':
        user_state['data']['pickup_time'] = text
        user_state['step'] = 'passenger_count'
        ask_passenger_count(event)
            
    elif step == 'passenger_count':
        try:
            # 處理特殊選項
            if text == "5人以上":
                message = TextSendMessage(text="請輸入確切的乘客人數（5-8人）：")
                line_bot_api.reply_message(event.reply_token, message)
                return
            
            passenger_count = int(text)
            if 1 <= passenger_count <= 8:
                user_state['data']['passenger_count'] = passenger_count
                user_state['step'] = 'special_requirements'
                
                message = TextSendMessage(
                    text="請輸入特殊需求（如無特殊需求請輸入「無」）：\n\n例如：\n• 需要嬰兒座椅\n• 輪椅無障礙車輛\n• 大型行李\n• 寵物運送"
                )
                line_bot_api.reply_message(event.reply_token, message)
            else:
                message = TextSendMessage(text="❌ 乘客人數請輸入 1-8 之間的數字：")
                line_bot_api.reply_message(event.reply_token, message)
        except ValueError:
            message = TextSendMessage(text="❌ 請輸入有效的數字（1-8）：")
            line_bot_api.reply_message(event.reply_token, message)
            
    elif step == 'special_requirements':
        user_state['data']['special_requirements'] = text if text != "無" else ""
        
        # 設置完成標記，避免重複處理
        user_state['step'] = 'completing'
        
        complete_ride_booking(event, user_id, user_state)

def ask_passenger_count(event):
    """詢問乘客人數"""
    quick_reply_items = [
        QuickReplyButton(action=MessageAction(label="1人", text="1")),
        QuickReplyButton(action=MessageAction(label="2人", text="2")),
        QuickReplyButton(action=MessageAction(label="3人", text="3")),
        QuickReplyButton(action=MessageAction(label="4人", text="4")),
        QuickReplyButton(action=MessageAction(label="5人以上", text="5人以上"))
    ]
    quick_reply = QuickReply(items=quick_reply_items)
    
    message = TextSendMessage(text="請選擇乘客人數：", quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

def complete_ride_booking(event, user_id, user_state):
    """完成叫車需求建立"""
    ride_id = get_next_ride_id()
    ride_data = user_state['data'].copy()
    ride_data['user_id'] = user_id
    
    if save_ride_request(ride_id, ride_data):
        # 發送確認訊息給客戶
        confirm_text = f"✅ 叫車需求已建立成功！\n\n🚗 叫車編號：{ride_id}\n"
        confirm_text += "=" * 25 + "\n"
        confirm_text += f"👤 乘客：{ride_data['customer_name']}\n"
        confirm_text += f"📱 電話：{ride_data['customer_phone']}\n"
        confirm_text += f"📍 上車地點：{ride_data['pickup_location']}\n"
        confirm_text += f"🎯 目的地：{ride_data['destination']}\n"
        confirm_text += f"⏰ 用車時間：{ride_data['pickup_time']}\n"
        confirm_text += f"👥 乘客人數：{ride_data['passenger_count']}人\n"
        
        if ride_data.get('special_requirements'):
            confirm_text += f"📝 特殊需求：{ride_data['special_requirements']}\n"
        
        confirm_text += "=" * 25 + "\n"
        confirm_text += f"📅 建立時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        confirm_text += f"📊 狀態：{RIDE_STATUS['PENDING']}\n\n"
        confirm_text += "我們已將您的叫車需求發送給派車中心，司機將會盡快與您聯繫。"
        
        # 發送派車通知到群組
        send_dispatch_notification(ride_id, ride_data)
        
        # 重置用戶狀態
        user_states[user_id] = {'mode': None, 'question_index': 0, 'data': {}}
        
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="再次叫車", text="叫車服務")),
            QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
        ]
        quick_reply = QuickReply(items=quick_reply_items)
        message = TextSendMessage(text=confirm_text, quick_reply=quick_reply)
    else:
        message = TextSendMessage(text="❌ 叫車需求建立失敗，請稍後再試。")
    
    line_bot_api.reply_message(event.reply_token, message)

# ==================== 搜尋功能 ====================
def start_search_flow(event, user_id):
    """開始搜尋客戶流程"""
    user_states[user_id] = {
        'mode': 'searching',
        'question_index': 0,
        'data': {}
    }
    
    message = TextSendMessage(
        text="🔍 請輸入要搜尋的關鍵字：\n\n"
             "可以搜尋：\n"
             "• 客戶編號（如：GT001）\n"
             "• 姓名\n"
             "• 電話號碼\n"
             "• 收件人姓名"
    )
    
    line_bot_api.reply_message(event.reply_token, message)

def start_ride_search_flow(event, user_id):
    """開始搜尋叫車流程"""
    user_states[user_id] = {
        'mode': 'searching_rides',
        'question_index': 0,
        'data': {}
    }
    
    message = TextSendMessage(
        text="🔍 請輸入要搜尋的叫車資訊：\n\n"
             "可以搜尋：\n"
             "• 叫車編號（如：R001）\n"
             "• 乘客姓名\n"
             "• 乘客電話號碼"
    )
    
    line_bot_api.reply_message(event.reply_token, message)

def search_customer(query):
    """搜尋客戶資料"""
    all_customers = load_customer_data()
    results = []
    
    for customer_id, data in all_customers.items():
        # 搜尋條件：姓名、電話、收件人、編號
        if (query.lower() in data.get('姓名', '').lower() or
            query in data.get('電話', '') or
            query.lower() in data.get('收件人', '').lower() or
            query.upper() in customer_id.upper()):
            results.append((customer_id, data))
    
    return results

def search_ride_request(query):
    """搜尋叫車需求"""
    all_requests = load_ride_requests()
    results = []
    
    for ride_id, data in all_requests.items():
        if (query.upper() in ride_id.upper() or
            query in data.get('customer_phone', '') or
            query.lower() in data.get('customer_name', '').lower()):
            results.append((ride_id, data))
    
    return results

def handle_customer_search(event, user_id, text):
    """處理客戶搜尋"""
    results = search_customer(text)
    
    if results:
        if len(results) == 1:
            # 只有一個結果，直接顯示詳細資訊
            customer_id, data = results[0]
            show_customer_detail(event, customer_id, data)
        else:
            # 多個結果，顯示列表
            show_search_results(event, results, text)
    else:
        message = TextSendMessage(
            text=f"❌ 找不到與 '{text}' 相關的客戶資料。\n\n請檢查輸入是否正確，或嘗試其他關鍵字。"
        )
        line_bot_api.reply_message(event.reply_token, message)
    
    # 重置搜尋狀態
    user_states[user_id]['mode'] = None

def handle_ride_search(event, user_id, text):
    """處理叫車需求搜尋"""
    results = search_ride_request(text)
    
    if results:
        if len(results) == 1:
            # 只有一個結果，直接顯示詳細資訊
            ride_id, data = results[0]
            show_ride_detail(event, ride_id, data)
        else:
            # 多個結果，顯示列表
            show_ride_search_results(event, results, text)
    else:
        message = TextSendMessage(
            text=f"❌ 找不到與 '{text}' 相關的叫車需求。\n\n請檢查輸入是否正確，或嘗試其他關鍵字。"
        )
        line_bot_api.reply_message(event.reply_token, message)
    
    # 重置搜尋狀態
    user_states[user_id]['mode'] = None

def show_customer_detail(event, customer_id, data):
    """顯示客戶詳細資訊"""
    detail_text = f"📋 客戶詳細資訊\n\n"
    detail_text += f"客戶編號：{customer_id}\n"
    detail_text += "=" * 20 + "\n"
    
    for question in QUESTIONS:
        if question in data:
            detail_text += f"{question}：{data[question]}\n"
    
    if 'created_time' in data:
        created_time = datetime.fromisoformat(data['created_time'])
        detail_text += "=" * 20 + "\n"
        detail_text += f"建立時間：{created_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="繼續搜尋", text="查找新客需求")),
        QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
    ])
    
    message = TextSendMessage(text=detail_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

def show_search_results(event, results, query):
    """顯示搜尋結果列表"""
    result_text = f"🔍 搜尋結果 (關鍵字：{query})\n"
    result_text += f"共找到 {len(results)} 筆資料：\n\n"
    
    for i, (customer_id, data) in enumerate(results[:10], 1):  # 最多顯示10筆
        result_text += f"{i}. {customer_id}\n"
        result_text += f"   姓名：{data.get('姓名', 'N/A')}\n"
        result_text += f"   電話：{data.get('電話', 'N/A')}\n"
        result_text += f"   收件人：{data.get('收件人', 'N/A')}\n"
        result_text += "-" * 15 + "\n"
    
    if len(results) > 10:
        result_text += f"... 還有 {len(results) - 10} 筆資料\n"
    
    result_text += "\n💡 請輸入更具體的關鍵字以縮小搜尋範圍"
    
    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="繼續搜尋", text="查找新客需求")),
        QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
    ])
    
    message = TextSendMessage(text=result_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

def show_ride_detail(event, ride_id, data):
    """顯示叫車詳細資訊"""
    detail_text = f"🚗 叫車需求詳細資訊\n\n"
    detail_text += f"編號：{ride_id}\n"
    detail_text += "=" * 25 + "\n"
    detail_text += f"👤 乘客：{data.get('customer_name', 'N/A')}\n"
    detail_text += f"📱 電話：{data.get('customer_phone', 'N/A')}\n"
    detail_text += f"📍 上車地點：{data.get('pickup_location', 'N/A')}\n"
    detail_text += f"🎯 目的地：{data.get('destination', 'N/A')}\n"
    detail_text += f"⏰ 用車時間：{data.get('pickup_time', 'N/A')}\n"
    detail_text += f"👥 乘客人數：{data.get('passenger_count', 'N/A')}人\n"
    
    if data.get('special_requirements'):
        detail_text += f"📝 特殊需求：{data['special_requirements']}\n"
    
    detail_text += f"📊 狀態：{data.get('status', RIDE_STATUS['PENDING'])}\n"
    
    if data.get('driver_name'):
        detail_text += f"🚙 指派司機：{data['driver_name']}\n"
    if data.get('driver_phone'):
        detail_text += f"📞 司機電話：{data['driver_phone']}\n"
    
    if 'created_time' in data:
        created_time = datetime.fromisoformat(data['created_time'])
        detail_text += "=" * 25 + "\n"
        detail_text += f"建立時間：{created_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="繼續搜尋", text="查詢叫車")),
        QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
    ])
    
    message = TextSendMessage(text=detail_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

def show_ride_search_results(event, results, query):
    """顯示叫車搜尋結果列表"""
    result_text = f"🔍 叫車需求搜尋結果 (關鍵字：{query})\n"
    result_text += f"共找到 {len(results)} 筆資料：\n\n"
    
    for i, (ride_id, data) in enumerate(results[:10], 1):  # 最多顯示10筆
        result_text += f"{i}. {ride_id}\n"
        result_text += f"   乘客：{data.get('customer_name', 'N/A')}\n"
        result_text += f"   電話：{data.get('customer_phone', 'N/A')}\n"
        result_text += f"   狀態：{data.get('status', RIDE_STATUS['PENDING'])}\n"
        result_text += f"   時間：{data.get('pickup_time', 'N/A')}\n"
        result_text += "-" * 20 + "\n"
    
    if len(results) > 10:
        result_text += f"... 還有 {len(results) - 10} 筆資料\n"
    
    result_text += "\n💡 請輸入更具體的關鍵字以縮小搜尋範圍"
    
    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="繼續搜尋", text="查詢叫車")),
        QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
    ])
    
    message = TextSendMessage(text=result_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

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
    
    print("LINE Bot 智慧物流系統啟動中...")
    print(f"當前客戶編號計數器：GT{customer_counter:03d}")
    print("功能包含：")
    print("- 新客需求建立")
    print("- 叫車服務（簡化流程）")
    print("- 派車通知")
    print("- 管理員查詢功能")
    print(f"- 派車群組 ID: {DISPATCH_GROUP_ID}")
    
    if DISPATCH_GROUP_ID == 'your_dispatch_group_id_here':
        print("⚠️  警告：尚未設置派車群組 ID，派車通知功能將無法使用")
        print("   請按照以下步驟設置：")
        print("   1. 將 Bot 加入派車群組")
        print("   2. 在群組中發送 'groupid' 指令")
        print("   3. 複製群組 ID 並更新程式中的 DISPATCH_GROUP_ID")
    else:
        print("✅ 派車群組已設置完成")
    
    app.run(host='0.0.0.0', port=6000, debug=True)