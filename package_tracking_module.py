# package_tracking_module.py
# 貨品追蹤模組

import requests
import json
from datetime import datetime
from linebot.models import TextSendMessage, QuickReply, QuickReplyButton, MessageAction
from bs4 import BeautifulSoup
import re

# 安利物流追蹤API
TRACKING_BASE_URL = "http://220.130.163.195:8060/track/home/dlvstatus"

def start_package_tracking_flow(event, user_id, line_bot_api):
    """開始貨品追蹤流程"""
    message = TextSendMessage(
        text="📦 貨品狀態查詢\n\n請輸入您的追蹤單號：\n\n例如：\n• 客戶提單號\n• 託運單號\n\n請輸入完整的單號進行查詢"
    )
    line_bot_api.reply_message(event.reply_token, message)
    
    return {
        'mode': 'package_tracking',
        'step': 'tracking_number',
        'data': {}
    }

def handle_package_tracking_flow(event, user_id, user_state, text, line_bot_api):
    """處理貨品追蹤流程"""
    step = user_state.get('step')
    
    print(f"📦 追蹤流程 - 用戶: {user_id}, 當前步驟: {step}, 輸入: {text}")
    
    if step == 'tracking_number':
        # 清理輸入的追蹤號碼
        tracking_number = text.strip()
        
        if not tracking_number:
            message = TextSendMessage(text="❌ 請輸入有效的追蹤單號")
            line_bot_api.reply_message(event.reply_token, message)
            return
        
        # 進行追蹤查詢
        tracking_result = query_package_tracking(tracking_number)
        
        if tracking_result['success']:
            # 顯示追蹤結果
            show_tracking_result(event, tracking_number, tracking_result, line_bot_api)
        else:
            # 顯示錯誤訊息
            show_tracking_error(event, tracking_number, tracking_result['error'], line_bot_api)
        
        # 完成追蹤流程
        user_state['step'] = 'completed'

def query_package_tracking(tracking_number):
    """查詢包裹追蹤狀態"""
    try:
        # 準備請求參數
        params = {
            'trackingNo': tracking_number
        }
        
        # 設置請求標頭
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        print(f"正在查詢追蹤號: {tracking_number}")
        
        # 發送GET請求
        response = requests.get(
            TRACKING_BASE_URL,
            params=params,
            headers=headers,
            timeout=10,
            verify=False  # 如果SSL證書有問題可以設為False
        )
        
        print(f"請求URL: {response.url}")
        print(f"響應狀態碼: {response.status_code}")
        
        if response.status_code == 200:
            # 解析HTML響應
            return parse_tracking_response(response.text, tracking_number)
        else:
            return {
                'success': False,
                'error': f'伺服器響應錯誤：HTTP {response.status_code}'
            }
            
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': '查詢超時，請稍後再試'
        }
    except requests.exceptions.ConnectionError:
        return {
            'success': False,
            'error': '連線失敗，請檢查網路連線或稍後再試'
        }
    except Exception as e:
        print(f"追蹤查詢錯誤: {str(e)}")
        return {
            'success': False,
            'error': f'查詢時發生錯誤：{str(e)}'
        }

def parse_tracking_response(html_content, tracking_number):
    """解析追蹤響應HTML"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 檢查是否有查無資料的情況
        error_indicators = [
            '查無資料', '無此單號', '單號不存在', 'not found', 'no data',
            '錯誤', 'error', '無法查詢', '查詢不到'
        ]
        
        page_text = soup.get_text().lower()
        for indicator in error_indicators:
            if indicator.lower() in page_text:
                return {
                    'success': False,
                    'error': f'追蹤單號 {tracking_number} 查無資料，請確認單號是否正確'
                }
        
        # 提取基本資訊
        basic_info = {}
        
        # 查找客戶提單號、收件人、收件地址等基本信息
        info_patterns = {
            '客戶提單號': ['客戶提單號', '提單號'],
            '收件人': ['收件人'],
            '收件人地址': ['收件人地址', '收件地址'],
            '總件數': ['總件數', '件數'],
            '代收金額': ['代收金額', '金額']
        }
        
        # 查找表格中的基本資訊
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    
                    for info_key, patterns in info_patterns.items():
                        if any(pattern in key for pattern in patterns):
                            basic_info[info_key] = value
                            break
        
        # 提取貨件歷程（物流追蹤記錄）
        tracking_history = []
        
        # 查找貨件歷程表格
        history_found = False
        for table in tables:
            # 檢查表頭是否包含歷程相關關鍵字
            headers = table.find_all('th')
            header_text = ' '.join([th.get_text(strip=True) for th in headers])
            
            if any(keyword in header_text for keyword in ['貨況', '時間', '站所', '歷程', '狀態']):
                history_found = True
                rows = table.find_all('tr')[1:]  # 跳過表頭
                
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:  # 至少要有3欄數據
                        row_data = []
                        for cell in cells:
                            cell_text = cell.get_text(strip=True)
                            if cell_text:  # 只添加非空內容
                                row_data.append(cell_text)
                        
                        if len(row_data) >= 3:  # 確保有足夠的數據
                            tracking_history.append(row_data)
                break
        
        # 如果沒有找到標準的歷程表格，嘗試查找其他格式
        if not history_found:
            # 查找所有表格中可能的追蹤記錄
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 4:  # 檢查是否有足夠的欄位
                        row_data = [cell.get_text(strip=True) for cell in cells]
                        # 檢查是否包含時間格式 (YYYY-MM-DD 或類似)
                        if any(re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', text) for text in row_data):
                            tracking_history.append(row_data)
        
        # 整理結果
        if basic_info or tracking_history:
            return {
                'success': True,
                'tracking_number': tracking_number,
                'basic_info': basic_info,
                'tracking_history': tracking_history,
                'query_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        else:
            # 如果沒有找到結構化數據，返回頁面主要內容
            main_content = soup.find('body')
            if main_content:
                content_text = main_content.get_text(strip=True)
                content_lines = [line.strip() for line in content_text.split('\n') if line.strip() and len(line.strip()) > 5]
                
                return {
                    'success': True,
                    'tracking_number': tracking_number,
                    'basic_info': {'說明': '查詢成功，但資料格式特殊'},
                    'tracking_history': [content_lines[:10]],  # 取前10行有意義的內容
                    'query_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            else:
                return {
                    'success': False,
                    'error': '無法解析追蹤結果，請稍後再試'
                }
                
    except Exception as e:
        print(f"解析HTML錯誤: {str(e)}")
        return {
            'success': False,
            'error': f'解析追蹤結果時發生錯誤：{str(e)}'
        }

def show_tracking_result(event, tracking_number, result, line_bot_api):
    """顯示追蹤結果"""
    result_text = f"📦 貨品追蹤結果\n\n"
    result_text += f"📋 追蹤單號：{tracking_number}\n"
    result_text += f"🕐 查詢時間：{result['query_time']}\n"
    result_text += "=" * 30 + "\n\n"
    
    # 顯示基本資訊
    basic_info = result.get('basic_info', {})
    if basic_info:
        result_text += "📋 基本資訊：\n"
        for key, value in basic_info.items():
            if value:  # 只顯示有值的項目
                result_text += f"• {key}：{value}\n"
        result_text += "\n"
    
    # 顯示追蹤歷程
    tracking_history = result.get('tracking_history', [])
    if tracking_history:
        result_text += "📍 貨件歷程：\n\n"
        
        for i, record in enumerate(tracking_history[:8], 1):  # 最多顯示8條記錄
            if isinstance(record, list):
                if len(record) >= 4:
                    # 標準格式：子提單號、貨況、貨況時間、站所
                    status = record[1] if len(record) > 1 else ''
                    time = record[2] if len(record) > 2 else ''
                    location = record[3] if len(record) > 3 else ''
                    
                    result_text += f"{i}. {status}\n"
                    if time:
                        result_text += f"   時間：{time}\n"
                    if location:
                        result_text += f"   地點：{location}\n"
                    result_text += "\n"
                else:
                    # 簡化格式
                    record_text = " | ".join(str(item) for item in record if str(item).strip())
                    if record_text.strip():
                        result_text += f"{i}. {record_text}\n"
            else:
                record_text = str(record)
                if record_text.strip():
                    result_text += f"{i}. {record_text}\n"
        
        if len(tracking_history) > 8:
            result_text += f"... 還有 {len(tracking_history) - 8} 筆記錄\n"
    else:
        result_text += "📍 目前查詢到基本資訊，詳細追蹤記錄請稍後再查詢\n"
    
    result_text += "\n" + "=" * 30 + "\n"
    result_text += "💡 提示：如需更詳細資訊，請聯繫客服\n"
    result_text += "📞 客服電話：(886-2) 2711-0758"
    
    quick_reply_items = [
        QuickReplyButton(action=MessageAction(label="再次查詢", text="貨品追蹤")),
        QuickReplyButton(action=MessageAction(label="叫車服務", text="叫車服務")),
        QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
    ]
    quick_reply = QuickReply(items=quick_reply_items)
    
    message = TextSendMessage(text=result_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

def show_tracking_error(event, tracking_number, error_message, line_bot_api):
    """顯示追蹤錯誤"""
    error_text = f"❌ 貨品追蹤查詢失敗\n\n"
    error_text += f"📋 追蹤單號：{tracking_number}\n"
    error_text += f"❗ 錯誤原因：{error_message}\n\n"
    error_text += "🔍 請檢查：\n"
    error_text += "• 單號是否輸入正確\n"
    error_text += "• 是否為有效的追蹤單號\n"
    error_text += "• 貨品是否已開始運送\n\n"
    error_text += "💡 如有疑問，請聯繫客服人員協助查詢"
    
    quick_reply_items = [
        QuickReplyButton(action=MessageAction(label="重新查詢", text="貨品追蹤")),
        QuickReplyButton(action=MessageAction(label="叫車服務", text="叫車服務")),
        QuickReplyButton(action=MessageAction(label="主選單", text="主選單"))
    ]
    quick_reply = QuickReply(items=quick_reply_items)
    
    message = TextSendMessage(text=error_text, quick_reply=quick_reply)
    line_bot_api.reply_message(event.reply_token, message)

def get_tracking_history(tracking_number, limit=10):
    """獲取追蹤歷史記錄（可擴展功能）"""
    # 這個函數可以用來保存和檢索追蹤歷史
    # 暫時返回空列表，將來可以實現數據庫存儲
    return []

def save_tracking_query(user_id, tracking_number, result):
    """保存追蹤查詢記錄（可擴展功能）"""
    try:
        query_record = {
            'user_id': user_id,
            'tracking_number': tracking_number,
            'query_time': datetime.now().isoformat(),
            'success': result.get('success', False),
            'result': result
        }
        
        # 這裡可以保存到文件或數據庫
        # 暫時只打印到控制台
        print(f"追蹤查詢記錄: {query_record}")
        
        return True
    except Exception as e:
        print(f"保存追蹤記錄失敗: {e}")
        return False

# 測試函數
def test_tracking_query(tracking_number="TEST123"):
    """測試追蹤查詢功能"""
    print(f"測試追蹤查詢: {tracking_number}")
    result = query_package_tracking(tracking_number)
    print(f"查詢結果: {result}")
    return result

if __name__ == "__main__":
    # 測試模組
    print("📦 貨品追蹤模組測試")
    test_result = test_tracking_query()
    print("測試完成")