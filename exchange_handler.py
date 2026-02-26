import ccxt
import config
import telegram_handler
from utils import Colors

class ExchangeHandler:
    def __init__(self):
        self.exchange = ccxt.binance({
            'apiKey': config.API_KEY,
            'secret': config.API_SECRET,
            'enableRateLimit': True,
        })
        
    def get_current_price(self, symbol):
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            print(Colors.error(f'❌ Failed to fetch price ({symbol}): ' + str(e)))
            return None
            
    def get_balance(self, asset='USDT'):
        try:
            balance = self.exchange.fetch_balance()
            return balance.get('free', {}).get(asset, 0.0)
        except Exception as e:
            print(Colors.error(f'❌ Failed to fetch balance ({asset}): ' + str(e)))
            return 0.0

    def place_order(self, symbol, side, amount, type='market', price=None):
        """Submit a real order"""
        try:
            if type == 'market':
                return self.exchange.create_order(symbol, type, side, amount)
            else:
                return self.exchange.create_order(symbol, type, side, amount, price)
        except Exception as e:
            print(Colors.error(f'❌ Failed to submit order ({side} {amount} {symbol}): ' + str(e)))
            telegram_handler.send_telegram(f"🚨 <b>ORDER ERROR!</b>\n{side.upper()} {amount} {symbol}\n Error: {str(e)}")
            return None

    def fetch_my_trades(self, symbol, limit=500):
        """Fetch real trade history from Binance"""
        try:
            return self.exchange.fetch_my_trades(symbol, limit=limit)
        except Exception as e:
            print(Colors.error(f'❌ Failed to fetch trade history: {e}'))
            return []

    def fetch_all_my_trades(self, symbol):
        """Fetch ALL trade history from Binance (with pagination)"""
        try:
            all_trades = []
            since = None
            while True:
                trades = self.exchange.fetch_my_trades(symbol, since=since, limit=1000)
                if not trades:
                    break
                all_trades.extend(trades)
                # Continue from 1ms after the last trade's timestamp
                last_ts = trades[-1]['timestamp']
                if since == last_ts + 1:
                    break  # Prevent infinite loop
                since = last_ts + 1
                if len(trades) < 1000:
                    break  # Last page, no more trades
            return all_trades
        except Exception as e:
            print(Colors.error(f'❌ Failed to fetch trade history: {e}'))
            return []

    def fetch_ohlcv(self, symbol, timeframe='1h', limit=100):
        try:
            return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except Exception as e:
            print(Colors.warning(f'⚠️ Failed to load historical data: {e}'))
            return []
