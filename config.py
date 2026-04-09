import os
import sys

def load_env_file():
    """Manual .env file reader (no python-dotenv required)"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

    if not os.path.exists(env_path):
        print(f"\033[91m❌ ERROR: .env file not found!\033[0m")
        print(f"\033[93m   Copy .env.example to .env:\033[0m")
        print(f"\033[96m   cp .env.example .env\033[0m")
        print(f"\033[93m   Then fill in your API credentials.\033[0m")
        sys.exit(1)

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Load .env file
load_env_file()

# API Credentials
API_KEY = os.environ.get('BINANCE_API_KEY', '')
API_SECRET = os.environ.get('BINANCE_API_SECRET', '')

# Telegram Settings
TELEGRAM_ENABLED = True
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

# Trading Settings
SYMBOL = os.environ.get('SYMBOL', 'ETH/USDT')
INVESTMENT = 1000                # Total investment in USDT
GRID_COUNT = int(os.environ.get('GRID_COUNT', '10'))
GRID_SPREAD = 0.025              # 2.5% grid spacing

# DCA Mode - Stop Loss Disabled
STOP_LOSS_ENABLED = False
STOP_LOSS_PCT = 100

TRAILING_PROFIT_PCT = 1.2        # Trailing starts at 1.2% profit
TRAILING_CALLBACK_PCT = 0.3      # Sell when price drops 0.3% from peak

HYBRID_MODE = True
EMA_PERIOD = 30

# EMA Dynamic Buy Zones
EMA_ZONE_WEAK = -1.5         # 0% to -1.5%: weak signal (0.75x)
EMA_ZONE_NORMAL = -3.0       # -1.5% to -3%: normal signal (1x)
EMA_ZONE_STRONG = -5.0       # -3% to -5%: strong dip (1.5x)
EMA_ZONE_EXPENSIVE = 5.0     # 5%+ above EMA: too expensive, don't buy
EMA_ABOVE_MULTIPLIER = 0.5   # Above EMA: expensive, buy less
EMA_WEAK_MULTIPLIER = 0.75   # Slight dip: buy a bit more
EMA_NORMAL_MULTIPLIER = 1.0  # Normal dip: standard buy
EMA_STRONG_MULTIPLIER = 1.5  # Strong dip: buy aggressively

# Auto Grid Reset
AUTO_GRID_RESET = True
GRID_OUT_OF_RANGE_PCT = 2

PAPER_TRADING = True             # Start with paper trading! Set to False for real trading
CHECK_INTERVAL = 30
GRID_UPDATE_INTERVAL = 3600

SHOW_GRID_TABLE = True
COMPACT_MODE = False

# Advanced Features
AUTO_COMPOUND = True             # Automatically increase grid amounts as profits grow
DAILY_REPORT_ENABLED = True      # Send daily summary report via Telegram
ENABLE_REBALANCING = True        # When cash drops below $50, sell top losing position to buy lower
REBALANCING_MIN_DISTANCE_PCT = 2.0  # Minimum 2% price drop from last buy to trigger rebalancing
MIN_CASH_BEFORE_REBALANCING = 50.0  # Swap triggers when cash drops below this amount (no position limit)
