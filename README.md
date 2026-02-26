# Smart Grid Bot v2.9

Automated grid trading bot for Binance. Buys dips, sells peaks with trailing stop. Runs 24/7, controlled via Telegram.

## How It Works

- Creates **10 grid levels** across a price range (2.5% spread)
- **Buys** when price drops to a grid level
- **Trailing stop** locks profit: activates at +1.2%, sells on -0.3% from peak
- **EMA trend filter** blocks buys during sharp crashes
- **DCA mode** — no stop loss, accumulates on dips
- **Auto compound** — reinvests profits into larger grid amounts
- **Orphan system** — old positions trade independently after grid reset
- **Rebalancing** — sacrifices worst position to buy lower when balance depleted

## Quick Start

### 1. Prerequisites

- Python 3.8+
- Binance account with API access
- Telegram bot (from @BotFather)

### 2. Install

```bash
git clone <repo-url> smart_grid_bot
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
python3 main_v2_9.py
```

For 24/7 on a server:

```bash
screen -S gridbot python3 main_v2_9.py
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
screen -dmS gridbot python3 main_v2_9.py

# Check status
screen -r gridbot
```

## Disclaimer

This bot is for educational purposes. Trading cryptocurrency involves risk. Use at your own risk. Always start with paper trading and small amounts.
