# Smart Grid Bot v3.0

A fully automated **grid trading bot** for Binance with DCA strategy, trailing stop-loss, and EMA-based dynamic buy zones. Runs 24/7 and is fully controlled via Telegram.

> **Legend:** 🆕 new in the latest update · 🔄 changed in the latest update · 🐛 bug fix

---

## What's New (October 2026)

- 🆕 **Smart buy sizing**: fixed base above a balance threshold, proportional below it, hard cap per buy (see Buy Sizing below)
- 🆕 **Live settings via Telegram**: `/settings`, `/threshold`, `/multiplier`, saved across restarts
- 🆕 **Weekly and monthly reports**, plus the `/report` command
- 🆕 **systemd service file** (`gridbot.service`) for running 24/7 on a server
- 🔄 `/status` now shows the EMA distance and the current buy zone
- 🔄 `/positions` splits long lists into several messages (Telegram length limit)
- 🔄 Trailing notifications show the position's cost and current value
- 🐛 Net profit now subtracts the commission when fees are paid in BNB
- 🐛 The grid center line no longer turns into a buy level due to float rounding

---

## Features

| Feature | Description |
|---------|-------------|
| **Grid Trading** | Creates 10 grid levels across a dynamic price range and buys the dips |
| **Trailing Stop** | Locks profit automatically — activates at +1.2%, sells on -0.3% pullback |
| **EMA Dynamic Buy Zones** | Adjusts buy amounts based on distance from EMA — buy less when expensive, buy more on deep dips |
| **Smart Buy Sizing** 🆕 | Proportional buys on small balances, a fixed base on large balances, and a hard cap per buy — many small positions instead of a few huge ones |
| **Live Settings via Telegram** 🆕 | Change the threshold and zone multipliers from Telegram — changes survive restarts |
| **DCA Mode** | No stop loss — accumulates positions on dips for long-term gains |
| **Auto Compound** 🔄 | Below the threshold, buy amounts scale with your current balance |
| **Auto Grid Reset** | Regenerates grids when price moves out of range |
| **Orphan System** | Old positions continue trading independently after grid reset |
| **Rebalancing** | When cash drops below $50, sells the top losing position to buy lower |
| **BNB Auto-Buy** | Automatically purchases BNB when balance is low to maintain fee discounts |
| **Daily / Weekly / Monthly Reports** 🔄 | Sends P/L, commission and buy/sell counts via Telegram at the end of each period |
| **Paper Trading** | Test the bot risk-free before going live |

---

## EMA Dynamic Buy Zones

The bot adjusts buy amounts based on how far the price has dropped from the EMA (Exponential Moving Average):

| Zone | EMA Distance | Multiplier | Meaning |
|------|-------------|------------|---------|
| Expensive | > +5% | 0x | Way above EMA, don't buy |
| Above EMA | 0% to +5% | 0.5x | Price is expensive, buy less |
| Weak Dip | 0% to -1.5% | 0.75x | Small dip, conserve capital |
| Normal Dip | -1.5% to -3% | 1.0x | Standard buy amount |
| Strong Dip | -3% to -5% | 1.5x | Deep dip, buy aggressively |
| Hard Stop | below -5% | 0x | Crash protection, no buy |

🆕 The `/status` command now shows the current EMA distance and which zone the bot is in.

---

## Buy Sizing 🆕

Each buy = **base amount × zone multiplier**, capped at `MAX_BUY_USDT`. The base amount depends on your free USDT balance:

- **Balance above `FIXED_AMOUNT_THRESHOLD`** ($1,000) → fixed base of `FIXED_GRID_AMOUNT` ($100). Buys don't grow as your balance grows — extra cash gives the bot more *depth* to keep buying through a long dip.
- **Balance below the threshold** → base = balance ÷ `GRID_COUNT`, so buys shrink with your balance.

| Balance | Above EMA (0.5x) | Weak Dip (0.75x) | Normal Dip (1.0x) | Strong Dip (1.5x) |
|---------|-----------------|------------------|-------------------|-------------------|
| $727 (proportional) | $36 | $55 | $73 | $109 |
| $1,000+ (fixed) | $50 | $75 | $100 | $150 |
| $5,000 (fixed) | $50 | $75 | $100 | $150 |

New amounts take effect on the next grid reset (automatic, or `/reset`). Zone multipliers apply immediately.

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

🔄 For 24/7 operation, run it as a systemd service — see [Server Setup](#server-setup-optional).

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/status` 🔄 | Portfolio overview — price, EMA distance and buy zone, balance, P/L, BNB |
| `/positions` 🔄 | List open positions with individual P/L (split into several messages when long) |
| `/grids` | Current grid levels and their status |
| `/commission` | Real-time commission data from Binance |
| `/stats` | Detailed trade statistics |
| `/report` 🆕 | Live daily / weekly / monthly summary |
| `/settings` 🆕 | Current buy settings and the resulting buy amounts per zone |
| `/threshold [amount]` 🆕 | Change `FIXED_AMOUNT_THRESHOLD` (e.g. `/threshold 1500`) |
| `/multiplier [zone] [value]` 🆕 | Change a zone multiplier — zones: `above`, `weak`, `normal`, `strong` (e.g. `/multiplier normal 1.3`) |
| `/sell [id]` | Sell a specific position by ID |
| `/sellall` | Market sell all open positions |
| `/start` | Resume trading |
| `/pause` | Pause the bot (no buys or sells until `/start`) |
| `/shutdown` | Sell everything and stop the bot |
| `/reset` | Regenerate grids at current price |
| `/help` | List all commands |

> Settings changed with `/threshold` and `/multiplier` are saved in `state_v3_0.json` and **override `config.py`** after a restart. Use `/settings` to see the values actually in use.

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

### Buy Sizing 🆕

| Setting | Default | Description |
|---------|---------|-------------|
| `FIXED_GRID_AMOUNT` | 100.0 | Fixed base buy amount (used above the threshold) |
| `FIXED_AMOUNT_THRESHOLD` | 1000.0 | Above this USDT balance: fixed base; below: proportional |
| `MAX_BUY_USDT` | 150.0 | Hard cap for a single buy, even after multipliers |

### Trailing Stop

| Setting | Default | Description |
|---------|---------|-------------|
| `TRAILING_PROFIT_PCT` | 1.2 | Trailing activates at this profit % |
| `TRAILING_CALLBACK_PCT` | 0.3 | Sells when price drops this % from peak |

### EMA Dynamic Buy Zones

| Setting | Default | Description |
|---------|---------|-------------|
| `EMA_PERIOD` | 30 | EMA calculation period |
| `EMA_ZONE_EXPENSIVE` | 5.0 | Block buys when price is 5%+ above EMA |
| `EMA_ABOVE_MULTIPLIER` | 0.5 | Buy multiplier when above EMA |
| `EMA_WEAK_MULTIPLIER` | 0.75 | Buy multiplier for weak dip |
| `EMA_NORMAL_MULTIPLIER` | 1.0 | Buy multiplier for normal dip |
| `EMA_STRONG_MULTIPLIER` | 1.5 | Buy multiplier for strong dip |

### Advanced

| Setting | Default | Description |
|---------|---------|-------------|
| `AUTO_COMPOUND` 🔄 | True | Below the threshold, scale buys with current balance |
| `ENABLE_REBALANCING` | True | Sell worst position to buy lower when cash is low |
| `MIN_CASH_BEFORE_REBALANCING` | 50.0 | Swap triggers when cash drops below this amount |
| `AUTO_GRID_RESET` | True | Auto-reset grids when price moves out of range |
| `DAILY_REPORT_ENABLED` 🔄 | True | Send daily / weekly / monthly summaries via Telegram (UTC) |

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
```

### Run as a systemd service (recommended) 🆕

systemd keeps the bot running 24/7: it restarts automatically after a crash or a server reboot. A ready-made service file is included (`gridbot.service`). Edit the paths in it if you cloned somewhere other than `/root/smart_grid_bot`.

```bash
cp gridbot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now gridbot

# Status & logs
systemctl status gridbot
journalctl -u gridbot -f

# After updating code
systemctl restart gridbot
```

> `WorkingDirectory` in the service file must point to the bot folder — the state file (`state_v3_0.json`) is saved there. Don't also start the bot manually (e.g. in `screen`) while the service is running, or two instances will trade at the same time.

🆕 **Small server tip:** on 1 GB RAM machines, add a swap file so system updates can't run the server out of memory:

```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
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
