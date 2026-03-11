# Smart Grid Bot v3.0

Automated grid trading bot for Binance. Buys dips, sells peaks with trailing stop. Runs 24/7, controlled via Telegram.

## How It Works

- Creates **10 grid levels** across a price range (2.5% spread)
- **Buys** when price drops to a grid level
- **Trailing stop** locks profit: activates at +1.2%, sells on -0.3% from peak
- **EMA Dynamic Buy Zones** — adjusts buy amounts based on distance from EMA (buy less near EMA, buy more on deep dips)
- **DCA mode** — no stop loss, accumulates on dips
- **Auto compound** — reinvests profits into larger grid amounts
- **Orphan system** — old positions trade independently after grid reset
- **Rebalancing** — sacrifices worst position to buy lower when balance depleted

## EMA Dynamic Buy Zones

The bot adjusts buy amounts based on how far the price has dropped from the EMA (Exponential Moving Average). Closer to EMA = buy less, deeper dip = buy more.

| Zone | EMA Distance | Multiplier | Meaning |
|------|-------------|------------|---------|
| 📈 Above EMA | > 0% | 0.5x | Price is expensive, buy less |
| 🔹 Weak Dip | 0% to -0.7% | 0.75x | Small dip, conserve capital |
| 🟢 Normal Dip | -0.7% to -1.3% | 1.0x | Standard buy amount |
| 🔥 Strong Dip | -1.3% to -2% | 1.5x | Deep dip, buy aggressively |
| 🔴 Hard Stop | below -2% | 0x | Crash protection, no buy |

## Quick Start

### 1. Prerequisites

- Python 3.8+
- Binance account with API access
- Telegram bot (from @BotFather)

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

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/status` | Portfolio status, P/L, commission |
| `/positions` | Open positions with P/L |
| `/grids` | Grid levels and status |
| `/commission` | Real commission from Binance |
| `/stats` | Trade statistics |
| `/sell [id]` | Sell specific position |
| `/sellall` | Sell all positions |
| `/start` | Resume trading |
| `/pause` | Pause (stops buys, sells continue) |
| `/shutdown` | Sell all and stop bot |
| `/reset` | Regenerate grids at current price |

## Key Settings (config.py)

| Setting | Default | Description |
|---------|---------|-------------|
| `INVESTMENT` | 1000 | Total USDT investment |
| `GRID_COUNT` | 10 | Number of grid levels |
| `GRID_SPREAD` | 0.025 | Grid spacing (2.5%) |
| `TRAILING_PROFIT_PCT` | 1.2 | Trailing activation (%) |
| `TRAILING_CALLBACK_PCT` | 0.3 | Sell callback from peak (%) |
| `PAPER_TRADING` | True | Paper trade mode |
| `MAX_OPEN_POSITIONS` | 25 | Max open positions |
| `ENABLE_REBALANCING` | True | Enable rebalancing |
| `AUTO_COMPOUND` | True | Reinvest profits |
| `EMA_PERIOD` | 30 | EMA calculation period |
| `EMA_ABOVE_MULTIPLIER` | 0.5 | Buy multiplier above EMA |
| `EMA_WEAK_MULTIPLIER` | 0.75 | Buy multiplier for weak dip |
| `EMA_NORMAL_MULTIPLIER` | 1.0 | Buy multiplier for normal dip |
| `EMA_STRONG_MULTIPLIER` | 1.5 | Buy multiplier for strong dip |

## Tips

- **Start with paper trading** (`PAPER_TRADING = True`) to understand the bot
- **Enable BNB fee payment** on Binance for 25% commission discount
- **Buy some BNB** ($5-10) to cover trading fees
- **Monitor via Telegram** — bot sends real-time trade notifications
- **Don't panic** during dips — DCA mode is designed for this

## Server Setup (Optional)

For 24/7 operation on a VPS (e.g., DigitalOcean $6/mo):

```bash
# SSH into your server
ssh root@your-server-ip

# Install Python
apt update && apt install python3 python3-pip -y

# Upload bot files
# (use scp, git, or manual upload)

# Install dependencies
pip3 install -r requirements.txt

# Create .env and configure
cp .env.example .env
nano .env

# Run in background
screen -dmS gridbot python3 main_v3_0.py

# Check status
screen -r gridbot
```

## Disclaimer

This bot is for educational purposes. Trading cryptocurrency involves risk. Use at your own risk. Always start with paper trading and small amounts.
