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
        
        # Local state (non-persistent)
        self.current_price = 0
        self.last_sync_time = 0  # Balance sync timestamp
        self.price_history = deque(maxlen=config.EMA_PERIOD * 2)
        self.ema_value = None
        self.stats = {
            'total_buys': 0, 'total_sells': 0, 'blocked_by_trend': 0,
            'dip_buys': 0, 'max_drawdown': 0, 'winning_trades': 0, 'losing_trades': 0,
            'total_commission': 0.0,
            'daily_stats': {'profit': 0.0, 'commission': 0.0, 'trades': 0}
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
        print(f"{Colors.CYAN}║  {Colors.BOLD}{Colors.WHITE}🤖 SMART GRID BOT v{self.version} - DCA MOD (Persistence){Colors.RESET}{Colors.CYAN}             ║{Colors.RESET}")
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
        print(f"   /status /positions /stats /grids /start /pause /shutdown /reset /help")
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
            elif text == '/sellall': self._cmd_sellall()
            elif text.startswith('/sell '): self._cmd_sell_specific(text)
            elif text == '/shutdown': self._cmd_shutdown()

    def _get_real_commission(self):
        """Fetch real commission data from Binance (all trades)"""
        try:
            trades = self.exchange_handler.fetch_all_my_trades(config.SYMBOL)
            if not trades:
                return None
            total_fee_usdt = 0.0
            for t in trades:
                fee = t.get('fee', {})
                fc = fee.get('cost', 0.0) or 0.0
                curr = fee.get('currency', '')
                if curr == 'USDT':
                    total_fee_usdt += fc
                elif curr == 'BNB':
                    # Calculate BNB fee as USDT using trade-time rate
                    # Standard BNB discounted fee rate: 0.075%
                    trade_cost = t.get('cost', 0)
                    if trade_cost:
                        total_fee_usdt += trade_cost * 0.00075
                else:
                    price = t.get('price', 0)
                    if price:
                        total_fee_usdt += fc * price
            return total_fee_usdt
        except:
            return None

    def _cmd_status(self):
        if not self.current_price: return telegram_handler.send_telegram("❌ Could not fetch price!")
        total_value = self.balance_usdt + (self.balance_eth * self.current_price)
        pnl = total_value - config.INVESTMENT
        pnl_pct = (pnl / config.INVESTMENT) * 100 if config.INVESTMENT > 0 else 0
        runtime = str(datetime.now() - self.start_time).split('.')[0]

        # Fetch real commission from Binance
        real_commission = self._get_real_commission()

        # Gross profit = net profit + estimated commission (bot internal)
        gross_profit_total = self.total_profit + self.total_commission
        commission = real_commission if real_commission is not None else self.total_commission
        net_profit_total = gross_profit_total - commission
        commission_source = "Binance" if real_commission is not None else "Estimate"

        base_asset = config.SYMBOL.split('/')[0]
        crypto_value = self.balance_eth * self.current_price

        bnb_balance = self.exchange_handler.get_balance('BNB')
        bnb_price = self.exchange_handler.get_current_price('BNB/USDT')
        bnb_usd = bnb_balance * bnb_price if bnb_balance > 0 and bnb_price else 0
        bnb_str = f"{bnb_balance:.4f} (~${bnb_usd:.2f}) {'⚠️' if bnb_usd < 5 else ''}"

        ema_str = f"{self.ema_value:,.2f}" if self.ema_value else "0.00"
        msg = (f"📊 <b>BOT STATUS</b> {'⏸️' if self.paused else '✅'}\n\n"
               f"💰 <b>Price:</b> ${self.current_price:,.2f} | 📈 <b>EMA:</b> ${ema_str}\n"
               f"──────────────────\n"
               f"💵 <b>Balance (USDT):</b> ${self.balance_usdt:.2f}\n"
               f"🪙 <b>{base_asset}:</b> {self.balance_eth:.6f} (${crypto_value:.2f})\n"
               f"🔶 <b>BNB (Fee):</b> {bnb_str}\n"
               f"📊 <b>Total Portfolio:</b> ${total_value:.2f}\n"
               f"{'📈' if pnl >= 0 else '📉'} <b>Overall P/L:</b> ${pnl:+.2f} ({pnl_pct:+.2f}%)\n"
               f"──────────────────\n"
               f"💵 <b>Gross Profit:</b> ${gross_profit_total:+.2f}\n"
               f"💸 <b>Commission ({commission_source}):</b> ${commission:.2f}\n"
               f"{'💰' if net_profit_total >= 0 else '📉'} <b>Net Profit:</b> ${net_profit_total:+.2f}\n"
               f"──────────────────\n"
               f"📍 <b>Open Positions:</b> {len(self.open_positions)}"
               f"{' (🔸' + str(sum(1 for p in self.open_positions if p.get('grid_id', -1) == -1)) + ' orphan)' if any(p.get('grid_id', -1) == -1 for p in self.open_positions) else ''}"
               f" | 🟢 <b>Empty Grids:</b> {sum(1 for g in self.grids if g['status'] == 'waiting_buy')}\n"
               f"⏱️ <b>Uptime:</b> {runtime}")
        telegram_handler.send_telegram(msg)

    def _cmd_positions(self):
        if not self.open_positions: return telegram_handler.send_telegram("📍 No open positions.")
        msg = f"📍 <b>OPEN POSITIONS</b>\n\n"
        total_pnl_usd = 0.0
        total_cost = 0.0
        
        for pos in self.open_positions:
            pnl_pct = ((self.current_price - pos['buy_price']) / pos['buy_price']) * 100
            pnl_usd = (self.current_price - pos['buy_price']) * pos['crypto_amount']
            total_pnl_usd += pnl_usd
            cost = pos['buy_price'] * pos['crypto_amount']
            total_cost += cost
            
            orphan_tag = " 🔸" if pos.get('grid_id', -1) == -1 else ""
            msg += f"#{pos['id']}{orphan_tag}: ${pos['buy_price']:,.2f} | <b>Amount: ${cost:.2f}</b> → P/L: ${pnl_usd:+.2f} ({pnl_pct:+.2f}%)\n"
            msg += f"   Sell individual: /sell {pos['id']}\n"
            
        total_pnl_pct = (total_pnl_usd / total_cost) * 100 if total_cost > 0 else 0
        msg += f"\n──────────────────\n"
        msg += f"💰 <b>Total Cost: ${total_cost:.2f}</b>\n"
        msg += f"📊 <b>Total P/L: ${total_pnl_usd:+.2f} ({total_pnl_pct:+.2f}%)</b>"
        telegram_handler.send_telegram(msg)

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

    def _cmd_help(self):
        msg = ("📋 <b>COMMANDS</b>\n"
               "/status - General status\n"
               "/positions - Open positions\n"
               "/stats - Statistics\n"
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
        if deviation >= 0: return True, "above_ema", config.EMA_ABOVE_MULTIPLIER
        if deviation >= config.EMA_ZONE_WEAK: return True, "weak_dip", config.EMA_WEAK_MULTIPLIER
        if deviation >= config.EMA_ZONE_NORMAL: return True, "normal_dip", config.EMA_NORMAL_MULTIPLIER
        if deviation >= config.EMA_ZONE_STRONG: return True, "strong_dip", config.EMA_STRONG_MULTIPLIER
        return False, "hard_stop", 0

    def get_trend_indicator(self, current_price):
        if self.ema_value is None: return "⏳ ..."
        dev = ((current_price - self.ema_value) / self.ema_value) * 100
        if dev >= 1: return f"📈 Uptrend (+{dev:.1f}%) 0.5x"
        if dev >= 0: return f"📊 Neutral ({dev:.1f}%) 0.5x"
        if dev >= config.EMA_ZONE_WEAK: return f"🔹 Weak Dip ({dev:.1f}%) 0.75x"
        if dev >= config.EMA_ZONE_NORMAL: return f"🟢 Normal Dip ({dev:.1f}%) 1x"
        if dev >= config.EMA_ZONE_STRONG: return f"🔥 Strong Dip ({dev:.1f}%) 1.5x"
        return f"🔴 Hard Stop ({dev:.1f}%) ❌"

    def _create_grids(self, center_price):
        self.grids = []
        
        # Per-grid investment amount calculation
        if config.AUTO_COMPOUND:
            # Only distribute current USDT balance across grids
            # Orphan positions' value is already held as ETH
            available_for_grids = self.balance_usdt
            amount_per_grid = available_for_grids / config.GRID_COUNT
        else:
            amount_per_grid = config.INVESTMENT / config.GRID_COUNT
            
        step = (center_price * config.GRID_SPREAD * 2) / config.GRID_COUNT
        lower = center_price * (1 - config.GRID_SPREAD)
        for i in range(config.GRID_COUNT + 1):
            price = lower + (step * i)
            # Safety Check: Ensure amount per grid is not below Binance minimum (~$10)
            safe_amount = max(amount_per_grid, 10.5) 
            self.grids.append({'id': i, 'price': price, 'amount_usdt': safe_amount, 'status': 'waiting_buy' if price < center_price else 'empty'})
        
        # Mark old positions as orphans (independent from grids)
        # These positions continue to sell at their own sell_target/trailing targets
        for pos in self.open_positions:
            pos['grid_id'] = -1  # Orphan position (no longer tied to a grid)
            
        self._save_state()

    def _open_position(self, grid, price, timestamp, buy_multiplier=1.0):
        adjusted_amount = grid['amount_usdt'] * buy_multiplier
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
        self.stats['daily_stats']['commission'] += fee
        self.stats['daily_stats']['trades'] += 1
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

        profit = net_usdt - pos.get('entry_cost', pos['buy_price'] * pos['crypto_amount'])
        self.total_commission += fee
        self.total_profit += profit
        self.stats['daily_stats']['profit'] += profit
        self.stats['daily_stats']['commission'] += fee
        self.stats['daily_stats']['trades'] += 1
        
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
        
        entry_cost = pos.get('entry_cost', pos['buy_price'] * pos['crypto_amount'])
        pnl_pct = ((price/pos['buy_price'])-1)*100
        gross_profit = usdt_val - entry_cost
        net_profit = gross_profit - fee  # Always: gross - commission = real net
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

        # Add current price to history for EMA calculation
        self.price_history.append(curr_price)
        self.calculate_ema()
        
        # 1. Check Positions (Sell / Trailing)
        for pos in self.open_positions[:]:
            # Update highest price if reached
            if curr_price > pos['highest_price']:
                old_highest = pos['highest_price']
                pos['highest_price'] = curr_price

                # Notify on every %1.2 increase while trailing is active
                if pos['is_trailing']:
                    notify_level = pos.get('trailing_notify_level', 1)
                    next_threshold = pos['buy_price'] * (1 + config.TRAILING_PROFIT_PCT * (notify_level + 1) / 100)
                    if curr_price >= next_threshold:
                        pos['trailing_notify_level'] = notify_level + 1
                        profit_pct = ((curr_price - pos['buy_price']) / pos['buy_price']) * 100
                        new_callback = curr_price * (1 - config.TRAILING_CALLBACK_PCT/100)
                        msg = (f"🔄 <b>TRAILING UPDATED</b> #{pos['id']}\n"
                               f"──────────────────\n"
                               f"📈 New High: ${curr_price:,.2f}\n"
                               f"🔒 New Lock: ${new_callback:,.2f}\n"
                               f"💰 Profit: {profit_pct:.1f}%")
                        telegram_handler.send_telegram(msg)
                
            # Check if Trailing phase started
            if not pos['is_trailing'] and curr_price >= pos['sell_target']:
                pos['is_trailing'] = True
                callback_lock = curr_price * (1 - config.TRAILING_CALLBACK_PCT/100)
                msg = (f"━━━━━━━━━━━━━━━━━━━\n"
                       f"🎯 <b>TRAILING ACTIVE</b> #{pos['id']}\n"
                       f"━━━━━━━━━━━━━━━━━━━\n"
                       f"📍 Price: ${curr_price:,.2f}\n"
                       f"🔒 Lock: ${callback_lock:,.2f} (-{config.TRAILING_CALLBACK_PCT}%)\n"
                       f"━━━━━━━━━━━━━━━━━━━")
                telegram_handler.send_telegram(msg)
                print(f"\n{Colors.success('🚀 Trailing started: #' + str(pos['id']))}")
                
            # If trailing, check for callback sell
            if pos['is_trailing']:
                callback_price = pos['highest_price'] * (1 - config.TRAILING_CALLBACK_PCT/100)
                if curr_price <= callback_price:
                    self._close_position(pos, curr_price, timestamp, "Trailing Stop")
            else:
                # Normal target sell logic if price is high enough but we wait for trailing
                pass

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

    def _check_daily_report(self):
        today = datetime.now(TZ_UTC).strftime("%Y-%m-%d")
        if today != self.last_report_date:
            daily = self.stats['daily_stats']
            msg = (f"📅 <b>DAILY SUMMARY REPORT</b> ({self.last_report_date})\n"
                   f"──────────────────\n"
                   f"💰 <b>Net Profit:</b> ${daily['profit']:+.2f}\n"
                   f"💸 <b>Commission:</b> ${daily['commission']:.2f}\n"
                   f"🔄 <b>Trade Count:</b> {daily['trades']}\n"
                   f"──────────────────\n"
                   f"💹 <b>Total Portfolio:</b> ${self.balance_usdt + (self.balance_eth * self.current_price):.2f}\n\n"
                   f"🚀 May the new day bring great profits!")
            telegram_handler.send_telegram(msg)
            
            # Reset daily stats
            self.stats['daily_stats'] = {'profit': 0.0, 'commission': 0.0, 'trades': 0}
            self.last_report_date = today
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

    def run(self):
        # OHLCV for initial EMA
        ohlcv = self.exchange_handler.fetch_ohlcv(config.SYMBOL, limit=config.EMA_PERIOD)
        for c in ohlcv: self.price_history.append(c[4])
        
        # If grids empty, create them
        if not self.grids:
            self._create_grids(self.exchange_handler.get_current_price(config.SYMBOL))
            
        self._print_keyboard_help()
        print(f"\n{Colors.success('🚀 Bot v' + self.version + ' Running...')}")
        while self.running:
            try:
                self.check_and_execute()
                # Check Telegram more frequently (every 0.5 seconds)
                for _ in range(config.CHECK_INTERVAL * 2):
                    if not self.running: break
                    self.process_telegram_commands(timeout=0)
                    time.sleep(0.5)
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                print(f"\n{Colors.error('⚠️ Error: ' + str(e))}")
                time.sleep(5)
