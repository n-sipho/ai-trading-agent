import discord
from discord.ext import commands, tasks
import asyncio
import os
import json
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

import aiohttp
original_init = aiohttp.TCPConnector.__init__
def patched_init(self, *args, **kwargs):
    kwargs['ssl'] = False
    original_init(self, *args, **kwargs)
aiohttp.TCPConnector.__init__ = patched_init

# Import the refactored bot logic
from bot_smc import MT5BotSMC
import strategy_smc

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Setup Discord Intents
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=intents)
client.remove_command("help")

# Global dictionary to hold active bot instances
# format: {"gold_bot": MT5BotSMC()}
active_bots = {}

# Global queue for Discord logs
discord_log_queue = []
processed_deals = set()

def sync_trade_job(bot_name, bot_instance):
    """Synchronous MT5 logic that runs in a separate thread so it doesn't block Discord."""
    print(f"\n--- [{bot_name}] Checking SMC Logic @ {datetime.now()} ---")
    
    # --- HOT-RELOAD CONFIG FROM DISK ---
    filepath = f"bots/{bot_name}.json"
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                new_cfg = json.load(f)
            bot_instance.cfg = new_cfg
        except Exception as e:
            print(f"[{bot_name}] Failed to hot-reload config: {e}")
            
    cfg = bot_instance.cfg
    total_open = bot_instance.get_total_open_trades()
    max_open = cfg.get("MAX_TOTAL_OPEN_TRADES", 2)
    
    if total_open >= max_open:
        print(f"[{bot_name}] Skipping entries: Global max open trades reached ({total_open}/{max_open}).")
        return

    symbols = cfg.get("SYMBOLS", [])
    smt_pairs = cfg.get("SMT_PAIRS", {})
    
    for symbol in symbols:
        print(f"[{bot_name}] Evaluating {symbol}:")
        
        # 1. Fetch HTF Data and get Macro Bias
        htf_tf = cfg.get("HTF_TIMEFRAME", 16388) # H4 default
        df_htf = bot_instance.get_data(symbol, htf_tf, 100)
        if df_htf is None:
            continue
        htf_bias = strategy_smc.get_htf_bias(df_htf, cfg)
        
        # 2. Fetch LTF Data
        ltf_tf = cfg.get("TIMEFRAME", 15)
        df = bot_instance.get_data(symbol, ltf_tf, 200)
        if df is None:
            continue

        # 3. Fetch Correlated Asset for SMT
        df_correlated = None
        smt_pairs = cfg.get('SMT_PAIRS', {})
        if cfg.get('USE_SMT_DIVERGENCE', False) and symbol in smt_pairs:
            correlated_symbol = smt_pairs[symbol]
            df_correlated = bot_instance.get_data(correlated_symbol, ltf_tf, 200)

        signal, sl_price, current_bar = strategy_smc.generate_smc_signals(df, cfg, df_correlated)
        
        # Log market analysis
        os.makedirs("data", exist_ok=True)
        filepath = f"data/{bot_name}_market_analysis.csv"
        
        data = {
            "Time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "Symbol": str(symbol),
            "Close_Price": float(current_bar['close']),
            "ATR": float(current_bar.get('ATR', 0)),
            "High_Volatility": bool(current_bar.get('High_Volatility', False)),
            "In_Kill_Zone": bool(current_bar.get('Active_Kill_Zone', False)),
            "Bullish_OTE": bool(current_bar.get('In_Bullish_OTE', False)),
            "Bearish_OTE": bool(current_bar.get('In_Bearish_OTE', False)),
            "Bullish_FVG": bool(current_bar.get('Recent_Bullish_FVG', False)),
            "Bearish_FVG": bool(current_bar.get('Recent_Bearish_FVG', False)),
            "Bullish_Sweep": bool(current_bar.get('Recent_Bullish_Sweep', False)),
            "Bearish_Sweep": bool(current_bar.get('Recent_Bearish_Sweep', False)),
            "Bullish_SMT": bool(current_bar.get('Recent_Bullish_SMT', False) if df_correlated is not None else False),
            "Bearish_SMT": bool(current_bar.get('Recent_Bearish_SMT', False) if df_correlated is not None else False),
            "HTF_Bias": int(htf_bias),
            "Generated_Signal": int(signal)
        }
        
        # Push to Firestore
        if 'db' in globals() and db is not None:
            try:
                db.collection("market_analysis").add(data)
            except Exception as e:
                print(f"Firestore error: {e}")
        
        df_new = pd.DataFrame([data])
        if os.path.exists(filepath):
            df_new.to_csv(filepath, mode='a', header=False, index=False)
        else:
            df_new.to_csv(filepath, mode='w', header=True, index=False)
        
        # 3. Execute Trade
        import MetaTrader5 as mt5
        if signal == 1:
            if htf_bias == 1:
                print(f"[{bot_name}] SMC Signal: BUY. Executing...")
                if bot_instance.execute_trade(symbol, mt5.ORDER_TYPE_BUY, sl_price):
                    total_open += 1
            else:
                print(f"[{bot_name}] Trade skipped: BUY contradicts HTF Macro Trend.")
        elif signal == -1:
            if htf_bias == -1:
                print(f"[{bot_name}] SMC Signal: SELL. Executing...")
                if bot_instance.execute_trade(symbol, mt5.ORDER_TYPE_SELL, sl_price):
                    total_open += 1
            else:
                print(f"[{bot_name}] Trade skipped: SELL contradicts HTF Macro Trend.")

        if total_open >= max_open:
            break

    # Export history
    bot_instance.export_live_trades_to_csv()

def sync_manage_breakeven():
    """Runs breakeven logic for all active bots."""
    for bot_name, bot_instance in active_bots.items():
        bot_instance.manage_breakeven_stops()

def sync_auto_discover_bots():
    """Scans the bots/ folder and auto-starts any new configs."""
    if not os.path.exists("bots"):
        return
        
    for f in os.listdir("bots"):
        if f.endswith(".json"):
            bot_name = f.replace(".json", "")
            if bot_name not in active_bots:
                filepath = f"bots/{f}"
                try:
                    with open(filepath, "r") as json_file:
                        cfg = json.load(json_file)
                    
                    if cfg.get("IS_ACTIVE", True):
                        print(f"[*] Auto-discovering and starting new bot: {bot_name}")
                        bot = MT5BotSMC(bot_name, cfg)
                        bot.log_queue = discord_log_queue  # Inject the log queue
                        bot.db = db if 'db' in globals() else None
                        if bot.connect():
                            active_bots[bot_name] = bot
                            cfg["IS_ACTIVE"] = True
                            with open(filepath, "w") as out_file:
                                json.dump(cfg, out_file, indent=4)
                        else:
                            print(f"[!] Failed to connect MT5 for {bot_name}. Disabling it.")
                            cfg["IS_ACTIVE"] = False
                            with open(filepath, "w") as out_file:
                                json.dump(cfg, out_file, indent=4)
                except Exception as e:
                    print(f"[!] Error auto-discovering {bot_name}: {e}")

def sync_check_closed_trades():
    """Scans MT5 history for recently closed trades and logs P/L to Discord."""
    import MetaTrader5 as mt5
    from datetime import datetime, timedelta
    
    from_date = datetime.now() - timedelta(days=1)
    to_date = datetime.now() + timedelta(days=1)
    deals = mt5.history_deals_get(from_date, to_date, group="*")
    
    if deals is None:
        return
        
    for deal in deals:
        if deal.ticket in processed_deals:
            continue
            
        processed_deals.add(deal.ticket)
        
        if deal.entry == mt5.DEAL_ENTRY_OUT:
            bot_name = None
            for name, bot in active_bots.items():
                if bot.magic_number == deal.magic:
                    bot_name = name
                    break
                    
            if bot_name:
                profit = deal.profit
                
                # Ignore zero profit deals (like breakeven stops might be slightly off 0 due to slippage, but purely 0 is often a cancelled order)
                if profit > 0:
                    color = discord.Color.green()
                    title = "💰 Trade Closed in Profit!"
                else:
                    color = discord.Color.red()
                    title = "📉 Trade Closed in Loss"
                    
                embed = discord.Embed(title=title, color=color)
                embed.add_field(name="Bot", value=bot_name)
                embed.add_field(name="Symbol", value=deal.symbol)
                embed.add_field(name="Position ID", value=f"#{deal.position_id}")
                embed.add_field(name="Profit/Loss", value=f"${profit:.2f}")
                
                discord_log_queue.append(embed)
                
                if 'db' in globals() and db is not None:
                    doc_data = {
                        "bot_name": bot_name,
                        "symbol": deal.symbol,
                        "position_id": deal.position_id,
                        "profit": float(profit),
                        "time_closed": datetime.now().isoformat(),
                        "status": "PROFIT" if profit > 0 else "LOSS"
                    }
                    try:
                        db.collection("trades").document(str(deal.position_id)).set(doc_data)
                    except Exception as e:
                        print(f"Firestore error: {e}")

@tasks.loop(minutes=15)
async def evaluation_loop():
    """Main trading loop running every 15 minutes."""
    
    if not active_bots:
        return
    # Run synchronously in a thread to prevent blocking the Discord connection
    for bot_name, bot_instance in active_bots.items():
        await asyncio.to_thread(sync_trade_job, bot_name, bot_instance)

_cached_starting_balance = None

def get_starting_balance():
    global _cached_starting_balance
    if _cached_starting_balance is not None:
        return _cached_starting_balance
        
    try:
        import MetaTrader5 as mt5
        from datetime import datetime
        deals = mt5.history_deals_get(datetime(2000, 1, 1), datetime.now())
        if deals:
            total_deposits = sum(d.profit for d in deals if d.type == mt5.DEAL_TYPE_BALANCE)
            if total_deposits > 0:
                _cached_starting_balance = total_deposits
                return total_deposits
    except Exception:
        pass
    return 50000.0

def sync_process_firestore_commands():
    if db is None: return
    try:
        import MetaTrader5 as mt5
        import json
        
        # Poll bot_commands collection
        commands_ref = db.collection('bot_commands')
        docs = commands_ref.get()
        
        for doc in docs:
            data = doc.to_dict()
            cmd = data.get('command')
            
            # Delete the command so it doesn't run twice
            doc.reference.delete()
            
            if cmd == 'CLOSE_ALL':
                print("[Firestore] Executing Panic: CLOSE ALL POSITIONS")
                positions = mt5.positions_get()
                if positions:
                    for pos in positions:
                        close_request = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "position": pos.ticket,
                            "symbol": pos.symbol,
                            "volume": pos.volume,
                            "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                            "price": mt5.symbol_info_tick(pos.symbol).bid if pos.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(pos.symbol).ask,
                            "deviation": 20,
                            "magic": pos.magic,
                            "comment": "Panic Close from Dashboard",
                            "type_time": mt5.ORDER_TIME_GTC,
                            "type_filling": mt5.ORDER_FILLING_IOC,
                        }
                        mt5.order_send(close_request)
                        
            elif cmd == 'BOT_ACTION':
                bot_name = data.get('bot_name')
                action = data.get('action')
                if action == 'START':
                    print(f"[Firestore] Starting bot {bot_name}")
                    config_path = f"bots/{bot_name}.json"
                    if os.path.exists(config_path):
                        with open(config_path, "r") as f:
                            cfg = json.load(f)
                        cfg["IS_ACTIVE"] = True
                        with open(config_path, "w") as f:
                            json.dump(cfg, f, indent=4)
                elif action == 'STOP':
                    print(f"[Firestore] Pausing bot {bot_name}")
                    if bot_name in active_bots:
                        del active_bots[bot_name]
                    config_path = f"bots/{bot_name}.json"
                    if os.path.exists(config_path):
                        with open(config_path, "r") as f:
                            cfg = json.load(f)
                        cfg["IS_ACTIVE"] = False
                        with open(config_path, "w") as f:
                            json.dump(cfg, f, indent=4)
                        
            elif cmd == 'SET_CONFIG':
                bot_name = data.get('bot_name')
                key = data.get('key')
                val = data.get('value')
                print(f"[Firestore] Changing {bot_name} {key} to {val}")
                config_path = f"bots/{bot_name}.json"
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        cfg = json.load(f)
                    cfg[key] = val
                    with open(config_path, "w") as f:
                        json.dump(cfg, f, indent=4)
                    
    except Exception as e:
        print(f"Error processing commands: {e}")

@tasks.loop(seconds=2)
async def firestore_command_loop():
    """Listens for and executes commands sent from the React Dashboard"""
    await asyncio.to_thread(sync_process_firestore_commands)

@tasks.loop(minutes=1)
async def breakeven_loop():
    """Breakeven management loop running every 1 minute."""
    if not active_bots:
        return
    await asyncio.to_thread(sync_manage_breakeven)

def sync_push_trading_logs():
    if db is None: return
    try:
        import MetaTrader5 as mt5
        import firebase_admin.firestore as firestore
        acc_info = mt5.account_info()
        if acc_info is None: return
        
        positions = mt5.positions_get()
        pos_list = []
        if positions:
            for p in positions:
                pos_list.append({
                    'symbol': p.symbol,
                    'type': 'BUY' if p.type == mt5.ORDER_TYPE_BUY else 'SELL',
                    'volume': p.volume,
                    'open': p.price_open,
                    'profit': p.profit
                })
                
        doc_ref = db.collection('trading_logs').document()
        doc_ref.set({
            'timestamp': firestore.SERVER_TIMESTAMP,
            'starting_balance': get_starting_balance(),
            'balance': acc_info.balance,
            'equity': acc_info.equity,
            'margin_level': acc_info.margin_level,
            'free_margin': acc_info.margin_free,
            'profit': acc_info.profit,
            'open_positions': pos_list,
            'active_bots': list(active_bots.keys())
        })
    except Exception as e:
        print(f"Error pushing trading logs: {e}")

@tasks.loop(seconds=5)
async def firestore_publisher_loop():
    """Pushes live account snapshot to Firestore trading_logs"""
    await asyncio.to_thread(sync_push_trading_logs)


@tasks.loop(seconds=5)
async def bot_discovery_loop():
    """Fast loop that scans for new bot configurations instantly."""
    await asyncio.to_thread(sync_auto_discover_bots)

@tasks.loop(seconds=10)
async def closed_trades_loop():
    """Checks for closed trades to report P/L."""
    if not active_bots:
        return
    await asyncio.to_thread(sync_check_closed_trades)

@tasks.loop(seconds=2)
async def discord_log_publisher():
    """Publishes queued logs to the designated Discord channel."""
    if not discord_log_queue:
        return
        
    channel_id = None
    if os.path.exists("log_channel.txt"):
        with open("log_channel.txt", "r") as f:
            try:
                channel_id = int(f.read().strip())
            except:
                pass
                
    if channel_id:
        channel = client.get_channel(channel_id)
        if channel:
            while discord_log_queue:
                embed = discord_log_queue.pop(0)
                try:
                    await channel.send(embed=embed)
                except:
                    discord_log_queue.insert(0, embed)
                    break


@client.event
async def on_ready():
    print(f'Discord Controller logged in as {client.user}')
    
    if not os.path.exists("bots"):
        os.makedirs("bots")
        
    global db
    if not firebase_admin._apps:
        try:
            cred = credentials.Certificate("firebase_credentials.json")
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            print("Firebase connected successfully!")
        except Exception as e:
            print(f"Firebase connection failed: {e}")
            db = None
    else:
        db = firestore.client()
        
    import MetaTrader5 as mt5
    mt5_login = int(os.getenv("MT5_LOGIN", 0))
    mt5_password = os.getenv("MT5_PASSWORD", "")
    mt5_server = os.getenv("MT5_SERVER", "")
    if mt5_login and mt5_password and mt5_server:
        if not mt5.initialize(login=mt5_login, password=mt5_password, server=mt5_server):
            print(f"Global MT5 initialization failed: {mt5.last_error()}")
        else:
            print("Global MT5 connection successfully established.")
    else:
        print("Missing MT5 credentials in .env file.")

    # Perform initial auto-discovery before starting loops
    await asyncio.to_thread(sync_auto_discover_bots)
    
    evaluation_loop.start()
    breakeven_loop.start()
    bot_discovery_loop.start()
    closed_trades_loop.start()
    discord_log_publisher.start()
    firestore_publisher_loop.start()
    firestore_command_loop.start()
    print("Auto-discovery complete. Listening for commands via Discord...")

@client.command()
async def setlogchannel(ctx):
    """Sets the current channel as the dashboard for all bot logs."""
    with open("log_channel.txt", "w") as f:
        f.write(str(ctx.channel.id))
    embed = discord.Embed(title="✅ Dashboard Channel Set", description="All live trade executions and Profit/Loss logs will be sent to this channel.", color=discord.Color.green())
    await ctx.send(embed=embed)

@client.command()
async def help(ctx):
    """Shows the help menu with examples."""
    embed = discord.Embed(
        title="🛠️ SMC Bot Command Center",
        description="Here is a list of all available commands to control your trading bots:",
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name="`!bots`",
        value="Lists all the bot configurations found in your `bots/` folder and shows if they are currently online.\n*Example:* `!bots`",
        inline=False
    )
    
    embed.add_field(
        name="`!status`",
        value="Shows the current active trades and risk settings for every running bot.\n*Example:* `!status`",
        inline=False
    )
    
    embed.add_field(
        name="`!inputs`",
        value="Displays a glossary of all the customizable strategy parameters and how to change them.\n*Example:* `!inputs`",
        inline=False
    )
    
    embed.add_field(
        name="`!inputs`",
        value="Displays a glossary of all the customizable strategy parameters and how to change them.\n*Example:* `!inputs`",
        inline=False
    )
    
    embed.add_field(
        name="`!start <bot_name>`",
        value="Activates a specific bot. The bot must have a matching `.json` file in the `bots/` directory.\n*Example:* `!start gold_bot`",
        inline=False
    )
    
    embed.add_field(
        name="`!stop <bot_name>`",
        value="Safely pauses a bot from taking new trades and disconnects its loop.\n*Example:* `!stop gold_bot`",
        inline=False
    )
    
    embed.add_field(
        name="`!set <bot_name> <parameter> <value>`",
        value="Live-edits a setting inside the bot's JSON configuration without needing to restart it.\n*Example:* `!set gold_bot RISK_PERCENT 2.0`\n*Example:* `!set gold_bot MAX_TOTAL_OPEN_TRADES 3`",
        inline=False
    )
    
    embed.add_field(
        name="`!report <bot_name>`",
        value="Generates and uploads the latest `live_trades.csv` and `market_analysis.csv` files directly to this chat.\n*Example:* `!report gold_bot`",
        inline=False
    )
    
    embed.add_field(
        name="`!create <new_bot_name> <symbol>`",
        value="Easily creates a new bot configuration. The Magic Number is auto-generated!\n*Example:* `!create nasdaq_bot US100`",
        inline=False
    )
    
    embed.set_footer(text="SMC Multi-Bot Controller V1.0")
    await ctx.send(embed=embed)

@client.command()
async def create(ctx, new_bot_name: str, symbol: str):
    """Creates a new bot configuration from an existing template."""
    if not os.path.exists("bots"):
        os.makedirs("bots")
        
    filepath = f"bots/{new_bot_name}.json"
    if os.path.exists(filepath):
        embed = discord.Embed(title="❌ Error", description=f"Bot configuration `{new_bot_name}.json` already exists!", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
        
    # Find a template to copy from (preferably gold_bot, else any)
    template_path = None
    if os.path.exists("bots/gold_bot.json"):
        template_path = "bots/gold_bot.json"
    else:
        files = [f for f in os.listdir("bots") if f.endswith(".json")]
        if files:
            template_path = f"bots/{files[0]}"
            
    if not template_path:
        embed = discord.Embed(title="❌ Error", description="No existing bots found to use as a template. You need at least one baseline bot configuration.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
        
    try:
        import random
        # Ensure unique magic number
        existing_magics = set()
        for f_name in os.listdir("bots"):
            if f_name.endswith(".json"):
                try:
                    with open(f"bots/{f_name}", "r") as temp_f:
                        temp_c = json.load(temp_f)
                        if "MAGIC_NUMBER" in temp_c:
                            existing_magics.add(temp_c["MAGIC_NUMBER"])
                except: pass
                
        while True:
            magic_number = random.randint(100000, 999999)
            if magic_number not in existing_magics:
                break
                
        with open(template_path, "r") as f:
            cfg = json.load(f)
            
        cfg["SYMBOLS"] = [symbol]
        cfg["MAGIC_NUMBER"] = magic_number
        cfg["IS_ACTIVE"] = False
        
        # Ensure friction params exist
        if "COMMISSION_PER_LOT" not in cfg:
            cfg["COMMISSION_PER_LOT"] = 7.0
        if "SPREAD_POINTS" not in cfg:
            cfg["SPREAD_POINTS"] = 15
        if "SLIPPAGE_POINTS" not in cfg:
            cfg["SLIPPAGE_POINTS"] = 5
        
        with open(filepath, "w") as f:
            json.dump(cfg, f, indent=4)
            
        embed = discord.Embed(
            title="✨ Bot Created Successfully", 
            description=f"Created `{new_bot_name}` trading **{symbol}** with Magic Number **{magic_number}**.", 
            color=discord.Color.green()
        )
        embed.add_field(name="Next Steps", value=f"To start this bot, run:\n`!start {new_bot_name}`")
        await ctx.send(embed=embed)
    except Exception as e:
        embed = discord.Embed(title="❌ Error", description=f"Failed to create bot: {e}", color=discord.Color.red())
        await ctx.send(embed=embed)

@client.command()
async def inputs(ctx):
    """Shows a glossary of SMC bot inputs."""
    embed = discord.Embed(
        title="⚙️ SMC Bot Inputs Guide",
        description="These are the settings you can change live using the `!set <bot_name> <parameter> <value>` command.",
        color=discord.Color.dark_purple()
    )
    
    embed.add_field(name="`RISK_PERCENT`", value="Percentage of account balance to risk per trade. (e.g. `1.0`)", inline=False)
    embed.add_field(name="`RR_TARGET`", value="Reward-to-Risk ratio. A value of `2.0` means you aim to make 2x your risk.", inline=False)
    embed.add_field(name="`MAX_TOTAL_OPEN_TRADES`", value="Maximum number of active trades allowed at the same time.", inline=False)
    embed.add_field(name="`USE_BREAKEVEN_STOP`", value="Set to `True` or `False`. Moves stop loss to entry price when trade hits 1:1 risk-reward.", inline=False)
    embed.add_field(name="`USE_VOLATILITY_FILTER`", value="Set to `True` or `False`. Prevents trading if the market is moving too slowly (low ATR).", inline=False)
    embed.add_field(name="`LONDON_KZ_START` / `LONDON_KZ_END`", value="London Kill Zone hours (e.g. `2` and `5`). The bot only takes trades during kill zones.", inline=False)
    embed.add_field(name="`NY_KZ_START` / `NY_KZ_END`", value="New York Kill Zone hours (e.g. `7` and `10`).", inline=False)
    
    embed.add_field(
        name="🛠️ How to Update",
        value="To change the risk on a bot named `gold_bot` to 2%, run:\n`!set gold_bot RISK_PERCENT 2.0`",
        inline=False
    )
    
    await ctx.send(embed=embed)

@client.command()
async def bots(ctx):
    """Lists all available bot configurations in the bots/ folder."""
    if not os.path.exists("bots"):
        await ctx.send("No `bots/` folder found.")
        return
        
    files = [f for f in os.listdir("bots") if f.endswith(".json")]
    if not files:
        await ctx.send("No bot configurations found.")
        return
        
    embed = discord.Embed(title="🤖 Available Bot Configurations", color=discord.Color.blue())
    for f in files:
        name = f.replace(".json", "")
        status = "🟢 ACTIVE" if name in active_bots else "🔴 OFFLINE"
        embed.add_field(name=name, value=status, inline=False)
        
    await ctx.send(embed=embed)

@client.command()
async def start(ctx, bot_name: str):
    """Starts a specific bot instance (e.g. !start gold_bot)."""
    if bot_name in active_bots:
        embed = discord.Embed(title="⚠️ Already Running", description=f"`{bot_name}` is already active.", color=discord.Color.orange())
        await ctx.send(embed=embed)
        return
        
    filepath = f"bots/{bot_name}.json"
    if not os.path.exists(filepath):
        embed = discord.Embed(title="❌ Error", description=f"Configuration `{filepath}` not found.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
        
    try:
        with open(filepath, "r") as f:
            cfg = json.load(f)
            
        bot = MT5BotSMC(bot_name, cfg)
        if await asyncio.to_thread(bot.connect):
            active_bots[bot_name] = bot
            
            # Save IS_ACTIVE state
            cfg["IS_ACTIVE"] = True
            with open(filepath, "w") as f:
                json.dump(cfg, f, indent=4)
                
            embed = discord.Embed(title="✅ Bot Started", description=f"Successfully connected `{bot_name}` to MT5.", color=discord.Color.green())
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="❌ Failed to Connect", description=f"Could not connect `{bot_name}` to MT5. Check terminal logs.", color=discord.Color.red())
            await ctx.send(embed=embed)
    except Exception as e:
        embed = discord.Embed(title="❌ Error", description=f"Error starting bot: {e}", color=discord.Color.red())
        await ctx.send(embed=embed)

@client.command()
async def stop(ctx, bot_name: str):
    """Stops a specific bot instance."""
    if bot_name not in active_bots:
        embed = discord.Embed(title="⚠️ Not Running", description=f"`{bot_name}` is not currently active.", color=discord.Color.orange())
        await ctx.send(embed=embed)
        return
        
    active_bots.pop(bot_name)
    
    # Save IS_ACTIVE state
    filepath = f"bots/{bot_name}.json"
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            cfg = json.load(f)
        cfg["IS_ACTIVE"] = False
        with open(filepath, "w") as f:
            json.dump(cfg, f, indent=4)
            
    embed = discord.Embed(title="🛑 Bot Stopped", description=f"Successfully paused `{bot_name}`.", color=discord.Color.red())
    await ctx.send(embed=embed)

@client.command()
async def status(ctx):
    """Shows the current status of all running bots."""
    if not active_bots:
        embed = discord.Embed(title="🤖 Running Bot Status", description="No bots are currently running.", color=discord.Color.greyple())
        await ctx.send(embed=embed)
        return
        
    embed = discord.Embed(title="🤖 Running Bot Status", color=discord.Color.green())
    for name, bot in active_bots.items():
        open_trades = await asyncio.to_thread(bot.get_total_open_trades)
        risk = bot.cfg.get('RISK_PERCENT', 0)
        symbols = bot.cfg.get('SYMBOLS', [])
        value = f"**Open Trades**: {open_trades}\n**Risk**: {risk}%\n**Symbols**: {symbols}"
        
        if bot.cfg.get('USE_SMT_DIVERGENCE', False):
            smt_pairs = bot.cfg.get('SMT_PAIRS', {})
            tracking = []
            for sym in symbols:
                if sym in smt_pairs:
                    tracking.append(f"{sym} vs {smt_pairs[sym]}")
            if tracking:
                value += f"\n**SMT Tracking**: {', '.join(tracking)}"
                
        embed.add_field(name=name, value=value, inline=False)
        
    await ctx.send(embed=embed)

@client.command()
async def set(ctx, bot_name: str, parameter: str, value: str):
    """Live-edits a bot's configuration (e.g. !set gold_bot RISK_PERCENT 2.0)."""
    filepath = f"bots/{bot_name}.json"
    if not os.path.exists(filepath):
        embed = discord.Embed(title="❌ Error", description=f"Configuration `{bot_name}.json` not found.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return
        
    try:
        with open(filepath, "r") as f:
            cfg = json.load(f)
            
        # Try to cast value appropriately
        if value.lower() == "true":
            val = True
        elif value.lower() == "false":
            val = False
        elif "." in value:
            try: val = float(value)
            except: val = value
        else:
            try: val = int(value)
            except: val = value
            
        cfg[parameter] = val
        
        with open(filepath, "w") as f:
            json.dump(cfg, f, indent=4)
            
        # If bot is running, update its active memory
        if bot_name in active_bots:
            active_bots[bot_name].cfg = cfg
            
        embed = discord.Embed(title="✅ Setting Updated", description=f"Updated `{parameter}` to `{val}` for `{bot_name}`.", color=discord.Color.green())
        await ctx.send(embed=embed)
    except Exception as e:
        embed = discord.Embed(title="❌ Error", description=f"Error updating config: {e}", color=discord.Color.red())
        await ctx.send(embed=embed)

@client.command()
async def report(ctx, bot_name: str):
    """Uploads the latest live trades and market analysis CSV for a bot."""
    if bot_name not in active_bots:
        embed = discord.Embed(title="⚠️ Not Running", description=f"`{bot_name}` is not currently active.", color=discord.Color.orange())
        await ctx.send(embed=embed)
        return
        
    bot = active_bots[bot_name]
    embed = discord.Embed(title="📊 Generating Report", description=f"Exporting latest trades for `{bot_name}`...", color=discord.Color.blue())
    msg = await ctx.send(embed=embed)
    
    # Export trades first
    await asyncio.to_thread(bot.export_live_trades_to_csv)
    
    trades_path = f"data/{bot_name}_live_trades.csv"
    analysis_path = f"data/{bot_name}_market_analysis.csv"
    
    files = []
    if os.path.exists(trades_path):
        files.append(discord.File(trades_path))
    if os.path.exists(analysis_path):
        files.append(discord.File(analysis_path))
        
    if files:
        success_embed = discord.Embed(title="✅ Report Ready", description=f"Here is the latest data for `{bot_name}`:", color=discord.Color.green())
        await msg.edit(embed=success_embed, attachments=files)
    else:
        error_embed = discord.Embed(title="❌ No Data", description=f"No data files found for `{bot_name}`.", color=discord.Color.red())
        await msg.edit(embed=error_embed)

if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_BOT_TOKEN not found in .env file.")
    else:
        print("Starting Discord Controller...")
        client.run(TOKEN)
