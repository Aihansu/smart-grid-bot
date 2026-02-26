import urllib.request
import urllib.parse
import json
import config

def send_telegram(message, reply_markup=None):
    """Send a Telegram message (with optional keyboard)"""
    if not config.TELEGRAM_ENABLED or not config.TELEGRAM_TOKEN:
        return
    
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': config.TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        if reply_markup:
            payload['reply_markup'] = json.dumps(reply_markup)
            
        data = urllib.parse.urlencode(payload).encode('utf-8')
        
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_telegram_updates(offset=None, timeout=1):
    """Fetch Telegram messages"""
    if not config.TELEGRAM_ENABLED or not config.TELEGRAM_TOKEN:
        return []
    
    try:
        params = {'timeout': timeout}
        if offset:
            params['offset'] = offset
        
        query_string = urllib.parse.urlencode(params)
        url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/getUpdates?{query_string}"
        
        req = urllib.request.Request(url)
        response = urllib.request.urlopen(req, timeout=timeout+5)
        result = json.loads(response.read().decode('utf-8'))
        
        if result.get('ok'):
            return result.get('result', [])
    except Exception as e:
        pass
    
    return []

def get_main_keyboard():
    """Main menu buttons"""
    return {
        'keyboard': [
            [{'text': '/status'}, {'text': '/positions'}],
            [{'text': '/stats'}, {'text': '/grids'}],
            [{'text': '/help'}]
        ],
        'resize_keyboard': True,
        'one_time_keyboard': False
    }
