# Smart Grid Bot v3.0

A fully automated **grid trading bot** for Binance with DCA strategy, trailing stop-loss, and EMA-based dynamic buy zones. Runs 24/7 and is fully controlled via Telegram.

---

## Features

| Feature | Description |
|---------|-------------|
| **Grid Trading** | Creates 10 grid levels across a dynamic price range and buys the dips |
| **Trailing Stop** | Locks profit automatically — activates at +1.2%, sells on -0.3% pullback |
| **EMA Dynamic Buy Zones** | Adjusts buy amounts based on distance from EMA — buy less when expensive, buy more on deep dips |
| **DCA Mode** | No stop loss — accumulates positions on dips for long-term gains |
| **Auto Compound** | Reinvests realized profits into larger grid amounts |
| **Auto Grid Reset** | Regenerates grids when price moves out of range |
| **Orphan System** | Old positions continue trading independently after grid reset |
| **Rebalancing** | When cash drops below $50, sells the top losing position to buy lower |
| **BNB Auto-Buy** | Automatically purchases BNB when balance is low to maintain fee discounts |
| **Daily Reports** | Sends daily P/L summary via Telegram |
| **Paper Trading** | Test the bot risk-free before going live |

---

## EMA Dynamic Buy Zones

The bot adjusts buy amounts based on how far the price has dropped from the EMA (Exponential Moving Average):

| Zone | EMA Distance | Multiplier | Meaning |
|------|-------------|------------|---------|
| Above EMA | > 0% | 0.5x | Price is expensive, buy less |
| Weak Dip | 0% to -0.7% | 0.75x | Small dip, conserve capital |
| Normal Dip | -0.7% to -1.3% | 1.0x | Standard buy amount |
| Strong Dip | -1.3% to -2% | 1.5x | Deep dip, buy aggressively |
| Hard Stop | below -2% | 0x | Crash protection, no buy |

---

## Quick Start

### 1. Prerequisites

- Python 3.8+
- Binance account with API access
- Telegram bot (from [@BotFather](https://t.me/BotFather))

### 2. Install

```bash
git clone https://github.com/Aihansu/smart-grid-bot.git smart_grid_bot
cd smart_grid_bot
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

**How to get these:**
- **Binance API**: [API Management](https://www.binance.com/en/my/settings/api-management) → Create API → Enable Spot Trading
- **Telegram Bot**: Message [@BotFather](https://t.me/BotFather) → /newbot → Copy token
- **Chat ID**: Message [@userinfobot](https://t.me/userinfobot) → Copy your ID

### 4. Configure Trading Settings

Edit `config.py`:

```python
INVESTMENT = 1000        # Your total investment in USDT
SYMBOL = 'ETH/USDT'     # Trading pair
PAPER_TRADING = True     # Start with True to test without real money!
```

### 5. Run

```bash
python3 main_v3_0.py
```

For 24/7 on a server:

```bash
screen -S gridbot python3 main_v3_0.py
# Detach: Ctrl+A, D
# Reattach: screen -r gridbot
```

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/status` | Portfolio overview — balance, P/L, commission, BNB |
| `/positions` | List open positions with individual P/L |
| `/grids` | Current grid levels and their status |
| `/commission` | Real-time commission data from Binance |
| `/stats` | Detailed trade statistics |
| `/sell [id]` | Sell a specific position by ID |
| `/sellall` | Market sell all open positions |
| `/start` | Resume trading |
| `/pause` | Pause buying (active sells continue) |
| `/shutdown` | Sell everything and stop the bot |
| `/reset` | Regenerate grids at current price |

---

## Configuration

All settings are in `config.py`:

### Core Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `INVESTMENT` | 1000 | Total USDT investment |
| `SYMBOL` | ETH/USDT | Trading pair |
| `GRID_COUNT` | 10 | Number of grid levels |
| `GRID_SPREAD` | 0.025 | Grid spacing (2.5%) |
| `PAPER_TRADING` | True | Paper trading mode |

### Trailing Stop

| Setting | Default | Description |
|---------|---------|-------------|
| `TRAILING_PROFIT_PCT` | 1.2 | Trailing activates at this profit % |
| `TRAILING_CALLBACK_PCT` | 0.3 | Sells when price drops this % from peak |

### EMA Dynamic Buy Zones

| Setting | Default | Description |
|---------|---------|-------------|
| `EMA_PERIOD` | 30 | EMA calculation period |
| `EMA_ABOVE_MULTIPLIER` | 0.5 | Buy multiplier when above EMA |
| `EMA_WEAK_MULTIPLIER` | 0.75 | Buy multiplier for weak dip |
| `EMA_NORMAL_MULTIPLIER` | 1.0 | Buy multiplier for normal dip |
| `EMA_STRONG_MULTIPLIER` | 1.5 | Buy multiplier for strong dip |

### Advanced

| Setting | Default | Description |
|---------|---------|-------------|
| `AUTO_COMPOUND` | True | Reinvest profits into larger buys |
| `ENABLE_REBALANCING` | True | Sell worst position to buy lower when cash is low |
| `MIN_CASH_BEFORE_REBALANCING` | 50.0 | Swap triggers when cash drops below this amount |
| `AUTO_GRID_RESET` | True | Auto-reset grids when price moves out of range |
| `DAILY_REPORT_ENABLED` | True | Send daily summary via Telegram |

---

## Server Setup (Optional)

For 24/7 operation on a VPS (e.g., DigitalOcean $6/mo, Hetzner $3.50/mo):

```bash
# SSH into your server
ssh root@your-server-ip

# Install Python
apt update && apt install python3 python3-pip -y

# Clone and setup
git clone https://github.com/Aihansu/smart-grid-bot.git smart_grid_bot
cd smart_grid_bot
pip3 install -r requirements.txt

# Configure
cp .env.example .env
nano .env

# Run in background
screen -dmS gridbot python3 main_v3_0.py

# Check status
screen -r gridbot
```

---

## Tips

- **Always start with paper trading** (`PAPER_TRADING = True`) to understand the bot before risking real money
- **Enable BNB fee payment** on Binance for 25% commission discount
- **Keep some BNB** in your account — the bot auto-buys $20 BNB when balance drops below $5
- **Monitor via Telegram** — the bot sends real-time notifications for every trade
- **Don't panic during dips** — DCA mode is designed to accumulate at lower prices

---

## Disclaimer

This bot is for educational purposes. Trading cryptocurrency involves significant risk. Use at your own risk. Always start with paper trading and small amounts.
