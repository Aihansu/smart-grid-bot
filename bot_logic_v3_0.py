import time
import os
import sys
import json
from datetime import datetime, timezone, timedelta
from collections import deque

# UTC timezone for daily report
TZ_UTC = timezone.utc
import config
from utils import Colors
from exchange_handler import ExchangeHandler
import telegram_handler

class SmartGridBotDCA_v3_0:
    def __init__(self):
        self.version = "3.0"
        self.state_file = "state_v3_0.json"
        self.running = True
        self.paused = False
        self.show_grid = config.SHOW_GRID_TABLE
        
        self.telegram_offset = None
        self.grid_out_of_range_notified = False
        self.trend_block_notified = False
        self.max_pos_notified = False
        self.bnb_low_notified = False

        self.exchange_handler = ExchangeHandler()
        self.exchange = self.exchange_handler.exchange
        
        # Default initialization
        self.balance_usdt = config.INVESTMENT
        self.balance_eth = 0.0
        
        self.grids = []
        self.open_positions = []
        self.position_counter = 0
        self.filled_orders = []
        self.total_profit = 0.0
        self.total_commission = 0.0
        self.start_time = datetime.now()
        self.last_report_date = datetime.now().strftime("%Y-%m-%d")
        self.last_week = datetime.now().strftime("%Y-W%W")
        self.last_month = datetime.now().strftime("%Y-%m")
        self.config_overrides = {}  # Settings changed via Telegram (survive restarts)

        # Local state (non-persistent)
        self.current_price = 0
        self.last_sync_time = 0  # Balance sync timestamp
        self.last_ema_update = 0  # EMA update timestamp
        self.price_history = deque(maxlen=config.EMA_PERIOD * 2)
        self.ema_value = None
        self.stats = {
            'total_buys': 0, 'total_sells': 0, 'blocked_by_trend': 0,
            'dip_buys': 0, 'max_drawdown': 0, 'winning_trades': 0, 'losing_trades': 0,
            'total_commission': 0.0,
            'daily_stats': {'profit': 0.0, 'commission': 0.0, 'trades': 0, 'buys': 0, 'sells': 0},
            'weekly_stats': {'profit': 0.0, 'commission': 0.0, 'trades': 0, 'buys': 0, 'sells': 0},
            'monthly_stats': {'profit': 0.0, 'commission': 0.0, 'trades': 0, 'buys': 0, 'sells': 0}
        }

        # Try to load existing state
        self._load_state()
        
        # Real Balance Sync (if not Paper Trading) - Must be done after state is loaded
        if not config.PAPER_TRADING:
            print(f"   {Colors.highlight('🔄 Syncing real balances...')}")

            # 1. USDT Balance
            real_usdt = self.exchange_handler.get_balance('USDT')
            if real_usdt > 0:
                self.balance_usdt = real_usdt
                print(f"   {Colors.success(f'✅ Real Balance (USDT): ${real_usdt:.2f}')}")

            # 2. Crypto Balance (ETH, etc.)
            base_asset = config.SYMBOL.split('/')[0]
            real_crypto = self.exchange_handler.get_balance(base_asset)
            # Can be 0.0 but usually there is some amount.
            # Note: We only sync if balance exists.
            if real_crypto >= 0:
                self.balance_eth = real_crypto
                print(f"   {Colors.success(f'✅ Real Crypto ({base_asset}): {real_crypto}')}")

            self._save_state() # Save new balances immediately
        
        self._clear_old_telegram_messages()
        self._clear_screen()
        self._print_banner()
        self._print_config()
        self._send_startup_notification()

    def _save_state(self):
        """Save bot state to file"""
        state = {
            'virtual_balance': self.balance_usdt,
            'virtual_crypto': self.balance_eth,
            'open_positions': self.open_positions,
            'position_counter': self.position_counter,
            'total_profit': self.total_profit,
            'total_commission': self.total_commission,
            'last_report_date': self.last_report_date,
            'last_week': self.last_week,
            'last_month': self.last_month,
            'config_overrides': self.config_overrides,
            'grids': self.grids,
            'stats': self.stats,
            'filled_orders': self.filled_orders,
            'start_time': self.start_time.isoformat() if isinstance(self.start_time, datetime) else self.start_time,
            'last_update': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        try:
            tmp_file = self.state_file + '.tmp'
            with open(tmp_file, 'w') as f:
                json.dump(state, f, indent=4)
            os.replace(tmp_file, self.state_file)  # Atomic rename - crash-safe
        except Exception as e:
            print(f"\n{Colors.error('❌ Failed to save state: ' + str(e))}")

    def _load_state(self):
        """Load bot state from file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.balance_usdt = state.get('virtual_balance', config.INVESTMENT)
                    self.balance_eth = state.get('virtual_crypto', 0.0)
                    self.open_positions = state.get('open_positions', [])
                    self.position_counter = state.get('position_counter', 0)
                    self.total_profit = state.get('total_profit', 0.0)
                    self.total_commission = state.get('total_commission', 0.0)
                    self.last_report_date = state.get('last_report_date', datetime.now().strftime("%Y-%m-%d"))
                    self.last_week = state.get('last_week', datetime.now().strftime("%Y-W%W"))
                    self.last_month = state.get('last_month', datetime.now().strftime("%Y-%m"))
                    # Re-apply settings changed via Telegram (these override config.py)
                    self.config_overrides = state.get('config_overrides', {})
                    for _k, _v in self.config_overrides.items():
                        setattr(config, _k, _v)
                    self.grids = state.get('grids', [])
                    
                    # Robust Stats Merging: Ensure all keys exist even when loading old state files
                    loaded_stats = state.get('stats', {})
                    for key, value in self.stats.items():
                        if key not in loaded_stats:
                            loaded_stats[key] = value
                        elif isinstance(value, dict) and isinstance(loaded_stats[key], dict):
                            # Deep merge for one level (e.g., daily_stats)
                            for sub_key, sub_val in value.items():
                                if sub_key not in loaded_stats[key]:
                                    loaded_stats[key][sub_key] = sub_val
                    
                    self.stats = loaded_stats
                    self.filled_orders = state.get('filled_orders', [])
                    
                    st_str = state.get('start_time')
                    if st_str:
                        try:
                            self.start_time = datetime.fromisoformat(st_str)
                        except:
                            self.start_time = datetime.now()
                        
                    print(f"{Colors.success('✅ Previous state loaded: ' + self.state_file)}")
            except Exception as e:
                print(f"{Colors.error('⚠️ Failed to read state file, starting fresh: ' + str(e))}")

    def _send_startup_notification(self):
        mode_text = "DCA Mode (Stop Loss Disabled)" if not config.STOP_LOSS_ENABLED else "Normal Mode"
        msg = (f"🤖 <b>Grid Bot v{self.version} Started!</b>\n\n"
               f"💰 Investment: ${config.INVESTMENT}\n"
               f"📊 Symbol: {config.SYMBOL}\n"
               f"🔢 Grid: {config.GRID_COUNT} levels\n"
               f"🎯 Mode: {mode_text}\n"
               f"💾 State: {'Loaded' if os.path.exists(self.state_file) else 'New'}\n\n"
               f"📋 Use the buttons below for the menu.")
        telegram_handler.send_telegram(msg, reply_markup=telegram_handler.get_main_keyboard())

    def _clear_old_telegram_messages(self):
        try:
            updates = telegram_handler.get_telegram_updates(None)
            if updates:
                last_update_id = updates[-1]['update_id']
                self.telegram_offset = last_update_id + 1
        except Exception as e:
            print(f"{Colors.warning('⚠️ Telegram message cleanup error: ' + str(e))}")

    def _clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def _print_banner(self):
        print(f"\n{Colors.CYAN}╔══════════════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.CYAN}║  {Colors.BOLD}{Colors.WHITE}🤖 SMART GRID BOT v{self.version} - DCA MODE (Persistence){Colors.RESET}{Colors.CYAN}            ║{Colors.RESET}")
        print(f"{Colors.CYAN}║  {Colors.DIM}Continuous Buy/Sell + Trailing TP + State Persistence{Colors.RESET}{Colors.CYAN}            ║{Colors.RESET}")
        print(f"{Colors.CYAN}╚══════════════════════════════════════════════════════════════════╝{Colors.RESET}\n")

    def _print_config(self):
        print(Colors.info('📋 SETTINGS'))
        print(f"   Symbol: {Colors.highlight(config.SYMBOL)}")
        print(f"   Investment: {Colors.highlight('$' + str(config.INVESTMENT))}")
        print(f"   Trailing TP: {Colors.success('ACTIVE (%' + str(config.TRAILING_PROFIT_PCT) + ' / %' + str(config.TRAILING_CALLBACK_PCT) + ')')}")
        print(f"   Telegram: {Colors.success('ACTIVE') if config.TELEGRAM_ENABLED else Colors.error('DISABLED')}\n")

    def _print_keyboard_help(self):
        print(f"{Colors.CYAN}{'─'*65}{Colors.RESET}")
        print(f"{Colors.BOLD}⌨️  KEYBOARD SHORTCUTS:{Colors.RESET}")
        print(f"   {Colors.highlight('g')} = Grid table | {Colors.highlight('p')} = Positions | {Colors.highlight('h')} = History")
        print(f"   {Colors.highlight('s')} = Statistics | {Colors.highlight('c')} = Clear screen | {Colors.highlight('q')} = Quit")
        print(f"\n{Colors.BOLD}📱 TELEGRAM COMMANDS:{Colors.RESET}")
        print(f"   /status /positions /stats /report /grids /settings /start /pause /shutdown /reset /help")
        print(f"{Colors.CYAN}{'─'*65}{Colors.RESET}\n")

    def process_telegram_commands(self, timeout=1):
        updates = telegram_handler.get_telegram_updates(self.telegram_offset, timeout=timeout)
        for update in updates:
            self.telegram_offset = update['update_id'] + 1
            if 'message' not in update or 'text' not in update['message']: continue
            message = update['message']
            if str(message['chat']['id']) != config.TELEGRAM_CHAT_ID: continue
            text = message['text'].strip().lower()
            
            # Simple command routing
            if text == '/status': self._cmd_status()
            elif text == '/positions': self._cmd_positions()
            elif text == '/stats': self._cmd_stats()
            elif text == '/grids': self._cmd_grids()
            elif text == '/start': self._cmd_start()
            elif text == '/pause': self._cmd_pause()
            elif text == '/reset': self._cmd_reset()
            elif text == '/help': self._cmd_help()
            elif text == '/commission': self._cmd_commission()
            elif text == '/report': self._cmd_report()
            elif text == '/settings': self._cmd_settings()
            elif text.startswith('/threshold'): self._cmd_threshold(text)
            elif text.startswith('/multiplier'): self._cmd_multiplier(text)
            elif text == '/sellall': self._cmd_sellall()
            elif text.startswith('/sell '): self._cmd_sell_specific(text)
            elif text == '/shutdown': self._cmd_shutdown()

    def _get_real_commission(self):
        """Fetch real commission data from Binance (returns BNB denomination)"""
        try:
            trades = self.exchange_handler.fetch_all_my_trades(config.SYMBOL)
            if not trades:
                return None
            total_fee_bnb = 0.0
            for t in trades:
                fee = t.get('fee', {})
                fc = fee.get('cost', 0.0) or 0.0
                curr = fee.get('currency', '')
                if curr == 'BNB':
                    total_fee_bnb += fc
                elif curr == 'USDT':
                    # Convert USDT fee to BNB
                    bnb_price = self.exchange_handler.get_current_price('BNB/USDT')
                    if bnb_price:
                        total_fee_bnb += fc / bnb_price
                else:
                    price = t.get('price', 0)
                    bnb_price = self.exchange_handler.get_current_price('BNB/USDT')
                    if price and bnb_price:
                        total_fee_bnb += (fc * price) / bnb_price
            return total_fee_bnb
        except:
            return None

    def _cmd_status(self):
        try:
            if not self.current_price: return telegram_handler.send_telegram("❌ Could not fetch price!")
            total_value = self.balance_usdt + (self.balance_eth * self.current_price)
            pnl = total_value - config.INVESTMENT
            pnl_pct = (pnl / config.INVESTMENT) * 100 if config.INVESTMENT > 0 else 0
            runtime = str(datetime.now() - self.start_time).split('.')[0]

            base_asset = config.SYMBOL.split('/')[0]
            crypto_value = self.balance_eth * self.current_price

            bnb_balance = self.exchange_handler.get_balance('BNB')
            bnb_price = self.exchange_handler.get_current_price('BNB/USDT')
            bnb_usd = bnb_balance * bnb_price if bnb_balance > 0 and bnb_price else 0
            bnb_str = f"{bnb_balance:.4f} (~${bnb_usd:.2f}) {'⚠️' if bnb_usd < 5 else ''}"

            gross_profit = self.total_profit + self.total_commission
            net_profit = self.total_profit

            ema_str = f"{self.ema_value:,.2f}" if self.ema_value else "0.00"
            if self.ema_value:
                ema_dev = ((self.current_price - self.ema_value) / self.ema_value) * 100
                # Zone detection (same thresholds as check_hybrid_filter)
                if ema_dev >= config.EMA_ZONE_EXPENSIVE:
                    zone_emoji, zone_name, zone_mult = "🚫", "Too Expensive", "0x"
                elif ema_dev >= 0:
                    zone_emoji, zone_name, zone_mult = "📈", "Above EMA", f"{config.EMA_ABOVE_MULTIPLIER}x"
                elif ema_dev >= config.EMA_ZONE_WEAK:
                    zone_emoji, zone_name, zone_mult = "🔹", "Weak Dip", f"{config.EMA_WEAK_MULTIPLIER}x"
                elif ema_dev >= config.EMA_ZONE_NORMAL:
                    zone_emoji, zone_name, zone_mult = "🟢", "Normal Dip", f"{config.EMA_NORMAL_MULTIPLIER}x"
                elif ema_dev >= config.EMA_ZONE_STRONG:
                    zone_emoji, zone_name, zone_mult = "🔥", "Strong Dip", f"{config.EMA_STRONG_MULTIPLIER}x"
                else:
                    zone_emoji, zone_name, zone_mult = "🛑", "Hard Stop", "0x"
                ema_dev_str = (f"\n📐 <b>EMA Distance:</b> {ema_dev:+.2f}%"
                               f"\n{zone_emoji} <b>Zone:</b> {zone_name} ({zone_mult})")
            else:
                ema_dev_str = ""
            msg = (f"📊 <b>BOT STATUS</b> {'⏸️' if self.paused else '✅'}\n\n"
                   f"💰 <b>Price:</b> ${self.current_price:,.2f} | 📈 <b>EMA:</b> ${ema_str}{ema_dev_str}\n"
                   f"──────────────────\n"
                   f"💵 <b>Balance (USDT):</b> ${self.balance_usdt:.2f}\n"
                   f"🪙 <b>{base_asset}:</b> {self.balance_eth:.6f} (${crypto_value:.2f})\n"
                   f"🔶 <b>BNB (Fee):</b> {bnb_str}\n"
                   f"📊 <b>Total Portfolio:</b> ${total_value:.2f}\n"
                   f"{'📈' if pnl >= 0 else '📉'} <b>Overall P/L:</b> ${pnl:+.2f} ({pnl_pct:+.2f}%)\n"
                   f"──────────────────\n"
                   f"💰 <b>Gross Profit:</b> ${gross_profit:+.2f}\n"
                   f"{'💵' if net_profit >= 0 else '🔻'} <b>Net Profit:</b> ${net_profit:+.2f}\n"
                   f"──────────────────\n"
                   f"📍 <b>Open Positions:</b> {len(self.open_positions)}"
                   f"{' (🔸' + str(sum(1 for p in self.open_positions if p.get('grid_id', -1) == -1)) + ' orphan)' if any(p.get('grid_id', -1) == -1 for p in self.open_positions) else ''}"
                   f" | 🟢 <b>Empty Grids:</b> {sum(1 for g in self.grids if g['status'] == 'waiting_buy')}\n"
                   f"⏱️ <b>Uptime:</b> {runtime}")
            telegram_handler.send_telegram(msg)
        except Exception as e:
            print(f"❌ /status error: {e}")
            telegram_handler.send_telegram(f"❌ /status error: {str(e)}")

    def _cmd_positions(self):
        if not self.open_positions: return telegram_handler.send_telegram("📍 No open positions.")
        total_pnl_usd = 0.0
        total_cost = 0.0

        # Telegram has a 4096-char limit; split the message into chunks when there are many positions
        MAX_LEN = 3500
        header = f"📍 <b>OPEN POSITIONS</b> ({len(self.open_positions)})\n\n"
        chunk = header
        for pos in self.open_positions:
            pnl_pct = ((self.current_price - pos['buy_price']) / pos['buy_price']) * 100
            pnl_usd = (self.current_price - pos['buy_price']) * pos['crypto_amount']
            total_pnl_usd += pnl_usd
            cost = pos['buy_price'] * pos['crypto_amount']
            total_cost += cost

            orphan_tag = " 🔸" if pos.get('grid_id', -1) == -1 else ""
            line = (f"#{pos['id']}{orphan_tag}: ${pos['buy_price']:,.2f} | <b>Amount: ${cost:.2f}</b> → P/L: ${pnl_usd:+.2f} ({pnl_pct:+.2f}%)\n"
                    f"   Sell individual: /sell {pos['id']}\n")
            # If this line would exceed the limit, send the current chunk and start a new one
            if len(chunk) + len(line) > MAX_LEN:
                telegram_handler.send_telegram(chunk)
                chunk = ""
            chunk += line

        total_pnl_pct = (total_pnl_usd / total_cost) * 100 if total_cost > 0 else 0
        chunk += f"\n──────────────────\n"
        chunk += f"💰 <b>Total Cost: ${total_cost:.2f}</b>\n"
        chunk += f"📊 <b>Total P/L: ${total_pnl_usd:+.2f} ({total_pnl_pct:+.2f}%)</b>"
        telegram_handler.send_telegram(chunk)

    def _cmd_sellall(self):
        count = len(self.open_positions)
        if count == 0: return telegram_handler.send_telegram("📍 No positions to sell.")
        for pos in self.open_positions[:]:
            self._close_position(pos, self.current_price, datetime.now().strftime("%H:%M:%S"), "Manual Sell All")
        telegram_handler.send_telegram(f"✅ {count} positions sold at market price.")

    def _cmd_sell_specific(self, text):
        try:
            pos_id = int(text.split(' ')[1])
            for pos in self.open_positions:
                if pos['id'] == pos_id:
                    self._close_position(pos, self.current_price, datetime.now().strftime("%H:%M:%S"), "Manual Single Sell")
                    return telegram_handler.send_telegram(f"✅ Position #{pos_id} sold.")
            telegram_handler.send_telegram(f"❌ #{pos_id} not found.")
        except:
            telegram_handler.send_telegram("❌ Usage: /sell [id]")

    def _cmd_stats(self):
        runtime = str(datetime.now() - self.start_time).split('.')[0]
        msg = (f"📊 <b>STATISTICS</b>\n\n⏱️ Uptime: {runtime}\n"
               f"🔄 Trades: {len(self.filled_orders)}\n"
               f"🟢 Buys: {self.stats['total_buys']} | 🔴 Sells: {self.stats['total_sells']}\n"
               f"💎 Profit: ${self.total_profit:+.2f}")
        telegram_handler.send_telegram(msg)

    def _cmd_grids(self):
        if not self.grids: return telegram_handler.send_telegram("📋 No grids.")
        msg = f"📋 <b>GRIDS</b>\n📍 Price: ${self.current_price:,.2f}\n\n"
        for grid in reversed(self.grids):
            icon = "🟢" if grid['status'] == 'waiting_buy' else "🟡" if grid['status'] == 'filled' else "⚪"
            msg += f"{icon} {grid['id']+1}: ${grid['price']:,.2f}\n"
        orphan_count = sum(1 for pos in self.open_positions if pos.get('grid_id', -1) == -1)
        if orphan_count > 0:
            msg += f"\n🔸 <b>Orphan Positions:</b> {orphan_count} (will sell at their targets)"
        telegram_handler.send_telegram(msg)

    def _cmd_start(self):
        self.paused = False
        telegram_handler.send_telegram("🚀 <b>Bot Resumed!</b>")

    def _cmd_pause(self):
        self.paused = True
        telegram_handler.send_telegram("⏸️ <b>Bot Paused</b>")

    def _cmd_shutdown(self):
        self._cmd_sellall()
        self.running = False
        self._save_state() # Ensure final state is saved
        telegram_handler.send_telegram("🛑 <b>Bot Shut Down.</b>")

    def _cmd_reset(self):
        self._create_grids(self.current_price)
        telegram_handler.send_telegram("🔄 <b>Grids Recreated.</b>")

    def _cmd_commission(self):
        telegram_handler.send_telegram("⏳ Fetching all trade history from Binance...")
        trades = self.exchange_handler.fetch_all_my_trades(config.SYMBOL)
        if not trades:
            return telegram_handler.send_telegram("❌ Could not fetch trade history or no trades yet.")

        total_fee_usdt = 0.0
        total_fee_bnb = 0.0
        bnb_usdt_value = 0.0
        buy_fee = 0.0
        sell_fee = 0.0
        trade_count = len(trades)

        for trade in trades:
            fee = trade.get('fee', {})
            fee_cost = fee.get('cost', 0.0) or 0.0
            fee_currency = fee.get('currency', '')
            side = trade.get('side', '')
            trade_cost = trade.get('cost', 0)

            if fee_currency == 'BNB':
                total_fee_bnb += fee_cost
                # Calculate BNB fee as USDT using trade-time rate
                fee_as_usdt = trade_cost * 0.00075 if trade_cost else 0
                bnb_usdt_value += fee_as_usdt
                if side == 'buy':
                    buy_fee += fee_as_usdt
                else:
                    sell_fee += fee_as_usdt
            elif fee_currency == 'USDT':
                total_fee_usdt += fee_cost
                if side == 'buy':
                    buy_fee += fee_cost
                else:
                    sell_fee += fee_cost
            else:
                # Convert commissions paid in ETH or other coins to USDT
                price = trade.get('price', 0)
                if price:
                    fee_as_usdt = fee_cost * price
                    total_fee_usdt += fee_as_usdt
                    if side == 'buy':
                        buy_fee += fee_as_usdt
                    else:
                        sell_fee += fee_as_usdt

        grand_total = total_fee_usdt + bnb_usdt_value

        # First and last trade dates
        first_date = trades[0].get('datetime', '')[:10] if trades else '-'
        last_date = trades[-1].get('datetime', '')[:10] if trades else '-'

        msg = (f"💸 <b>COMMISSION REPORT</b>\n"
               f"━━━━━━━━━━━━━━━━━━━\n"
               f"📊 <b>Total Trades:</b> {trade_count}\n"
               f"📅 <b>Period:</b> {first_date} → {last_date}\n"
               f"━━━━━━━━━━━━━━━━━━━\n")

        if total_fee_bnb > 0:
            msg += (f"🔸 <b>BNB Commission:</b> {total_fee_bnb:.6f} BNB\n"
                    f"   ≈ ${bnb_usdt_value:.2f} USDT\n")
        if total_fee_usdt > 0:
            msg += (f"🔹 <b>USDT Commission:</b> ${total_fee_usdt:.2f}\n"
                    f"   📈 Buy: ${buy_fee:.2f} | 📉 Sell: ${sell_fee:.2f}\n")

        msg += (f"━━━━━━━━━━━━━━━━━━━\n"
                f"💰 <b>TOTAL:</b> ${grand_total:.2f} USDT\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📌 <b>Bot Estimate:</b> ${self.total_commission:.2f}\n"
                f"📌 <b>Difference:</b> ${abs(grand_total - self.total_commission):.2f}")
        telegram_handler.send_telegram(msg)

    def _cmd_report(self):
        """Live daily/weekly/monthly summary (current, not-yet-reset period data)"""
        def block(emoji, title, label, s):
            return (f"{emoji} <b>{title}</b> ({label})\n"
                    f"💰 Net Profit: ${s['profit']:+.2f} | 💸 Comm: ${s['commission']:.2f}\n"
                    f"🟢 Buys: {s.get('buys', 0)} | 🔴 Sells: {s.get('sells', 0)} | 🔄 Total: {s['trades']}\n")
        portfolio = self.balance_usdt + (self.balance_eth * self.current_price)
        msg = ("📊 <b>LIVE SUMMARY REPORT</b>\n"
               "<i>(also sent automatically at the end of each period)</i>\n"
               "──────────────────\n"
               + block("📅", "TODAY", self.last_report_date, self.stats['daily_stats'])
               + "──────────────────\n"
               + block("📆", "THIS WEEK", self.last_week, self.stats['weekly_stats'])
               + "──────────────────\n"
               + block("🗓️", "THIS MONTH", self.last_month, self.stats['monthly_stats'])
               + "──────────────────\n"
               + f"💹 <b>Total Portfolio:</b> ${portfolio:.2f}")
        telegram_handler.send_telegram(msg)

    def _cmd_settings(self):
        """Show current buy settings"""
        msg = (f"⚙️ <b>BUY SETTINGS</b>\n"
               f"──────────────────\n"
               f"💵 Fixed base: ${config.FIXED_GRID_AMOUNT:.0f}\n"
               f"📏 Threshold: ${config.FIXED_AMOUNT_THRESHOLD:.0f}\n"
               f"   (above this balance: fixed base, below: proportional)\n"
               f"🔒 Max single buy: ${config.MAX_BUY_USDT:.0f}\n"
               f"──────────────────\n"
               f"📈 Above EMA: {config.EMA_ABOVE_MULTIPLIER}x → ${min(config.FIXED_GRID_AMOUNT*config.EMA_ABOVE_MULTIPLIER, config.MAX_BUY_USDT):.0f}\n"
               f"🔹 Weak Dip: {config.EMA_WEAK_MULTIPLIER}x → ${min(config.FIXED_GRID_AMOUNT*config.EMA_WEAK_MULTIPLIER, config.MAX_BUY_USDT):.0f}\n"
               f"🟢 Normal Dip: {config.EMA_NORMAL_MULTIPLIER}x → ${min(config.FIXED_GRID_AMOUNT*config.EMA_NORMAL_MULTIPLIER, config.MAX_BUY_USDT):.0f}\n"
               f"🔥 Strong Dip: {config.EMA_STRONG_MULTIPLIER}x → ${min(config.FIXED_GRID_AMOUNT*config.EMA_STRONG_MULTIPLIER, config.MAX_BUY_USDT):.0f}\n"
               f"──────────────────\n"
               f"Change:\n"
               f"/threshold [amount] — e.g. /threshold 1500\n"
               f"/multiplier [zone] [value] — e.g. /multiplier normal 1.3\n"
               f"Zones: above, weak, normal, strong")
        telegram_handler.send_telegram(msg)

    def _cmd_threshold(self, text):
        """Change the fixed-base threshold via Telegram"""
        try:
            val = float(text.split()[1].replace(',', '.'))
            if not (0 <= val <= 100000): raise ValueError
            config.FIXED_AMOUNT_THRESHOLD = val
            self.config_overrides['FIXED_AMOUNT_THRESHOLD'] = val
            self._save_state()
            mode = "FIXED base" if self.balance_usdt > val else "PROPORTIONAL"
            telegram_handler.send_telegram(
                f"✅ <b>Threshold updated:</b> ${val:.0f}\n"
                f"💵 Current balance: ${self.balance_usdt:.2f} → now in <b>{mode}</b> mode.")
        except (IndexError, ValueError):
            telegram_handler.send_telegram("❌ Usage: /threshold 1500")

    def _cmd_multiplier(self, text):
        """Change a zone multiplier via Telegram"""
        zones = {'above': ('EMA_ABOVE_MULTIPLIER', '📈 Above EMA'),
                 'weak': ('EMA_WEAK_MULTIPLIER', '🔹 Weak Dip'),
                 'normal': ('EMA_NORMAL_MULTIPLIER', '🟢 Normal Dip'),
                 'strong': ('EMA_STRONG_MULTIPLIER', '🔥 Strong Dip')}
        try:
            parts = text.split()
            zone = parts[1].lower()
            val = float(parts[2].replace(',', '.'))
            if zone not in zones or not (0 < val <= 3): raise ValueError
            key, label = zones[zone]
            setattr(config, key, val)
            self.config_overrides[key] = val
            self._save_state()
            example = min(config.FIXED_GRID_AMOUNT * val, config.MAX_BUY_USDT)
            telegram_handler.send_telegram(
                f"✅ <b>{label} multiplier:</b> {val}x\n"
                f"💵 Buy in fixed mode: ${example:.0f} (cap ${config.MAX_BUY_USDT:.0f})")
        except (IndexError, ValueError):
            telegram_handler.send_telegram(
                "❌ Usage: /multiplier [zone] [value]\n"
                "Zones: above, weak, normal, strong\n"
                "e.g. /multiplier normal 1.3")

    def _cmd_help(self):
        msg = ("📋 <b>COMMANDS</b>\n"
               "/status - General status\n"
               "/positions - Open positions\n"
               "/stats - Statistics\n"
               "/report - Daily/weekly/monthly summary\n"
               "/settings - Buy settings (threshold/multipliers)\n"
               "/threshold [amount] - Change threshold\n"
               "/multiplier [zone] [value] - Change multiplier\n"
               "/commission - Real commission report\n"
               "/sellall - Sell all\n"
               "/sell [id] - Sell specific\n"
               "/start /pause /shutdown /reset")
        telegram_handler.send_telegram(msg)

    def calculate_ema(self):
        if len(self.price_history) < config.EMA_PERIOD: return None
        prices = list(self.price_history)
        multiplier = 2 / (config.EMA_PERIOD + 1)
        ema = sum(prices[:config.EMA_PERIOD]) / config.EMA_PERIOD
        for price in prices[config.EMA_PERIOD:]: ema = (price * multiplier) + (ema * (1 - multiplier))
        self.ema_value = ema
        return ema

    def check_hybrid_filter(self, current_price):
        if not config.HYBRID_MODE or self.ema_value is None: return True, "ok", 1.0
        deviation = ((current_price - self.ema_value) / self.ema_value) * 100
        if deviation >= config.EMA_ZONE_EXPENSIVE: return False, "expensive", 0
        if deviation >= 0: return True, "above_ema", config.EMA_ABOVE_MULTIPLIER
        if deviation >= config.EMA_ZONE_WEAK: return True, "weak_dip", config.EMA_WEAK_MULTIPLIER
        if deviation >= config.EMA_ZONE_NORMAL: return True, "normal_dip", config.EMA_NORMAL_MULTIPLIER
        if deviation >= config.EMA_ZONE_STRONG: return True, "strong_dip", config.EMA_STRONG_MULTIPLIER
        return False, "hard_stop", 0

    def get_trend_indicator(self, current_price):
        if self.ema_value is None: return "⏳ ..."
        dev = ((current_price - self.ema_value) / self.ema_value) * 100
        if dev >= config.EMA_ZONE_EXPENSIVE: return f"🚫 Expensive (+{dev:.1f}%) ❌"
        if dev >= 1: return f"📈 Uptrend (+{dev:.1f}%) {config.EMA_ABOVE_MULTIPLIER}x"
        if dev >= 0: return f"📊 Neutral ({dev:.1f}%) {config.EMA_ABOVE_MULTIPLIER}x"
        if dev >= config.EMA_ZONE_WEAK: return f"🔹 Weak Dip ({dev:.1f}%) {config.EMA_WEAK_MULTIPLIER}x"
        if dev >= config.EMA_ZONE_NORMAL: return f"🟢 Normal Dip ({dev:.1f}%) {config.EMA_NORMAL_MULTIPLIER}x"
        if dev >= config.EMA_ZONE_STRONG: return f"🔥 Strong Dip ({dev:.1f}%) {config.EMA_STRONG_MULTIPLIER}x"
        return f"🔴 Hard Stop ({dev:.1f}%) ❌"

    def _create_grids(self, center_price):
        self.grids = []
        
        # Per-grid investment amount calculation
        # Threshold logic: if balance is ABOVE FIXED_AMOUNT_THRESHOLD, use the fixed base
        # (lots of cash → brake so buys don't grow). If BELOW, buy proportionally to the current balance.
        fixed_amount = getattr(config, 'FIXED_GRID_AMOUNT', 0)
        threshold = getattr(config, 'FIXED_AMOUNT_THRESHOLD', 0)
        if fixed_amount > 0 and self.balance_usdt > threshold:
            amount_per_grid = fixed_amount
        elif config.AUTO_COMPOUND:
            # Balance below threshold → distribute current USDT across grids proportionally
            # Orphan positions' value is already held as ETH
            available_for_grids = self.balance_usdt
            amount_per_grid = available_for_grids / config.GRID_COUNT
        else:
            amount_per_grid = config.INVESTMENT / config.GRID_COUNT

        step = (center_price * config.GRID_SPREAD * 2) / config.GRID_COUNT
        lower = center_price * (1 - config.GRID_SPREAD)
        # Float rounding tolerance: at some prices the center line (price == center_price) was
        # wrongly counted as "below price" due to floating-point error and turned green.
        # A relative epsilon keeps the center line always empty → consistent grid count.
        epsilon = center_price * 1e-9
        for i in range(config.GRID_COUNT + 1):
            price = lower + (step * i)
            # Safety Check: Ensure amount per grid is not below Binance minimum (~$10)
            safe_amount = max(amount_per_grid, 10.5)
            self.grids.append({'id': i, 'price': price, 'amount_usdt': safe_amount, 'status': 'waiting_buy' if price < center_price - epsilon else 'empty'})
        
        # Mark old positions as orphans (independent from grids)
        # These positions continue to sell at their own sell_target/trailing targets
        for pos in self.open_positions:
            pos['grid_id'] = -1  # Orphan position (no longer tied to a grid)
            
        self._save_state()

    def _open_position(self, grid, price, timestamp, buy_multiplier=1.0):
        adjusted_amount = grid['amount_usdt'] * buy_multiplier
        # Hard cap: can never exceed MAX_BUY_USDT, even after the multiplier (safety brake)
        max_buy = getattr(config, 'MAX_BUY_USDT', 0)
        if max_buy > 0:
            adjusted_amount = min(adjusted_amount, max_buy)
        adjusted_amount = max(adjusted_amount, 10.5)  # Binance minimum
        crypto = adjusted_amount / price
        # Real Order Submission
        if not config.PAPER_TRADING:
            order = self.exchange_handler.place_order(config.SYMBOL, 'buy', crypto)
            if not order:
                print(f"{Colors.error('❌ Real buy order failed!')}")
                return
            # Update with actual filled price and amount
            price = order.get('average', order.get('price', price))
            crypto = order.get('filled', crypto)
            cost = order.get('cost', crypto * price)
            
            # Commission Calculation (BNB or Base Asset?)
            fee_cost = 0.0
            fee_currency = ""
            if 'fee' in order and order['fee']:
                fee_cost = order['fee'].get('cost', 0.0)
                fee_currency = order['fee'].get('currency', "")
                
            # Update balance based on commission type
            base_asset = config.SYMBOL.split('/')[0]
            if fee_currency == base_asset:
                # Fee deducted in ETH - actual received crypto reduced
                crypto -= fee_cost
                fee = fee_cost * price  # In USDT for statistics
            elif fee_currency == 'USDT':
                cost += fee_cost
                fee = fee_cost
            elif fee_currency == 'BNB':
                # Deducted from BNB, crypto and USDT unaffected
                fee = cost * 0.00075  # Approximate USDT value
            else:
                fee = cost * 0.00075

            self.balance_usdt -= cost
            self.balance_eth += crypto
            
        else:
            # Paper Trading
            cost = adjusted_amount
            fee = cost * 0.001
            self.balance_usdt -= (cost + fee)
            self.balance_eth += crypto

        self.total_commission += fee
        for _p in ('daily_stats', 'weekly_stats', 'monthly_stats'):
            self.stats[_p]['commission'] += fee
            self.stats[_p]['trades'] += 1
            self.stats[_p]['buys'] += 1
        grid['status'] = 'filled'
        self.position_counter += 1
        pos = {
            'id': self.position_counter,
            'grid_id': grid['id'],
            'grid_price': grid['price'],
            'buy_price': price,
            'entry_cost': cost,
            'buy_fee': fee,
            'crypto_amount': crypto,
            'sell_target': price * (1 + config.TRAILING_PROFIT_PCT/100),
            'buy_time': timestamp,
            'highest_price': price,
            'is_trailing': False
        }
        self.open_positions.append(pos)
        self.stats['total_buys'] += 1
        self.filled_orders.append({'type': 'buy', 'id': pos['id'], 'price': price, 'time': timestamp})
        
        # Prevent state bloat: Keep only last 100 orders
        if len(self.filled_orders) > 100:
            self.filled_orders = self.filled_orders[-100:]
            
        self._save_state()
        sell_target = pos['sell_target']
        target_pct = config.TRAILING_PROFIT_PCT
        # Zone label
        if buy_multiplier <= 0.5:
            zone_label = "📈 Above EMA"
        elif buy_multiplier <= 0.75:
            zone_label = "🔹 Weak Dip"
        elif buy_multiplier >= 1.5:
            zone_label = "🔥 Strong Dip"
        else:
            zone_label = "🟢 Normal"
        msg = (f"━━━━━━━━━━━━━━━━━━━\n"
               f"🟢 <b>BUY</b> #{pos['id']}\n"
               f"━━━━━━━━━━━━━━━━━━━\n"
               f"💵 Amount: ${cost:.2f} ({buy_multiplier}x {zone_label})\n"
               f"📍 Price: ${price:,.2f}\n"
               f"💸 Commission: ${fee:.4f}\n"
               f"🎯 Target: ${sell_target:,.2f} (+{target_pct}%)\n"
               f"━━━━━━━━━━━━━━━━━━━")
        telegram_handler.send_telegram(msg)

    def _close_position(self, pos, price, timestamp, reason):
        sell_amount = pos['crypto_amount']

        # Check real balance - balance may be insufficient due to ETH fee deductions
        if not config.PAPER_TRADING:
            base_asset = config.SYMBOL.split('/')[0]
            real_balance = self.exchange_handler.get_balance(base_asset)
            if real_balance < sell_amount:
                # If balance is less than 50% of the position, it was already sold (manually or otherwise)
                if real_balance < sell_amount * 0.5:
                    print(f"{Colors.warning('⚠️ Position #' + str(pos['id']) + ' appears to be already sold (balance: ' + str(real_balance) + ')')}")
                    # Clean up position from state (for orphan positions grid_id = -1, skip)
                    if pos.get('grid_id', -1) != -1:
                        for g in self.grids:
                            if g['id'] == pos['grid_id']:
                                g['status'] = 'waiting_buy'
                                break
                    if pos in self.open_positions:
                        self.open_positions.remove(pos)
                    self._save_state()
                    telegram_handler.send_telegram(f"⚠️ Position #{pos['id']} was already sold, state cleaned up.")
                    return
                # Small difference (fee deduction) - sell what we have
                sell_amount = float(f"{real_balance:.5f}")
                if sell_amount <= 0:
                    print(f"{Colors.error('❌ Insufficient ' + base_asset + ' balance!')}")
                    return

        usdt_val = sell_amount * price
        net_usdt = usdt_val  # Default: full amount if no fee

        # Real Order Submission
        if not config.PAPER_TRADING:
            order = self.exchange_handler.place_order(config.SYMBOL, 'sell', sell_amount)
            if not order:
                print(f"{Colors.error('❌ Real sell order failed!')}")
                return
            # Update with actual filled price
            price = order.get('average', order.get('price', price))
            usdt_val = order.get('cost', pos['crypto_amount'] * price)
            
            fee_cost = 0.0
            fee_currency = ""
            if 'fee' in order and order['fee']:
                fee_cost = order['fee'].get('cost', 0.0)
                fee_currency = order['fee'].get('currency', "")

            # USDT is received on sell.
            # If fee is USDT, net received = usdt_val - fee
            if fee_currency == 'USDT':
                net_usdt = usdt_val - fee_cost
                fee = fee_cost
            else:
                # If fee is BNB, full USDT balance is received (usdt_val)
                net_usdt = usdt_val
                # Approximate fee for statistics (if BNB)
                fee = usdt_val * 0.00075

            self.balance_usdt += net_usdt
            self.balance_eth -= sell_amount

        else:
            fee = usdt_val * 0.001
            net_usdt = usdt_val - fee
            self.balance_usdt += net_usdt
            self.balance_eth -= sell_amount

        # Net profit = gross - commission. (When fees are paid in BNB, net_usdt == usdt_val, so
        # total_profit used to record the gross amount; now it matches the net shown in Telegram)
        entry_cost = pos.get('entry_cost', pos['buy_price'] * pos['crypto_amount'])
        gross_profit = usdt_val - entry_cost
        net_profit = gross_profit - fee
        profit = net_profit
        self.total_commission += fee
        self.total_profit += profit
        for _p in ('daily_stats', 'weekly_stats', 'monthly_stats'):
            self.stats[_p]['profit'] += profit
            self.stats[_p]['commission'] += fee
            self.stats[_p]['trades'] += 1
            self.stats[_p]['sells'] += 1

        self.stats['total_sells'] += 1
        self.filled_orders.append({'type': 'sell', 'id': pos['id'], 'price': price, 'profit': profit, 'time': timestamp})
        
        # Prevent state bloat: Keep only last 100 orders
        if len(self.filled_orders) > 100:
            self.filled_orders = self.filled_orders[-100:]
        
        # Reactivate the grid (for orphan positions grid_id = -1, skip)
        if pos.get('grid_id', -1) != -1:
            for g in self.grids:
                if g['id'] == pos['grid_id']:
                    g['status'] = 'waiting_buy'
                    break
            
        if pos in self.open_positions:
            self.open_positions.remove(pos)
            
        self._save_state()

        # gross_profit, net_profit, entry_cost computed above (identical to what total_profit records)
        pnl_pct = ((price/pos['buy_price'])-1)*100
        emoji = "💰" if net_profit >= 0 else "📉"
        net_emoji = '✅' if net_profit >= 0 else '❌'
        msg = (f"━━━━━━━━━━━━━━━━━━━\n"
               f"{emoji} <b>SELL</b> #{pos['id']}\n"
               f"━━━━━━━━━━━━━━━━━━━\n"
               f"💵 Amount: ${usdt_val:.2f}\n"
               f"🛒 Buy: ${pos['buy_price']:,.2f}\n"
               f"📍 Sell: ${price:,.2f}\n"
               f"📊 Gross: ${gross_profit:+.2f} ({pnl_pct:+.2f}%)\n"
               f"💸 Commission: ${fee:.2f}\n"
               f"{net_emoji} Net: ${net_profit:+.2f}\n"
               f"📋 Reason: {reason}\n"
               f"━━━━━━━━━━━━━━━━━━━")
        telegram_handler.send_telegram(msg)

    def _sync_balances(self):
        """Check and sync Binance balance every 5 minutes"""
        now = time.time()
        if now - self.last_sync_time < 300:  # 5 minutes
            return
        self.last_sync_time = now
        try:
            real_usdt = self.exchange_handler.get_balance('USDT')
            base_asset = config.SYMBOL.split('/')[0]
            real_crypto = self.exchange_handler.get_balance(base_asset)

            usdt_diff = abs(real_usdt - self.balance_usdt)
            crypto_diff = abs(real_crypto - self.balance_eth)

            # Only update if there is a meaningful difference (USDT $0.10+, ETH 0.00001+)
            if usdt_diff > 0.10 or crypto_diff > 0.00001:
                self.balance_usdt = real_usdt
                self.balance_eth = real_crypto
                self._save_state()
                print(f"\n{Colors.info('🔄 Balance synced: $' + f'{real_usdt:.2f}' + ' USDT, ' + f'{real_crypto:.6f}' + ' ' + base_asset)}")

            # BNB balance check - auto-buy if low
            bnb_balance = self.exchange_handler.get_balance('BNB')
            bnb_price = self.exchange_handler.get_current_price('BNB/USDT')
            bnb_usd = bnb_balance * bnb_price if bnb_balance > 0 and bnb_price else 0
            if bnb_usd < 5.0:
                if not self.bnb_low_notified:
                    if self.balance_usdt > 100 and bnb_price:
                        buy_usd = 20.0
                        bnb_amount = round(buy_usd / bnb_price, 3)
                        order = self.exchange_handler.place_order('BNB/USDT', 'buy', bnb_amount)
                        if order:
                            msg = (f"🤖 <b>BNB AUTO-PURCHASED</b>\n"
                                   f"──────────────────\n"
                                   f"💰 Bought: {bnb_amount:.3f} BNB (~${buy_usd:.2f})\n"
                                   f"📊 Previous BNB: {bnb_balance:.5f} (~${bnb_usd:.2f})\n"
                                   f"💡 Purchased to maintain commission discount.")
                            telegram_handler.send_telegram(msg)
                        else:
                            msg = (f"⚠️ <b>BNB PURCHASE FAILED</b>\n"
                                   f"──────────────────\n"
                                   f"💰 BNB: {bnb_balance:.5f} (~${bnb_usd:.2f})\n"
                                   f"💡 Please top up BNB manually.")
                            telegram_handler.send_telegram(msg)
                    else:
                        msg = (f"⚠️ <b>BNB LOW - INSUFFICIENT USDT</b>\n"
                               f"──────────────────\n"
                               f"💰 BNB: {bnb_balance:.5f} (~${bnb_usd:.2f})\n"
                               f"💵 USDT: ${self.balance_usdt:.2f} (insufficient for auto-buy)\n"
                               f"💡 Please top up BNB manually.")
                        telegram_handler.send_telegram(msg)
                    self.bnb_low_notified = True
            else:
                self.bnb_low_notified = False
        except Exception as e:
            print(f"{Colors.warning('⚠️ Balance sync error: ' + str(e))}")

    def check_and_execute(self):
        curr_price = self.exchange_handler.get_current_price(config.SYMBOL)
        if not curr_price: return
        self.current_price = curr_price
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.process_telegram_commands(timeout=0)
        if self.paused: return

        # Balance sync (every 5 min)
        if not config.PAPER_TRADING:
            self._sync_balances()

        # EMA update (from 15-minute candles, every 15 minutes)
        if time.time() - self.last_ema_update >= 900:
            self._update_ema_from_candles()

        # 1. Check Positions (Sell / Trailing)
        # First handle trailing activations and highest price updates
        sell_candidates = []  # (pos, profit_pct) - positions that hit callback
        for pos in self.open_positions[:]:
            # Check if Trailing phase started
            if not pos['is_trailing'] and curr_price >= pos['sell_target']:
                pos['is_trailing'] = True
                pos['highest_price'] = curr_price  # Start tracking from trailing activation price
                pos['trailing_notify_level'] = 1
                callback_lock = curr_price * (1 - config.TRAILING_CALLBACK_PCT/100)
                pos_cost = pos.get('entry_cost', pos['buy_price'] * pos['crypto_amount'])
                pos_value = pos['crypto_amount'] * curr_price
                msg = (f"━━━━━━━━━━━━━━━━━━━\n"
                       f"🎯 <b>TRAILING ACTIVE</b> #{pos['id']}\n"
                       f"━━━━━━━━━━━━━━━━━━━\n"
                       f"📍 Price: ${curr_price:,.2f}\n"
                       f"💵 Position: ${pos_cost:.2f} → ${pos_value:.2f}\n"
                       f"🔒 Lock: ${callback_lock:,.2f} (-{config.TRAILING_CALLBACK_PCT}%)\n"
                       f"━━━━━━━━━━━━━━━━━━━")
                telegram_handler.send_telegram(msg)
                print(f"\n{Colors.success('🚀 Trailing started: #' + str(pos['id']))}")

            # If trailing: update highest price at +1.2% steps only (step-based)
            # Keeps lock stable on small moves — gives positions breathing room
            if pos['is_trailing']:
                notify_level = pos.get('trailing_notify_level', 1)
                next_threshold = pos['buy_price'] * (1 + config.TRAILING_PROFIT_PCT * (notify_level + 1) / 100)
                if curr_price >= next_threshold:
                    # Crossed a step: raise highest price and lock, send notification
                    pos['highest_price'] = curr_price
                    pos['trailing_notify_level'] = notify_level + 1
                    profit_pct = ((curr_price - pos['buy_price']) / pos['buy_price']) * 100
                    new_callback = curr_price * (1 - config.TRAILING_CALLBACK_PCT/100)
                    pos_cost = pos.get('entry_cost', pos['buy_price'] * pos['crypto_amount'])
                    pos_value = pos['crypto_amount'] * curr_price
                    msg = (f"🔄 <b>TRAILING UPDATED</b> #{pos['id']}\n"
                           f"──────────────────\n"
                           f"📈 New High: ${curr_price:,.2f}\n"
                           f"💵 Position: ${pos_cost:.2f} → ${pos_value:.2f}\n"
                           f"🔒 New Lock: ${new_callback:,.2f}\n"
                           f"💰 Profit: {profit_pct:.1f}%")
                    telegram_handler.send_telegram(msg)

                callback_price = pos['highest_price'] * (1 - config.TRAILING_CALLBACK_PCT/100)
                if curr_price <= callback_price:
                    profit_pct = ((curr_price - pos['buy_price']) / pos['buy_price']) * 100
                    sell_candidates.append((pos, profit_pct))

        # Sell only 1 position per cycle (most profitable one)
        # Others are checked next cycle — if price recovers, they may be saved
        if sell_candidates:
            sell_candidates.sort(key=lambda x: x[1], reverse=True)
            best_pos = sell_candidates[0][0]
            self._close_position(best_pos, curr_price, timestamp, "Trailing Stop")

        # 2. Check Grids (Buy)
        can_buy, buy_reason, buy_multiplier = self.check_hybrid_filter(curr_price)
        
        # Trend Notification (One-time)
        if not can_buy and not self.trend_block_notified:
            msg = (f"🚨 <b>TREND WARNING</b>\n"
                   f"──────────────────\n"
                   f"⚠️ Market has entered a sharp decline zone.\n"
                   f"🛡️ New buys STOPPED for safety.\n"
                   f"📍 Price: ${curr_price:,.2f} | EMA: ${self.ema_value:,.2f}")
            telegram_handler.send_telegram(msg)
            self.trend_block_notified = True
        elif can_buy and self.trend_block_notified:
            msg = (f"✅ <b>TREND RECOVERED</b>\n"
                   f"──────────────────\n"
                   f"🟢 Market has returned to the safe zone.\n"
                   f"🚀 Buys re-enabled.\n"
                   f"📍 Price: ${curr_price:,.2f}")
            telegram_handler.send_telegram(msg)
            self.trend_block_notified = False

        # Grid Buy Check (no position limit — swap kicks in when cash drops below $50)
        for grid in sorted(self.grids, key=lambda x: x['price'], reverse=True):
            if grid['status'] == 'waiting_buy' and curr_price <= grid['price']:
                if can_buy:
                    adjusted_amount = grid['amount_usdt'] * buy_multiplier
                    max_buy = getattr(config, 'MAX_BUY_USDT', 0)
                    if max_buy > 0:
                        adjusted_amount = min(adjusted_amount, max_buy)
                    adjusted_amount = max(adjusted_amount, 10.5)  # Binance minimum
                    if self.balance_usdt < config.MIN_CASH_BEFORE_REBALANCING:
                        if config.ENABLE_REBALANCING:
                            self._check_for_rebalancing_swap(grid, curr_price, timestamp)
                    elif self.balance_usdt >= adjusted_amount:
                        self._open_position(grid, curr_price, timestamp, buy_multiplier)
                else:
                    self.stats['blocked_by_trend'] += 1
        
        # 3. Grid Out-of-Range Check
        if config.AUTO_GRID_RESET:
            self._check_grid_out_of_range(curr_price)
            
        # 4. Daily Report Check
        if config.DAILY_REPORT_ENABLED:
            self._check_daily_report()
                    
        total = self.balance_usdt + (self.balance_eth * curr_price)
        pnl = total - config.INVESTMENT
        print(f"\r[{timestamp}] v{self.version} | Price: ${curr_price:,.2f} | P/L: ${pnl:+.2f} | Pos: {len(self.open_positions)}", end="")

    def _send_period_report(self, title, emoji, period_label, stats_key, footer):
        """Shared report sender (daily/weekly/monthly)"""
        s = self.stats[stats_key]
        portfolio = self.balance_usdt + (self.balance_eth * self.current_price)
        msg = (f"{emoji} <b>{title}</b> ({period_label})\n"
               f"──────────────────\n"
               f"💰 <b>Net Profit:</b> ${s['profit']:+.2f}\n"
               f"💸 <b>Commission:</b> ${s['commission']:.2f}\n"
               f"🟢 <b>Buys:</b> {s.get('buys', 0)} | 🔴 <b>Sells:</b> {s.get('sells', 0)}\n"
               f"🔄 <b>Total Trades:</b> {s['trades']}\n"
               f"──────────────────\n"
               f"💹 <b>Total Portfolio:</b> ${portfolio:.2f}\n\n"
               f"{footer}")
        telegram_handler.send_telegram(msg)

    def _check_daily_report(self):
        # Daily report
        today = datetime.now(TZ_UTC).strftime("%Y-%m-%d")
        if today != self.last_report_date:
            self._send_period_report("DAILY SUMMARY REPORT", "📅", self.last_report_date,
                                     'daily_stats', "🚀 May the new day bring great profits!")
            self.stats['daily_stats'] = {'profit': 0.0, 'commission': 0.0, 'trades': 0, 'buys': 0, 'sells': 0}
            self.last_report_date = today
            self._save_state()

        # Weekly report (at the start of each new week)
        this_week = datetime.now(TZ_UTC).strftime("%Y-W%W")
        if this_week != self.last_week:
            self._send_period_report("WEEKLY SUMMARY REPORT", "📆", self.last_week,
                                     'weekly_stats', "📊 Have a great new week!")
            self.stats['weekly_stats'] = {'profit': 0.0, 'commission': 0.0, 'trades': 0, 'buys': 0, 'sells': 0}
            self.last_week = this_week
            self._save_state()

        # Monthly report (at the start of each new month)
        this_month = datetime.now(TZ_UTC).strftime("%Y-%m")
        if this_month != self.last_month:
            self._send_period_report("MONTHLY SUMMARY REPORT", "🗓️", self.last_month,
                                     'monthly_stats', "🎯 May the new month bring great profits!")
            self.stats['monthly_stats'] = {'profit': 0.0, 'commission': 0.0, 'trades': 0, 'buys': 0, 'sells': 0}
            self.last_month = this_month
            self._save_state()

    def _check_for_rebalancing_swap(self, grid, current_price, timestamp, reason="balance"):
        if not self.open_positions: return

        # Check if price has dropped at least X% from last position's price (Safety Distance)
        last_pos = self.open_positions[-1]
        dist = ((current_price - last_pos['buy_price']) / last_pos['buy_price']) * 100

        if dist <= -config.REBALANCING_MIN_DISTANCE_PCT:
            # Find the highest (most expensive) position
            highest_pos = max(self.open_positions, key=lambda x: x['buy_price'])

            # No need if the new swap price is higher than the old price
            if current_price >= highest_pos['buy_price']: return

            print(f"\n{Colors.warning('🔄 SWAP TRIGGERED: Sacrificing top position #' + str(highest_pos['id']))}")

            # 1. Sell the top one (Free up balance)
            self._close_position(highest_pos, current_price, timestamp, "SWAP (Sell)")

            # 2. Buy at the bottom (Open new position)
            # Note: Balance is updated after _close_position so we can buy now
            if self.balance_usdt >= grid['amount_usdt']:
                self._open_position(grid, current_price, timestamp)
                # Special Telegram Message
                reason_text = f"Cash dropped below ${config.MIN_CASH_BEFORE_REBALANCING:.0f}, top position sacrificed."
                msg = (f"🔄 <b>SWAP (Rebalancing) COMPLETED!</b>\n\n"
                       f"📍 {reason_text}\n"
                       f"❌ Sold: #{highest_pos['id']} (${highest_pos['buy_price']:,.2f})\n"
                       f"✅ New Buy: ${current_price:,.2f}\n"
                       f"🎯 Cost basis pulled much lower!")
                telegram_handler.send_telegram(msg)

    def _check_grid_out_of_range(self, current_price):
        if not self.grids: return
        
        lower_bound = self.grids[0]['price']
        upper_bound = self.grids[-1]['price']
        
        # Grid out-of-range threshold (e.g., 2%)
        margin = (upper_bound - lower_bound) * (config.GRID_OUT_OF_RANGE_PCT / 100)
        
        if current_price < (lower_bound - margin) or current_price > (upper_bound + margin):
            if not self.grid_out_of_range_notified:
                direction = "Moved Up" if current_price > upper_bound else "Moved Down"
                dir_emoji = "🚀" if current_price > upper_bound else "🔻"
                self._create_grids(current_price)
                new_lower = self.grids[0]['price']
                new_upper = self.grids[-1]['price']
                msg = (f"━━━━━━━━━━━━━━━━━━━\n"
                       f"🔄 <b>GRID RESET</b>\n"
                       f"━━━━━━━━━━━━━━━━━━━\n"
                       f"📍 New Center: ${current_price:,.2f}\n"
                       f"📊 Range: ${new_lower:,.0f} - ${new_upper:,.0f}\n"
                       f"{dir_emoji} Direction: {direction}\n"
                       f"━━━━━━━━━━━━━━━━━━━")
                telegram_handler.send_telegram(msg)
                self.grid_out_of_range_notified = True
                print(f"\n{Colors.warning(f'🔄 Price out of grid range ({direction}), grids reset.')}")
        else:
            # Hysteresis: Don't reset if close to grid boundary, wait until price moves far enough inside
            if self.grid_out_of_range_notified:
                hysteresis = margin * 2
                if (lower_bound + hysteresis) < current_price < (upper_bound - hysteresis):
                    self.grid_out_of_range_notified = False

    def _update_ema_from_candles(self):
        """Update EMA from 15-minute candles"""
        try:
            ohlcv = self.exchange_handler.fetch_ohlcv(config.SYMBOL, timeframe='15m', limit=config.EMA_PERIOD)
            if ohlcv:
                self.price_history.clear()
                for c in ohlcv:
                    self.price_history.append(c[4])
                self.calculate_ema()
                self.last_ema_update = time.time()
        except Exception as e:
            print(f"{Colors.warning('⚠️ EMA update error: ' + str(e))}")

    def run(self):
        # OHLCV for initial EMA (15-minute candles)
        self._update_ema_from_candles()

        # If grids empty, create them
        if not self.grids:
            self._create_grids(self.exchange_handler.get_current_price(config.SYMBOL))

        self._print_keyboard_help()
        print(f"\n{Colors.success('🚀 Bot v' + self.version + ' Running...')}")
        while self.running:
            try:
                self.check_and_execute()
                # Check Telegram every 3 seconds
                for i in range(config.CHECK_INTERVAL * 2):
                    if not self.running: break
                    if i % 6 == 0:  # Every 6 iterations = every 3 seconds
                        self.process_telegram_commands(timeout=0)
                    time.sleep(0.5)
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                print(f"\n{Colors.error('⚠️ Error: ' + str(e))}")
                time.sleep(5)
