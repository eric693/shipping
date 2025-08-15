# ride_booking_module.py
# 叫車需求處理模組

import json
import os
from datetime import datetime
from linebot.models import (
    TextSendMessage, QuickReply, QuickReplyButton, 
    MessageAction, LocationSendMessage
)

# 派車群組 ID (請替換為實際的群組 ID)
# 獲取方式：
# 1. 將 Bot 加入派車群組
# 2. 讓管理員在群組中發送 "groupid" 或 "群組id"
# 3. Bot 會回覆群組 ID，複製並貼上到下面
DISPATCH_GROUP_ID = 'C336c58b3f698fffbe565c256589f193f'  # 請替換為實際的群組 ID

# 如果您已經知道群組 ID，請直接替換上面的字串
# 例如：DISPATCH_GROUP_ID = 'Cxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# 叫車狀態常數
RIDE_STATUS = {
    'PENDING': '等待派車',
    'ASSIGNED': '已指派司機',
    'PICKED_UP': '已接客',
    'COMPLETED': '行程完成',
    'CANCELLED': '已取消'
}

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

def get_next_ride_id():
    """生成下一個叫車編號"""
    try:
        all_requests = load_ride_requests()
        if not all_requests:
            return "R001"
        
        # 找出最大編號
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

def get_customer_info(user_id, customer_data_func):
    """根據 user_id 查找客戶資料"""
    # 這裡需要從主系統獲取客戶資料
    # 假設有一個函數可以根據 user_id 找到對應的客戶資料
    all_customers = customer_data_func()
    
    # 由於原系統沒有儲存 user_id 對應關係，這裡需要額外的對應表
    # 建議在完成客戶建立時同時記錄 user_id 對應關係
    user_customer_mapping = load_user_customer_mapping()
    
    if user_id in user_customer_mapping:
        customer_id = user_customer_mapping[user_id]
        if customer_id in all_customers:
            return customer_id, all_customers[customer_id]
    
    return None, None

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

def start_ride_booking_flow(event, user_id, line_bot_api, customer_data_func):
    """開始叫車流程"""
    # 檢查客戶是否已完成建立
    customer_id, customer_info = get_customer_info(user_id, customer_data_func)
    
    if not customer_info:
        message = TextSendMessage(
            text="❌ 找不到您的客戶資料。\n\n請先完成新客需求建立後才能使用叫車服務。"
        )
        line_bot_api.reply_message(event.reply_token, message)
        return False
    
    # 初始化叫車流程
    return {
        'mode': 'ride_booking',
        'step': 'pickup_location',
        'data': {
            'customer_id': customer_id,
            'customer_name': customer_info.get('姓名', ''),
            'customer_phone': customer_info.get('電話', '')
        }
    }

def handle_ride_booking_flow(event, user_id, user_state, text, line_bot_api):
    """處理叫車流程中的步驟"""
    step = user_state.get('step')
    
    if step == 'pickup_location':
        # 收集上車地點
        user_state['data']['pickup_location'] = text
        user_state['step'] = 'destination'
        
        message = TextSendMessage(text="請輸入目的地：")
        line_bot_api.reply_message(event.reply_token, message)
        
    elif step == 'destination':
        # 收集目的地
        user_state['data']['destination'] = text
        user_state['step'] = 'pickup_time'
        
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="立即用車", text="立即用車")),
            QuickReplyButton(action=MessageAction(label="預約用車", text="預約用車"))
        ]
        quick_reply = QuickReply(items=quick_reply_items)
        
        message = TextSendMessage(
            text="請選擇用車時間：", 
            quick_reply=quick_reply
        )
        line_bot_api.reply_message(event.reply_token, message)
        
    elif step == 'pickup_time':
        if text == "立即用車":
            user_state['data']['pickup_time'] = "立即"
            user_state['step'] = 'passenger_count'
        elif text == "預約用車":
            user_state['step'] = 'scheduled_time'
            message = TextSendMessage(text="請輸入預約時間（格式：YYYY-MM-DD HH:MM）：")
            line_bot_api.reply_message(event.reply_token, message)
            return
        else:
            message = TextSendMessage(text="請選擇「立即用車」或「預約用車」。")
            line_bot_api.reply_message(event.reply_token, message)
            return
            
        # 詢問乘客人數
        ask_passenger_count(event, line_bot_api)
        
    elif step == 'scheduled_time':
        # 處理預約時間
        try:
            # 簡單驗證時間格式
            datetime.strptime(text, '%Y-%m-%d %H:%M')
            user_state['data']['pickup_time'] = text
            user_state['step'] = 'passenger_count'
            ask_passenger_count(event, line_bot_api)
        except ValueError:
            message = TextSendMessage(text="時間格式不正確，請重新輸入（格式：YYYY-MM-DD HH:MM）：")
            line_bot_api.reply_message(event.reply_token, message)
            
    elif step == 'passenger_count':
        try:
            passenger_count = int(text)
            if 1 <= passenger_count <= 8:
                user_state['data']['passenger_count'] = passenger_count
                user_state['step'] = 'special_requirements'
                
                message = TextSendMessage(
                    text="請輸入特殊需求（如無特殊需求請輸入「無」）：\n\n"
                         "例如：\n"
                         "• 需要嬰兒座椅\n"
                         "• 輪椅無障礙車輛\n"
                         "• 大型行李\n"
                         "• 寵物運送"
                )
                line_bot_api.reply_message(event.reply_token, message)
            else:
                message = TextSendMessage(text="乘客人數請輸入 1-8 之間的數字：")
                line_bot_api.reply_message(event.reply_token, message)
        except ValueError:
            message = TextSendMessage(text="請輸入有效的乘客人數（1-8）：")
            line_bot_api.reply_message(event.reply_token, message)
            
    elif step == 'special_requirements':
        user_state['data']['special_requirements'] = text if text != "無" else ""
        
        # 完成叫車需求建立
        complete_ride_booking(event, user_id, user_state, line_bot_api)

def ask_passenger_count(event, line_bot_api):
    """詢問乘客人數"""
    quick_reply_items = [
        QuickReplyButton(action=MessageAction(label="1人", text="1")),
        QuickReplyButton(action=MessageAction(label="2人", text="2")),
        QuickReplyButton(action=MessageAction(label="3人", text="3")),
        QuickReplyButton(action=MessageAction(label="4人", text="4")),
        QuickReplyButton(action=MessageAction(label="5人以上", text="5人以上"))
    ]
    quick_reply = QuickReply(items=quick_reply_items)
    
    message = TextSendMessage(
        text="請選擇乘客人數：", 
        quick_reply=quick_reply
    )
    line_bot_api.reply_message(event.reply_token, message)

def complete_ride_booking(event, user_id, user_state, line_bot_api):
    """完成叫車需求建立"""
    ride_id = get_next_ride_id()
    ride_data = user_state['data'].copy()
    ride_data['user_id'] = user_id
    
    # 保存叫車需求
    if save_ride_request(ride_id, ride_data):
        # 發送確認訊息給客戶
        send_booking_confirmation(event, ride_id, ride_data, line_bot_api)
        
        # 發送派車通知到群組
        send_dispatch_notification(ride_id, ride_data, line_bot_api)
        
        return True
    else:
        message = TextSendMessage(text="❌ 叫車需求建立失敗，請稍後再試。")
        line_bot_api.reply_message(event.reply_token, message)
        return False

def send_booking_confirmation(event, ride_id, ride_data, line_bot_api):
    """發送叫車確認訊息給客戶"""
    confirm_text = f"✅ 叫車需求已建立成功！\n\n"
    confirm_text += f"🚗 叫車編號：{ride_id}\n"
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
    confirm_text += "我們已將您的叫車需求發送給派車中心，\n"
    confirm_text += "司機將會盡快與您聯繫。\n\n"
    confirm_text += "如需查詢或取消，請記住您的叫車編號。"
    
    quick_reply_items = [
        QuickReplyButton(action=MessageAction(label="查詢叫車狀態", text=f"查詢 {ride_id}")),
        QuickReplyButton(action=MessageAction(label="再次叫車", text="叫車服務")),
        QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
    ]
    quick_reply = QuickReply(items=quick_reply_items)
    
    message = TextSendMessage(text=confirm_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

def send_dispatch_notification(ride_id, ride_data, line_bot_api):
    """發送派車通知到群組"""
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

def get_ride_status_text(ride_id):
    """獲取叫車狀態文字"""
    all_requests = load_ride_requests()
    
    if ride_id not in all_requests:
        return "❌ 找不到該叫車需求編號。"
    
    ride_data = all_requests[ride_id]
    
    status_text = f"🚗 叫車狀態查詢\n\n"
    status_text += f"編號：{ride_id}\n"
    status_text += f"乘客：{ride_data['customer_name']}\n"
    status_text += f"上車地點：{ride_data['pickup_location']}\n"
    status_text += f"目的地：{ride_data['destination']}\n"
    status_text += f"用車時間：{ride_data['pickup_time']}\n"
    status_text += f"當前狀態：{ride_data.get('status', RIDE_STATUS['PENDING'])}\n"
    
    if 'driver_name' in ride_data:
        status_text += f"指派司機：{ride_data['driver_name']}\n"
    if 'driver_phone' in ride_data:
        status_text += f"司機電話：{ride_data['driver_phone']}\n"
    
    created_time = datetime.fromisoformat(ride_data['created_time'])
    status_text += f"建立時間：{created_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    return status_text

def update_ride_status(ride_id, new_status, driver_name=None, driver_phone=None):
    """更新叫車狀態（管理員功能）"""
    try:
        all_requests = load_ride_requests()
        
        if ride_id not in all_requests:
            return False, "找不到該叫車需求"
        
        all_requests[ride_id]['status'] = new_status
        all_requests[ride_id]['updated_time'] = datetime.now().isoformat()
        
        if driver_name:
            all_requests[ride_id]['driver_name'] = driver_name
        if driver_phone:
            all_requests[ride_id]['driver_phone'] = driver_phone
        
        with open('ride_requests.json', 'w', encoding='utf-8') as f:
            json.dump(all_requests, f, ensure_ascii=False, indent=2)
        
        return True, "狀態更新成功"
    
    except Exception as e:
        return False, f"更新失敗: {str(e)}"