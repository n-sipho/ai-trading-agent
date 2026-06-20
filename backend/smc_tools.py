"""
SMC Tool Registry — Custom Pydantic AI tools that wrap the SMC strategy logic.

These are Python-native tools (not MCP tools) that the agent can call alongside
the MCP server tools. They accept raw data (e.g., candle JSON from the MCP
`get_candles_latest` tool) and run the SMC analysis on it.
"""

import json
import sys
import os
from pathlib import Path

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Import the SMC strategy module from the mt5_smc_bot directory
# ---------------------------------------------------------------------------
_SMC_BOT_DIR = str(Path(__file__).resolve().parent.parent / "mt5_smc_bot")
if _SMC_BOT_DIR not in sys.path:
    sys.path.insert(0, _SMC_BOT_DIR)

from strategy_smc import (
    calculate_fvg,
    identify_swings,
    detect_liquidity_sweeps,
    calculate_ote,
    is_kill_zone,
    calculate_atr,
    generate_smc_signals,
    get_htf_bias,
)

# ---------------------------------------------------------------------------
# Default SMC configuration
# ---------------------------------------------------------------------------
DEFAULT_SMC_CONFIG: dict = {
    "SWING_LENGTH": 5,
    "LONDON_KZ_START": 2,
    "LONDON_KZ_END": 5,
    "NY_KZ_START": 7,
    "NY_KZ_END": 10,
    "ATR_PERIOD": 14,
    "ATR_SMA_PERIOD": 50,
    "USE_VOLATILITY_FILTER": True,
    "HTF_SWING_LENGTH": 3,
    "RR_TARGET": 2.0,
    "RISK_PERCENT": 1.0,
}


# ---------------------------------------------------------------------------
# Helper: parse MCP candle JSON into a Pandas DataFrame
# ---------------------------------------------------------------------------
def _parse_candle_json(candle_data_json: str) -> pd.DataFrame:
    """Convert raw candle JSON (from the MCP get_candles_latest tool) into a
    DataFrame with the columns expected by the SMC strategy functions.

    The MCP server typically returns a list of dicts with keys like:
    ``time``, ``open``, ``high``, ``low``, ``close``, ``tick_volume`` (or
    ``volume``).  We normalise to lowercase column names and ensure ``time``
    is a proper datetime.
    """
    data = json.loads(candle_data_json) if isinstance(candle_data_json, str) else candle_data_json

    # Handle both list-of-dicts and dict-with-a-data-key formats
    if isinstance(data, dict):
        # Some MCP servers wrap results: {"candles": [...]} or {"data": [...]}
        for key in ("candles", "data", "rates", "bars"):
            if key in data:
                data = data[key]
                break
        else:
            # Single candle or unexpected structure — wrap in list
            data = [data]

    df = pd.DataFrame(data)

    # Normalise column names to lowercase
    df.columns = [c.lower() for c in df.columns]

    # Ensure required columns exist
    required = {"time", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Candle data is missing required columns: {missing}")

    # Convert the time column to datetime
    if not pd.api.types.is_datetime64_any_dtype(df["time"]):
        # Try numeric epoch first, then ISO string
        try:
            df["time"] = pd.to_datetime(df["time"], unit="s")
        except (ValueError, TypeError):
            df["time"] = pd.to_datetime(df["time"])

    # Sort chronologically
    df = df.sort_values("time").reset_index(drop=True)

    return df


# ============================================================================
# Pydantic AI Tool functions
# ============================================================================
# These are registered on the agent in agent.py via @agent.tool decorators.
# We define the core logic here so it can be unit-tested independently.
# ============================================================================


def analyze_candle_data_impl(candle_data_json: str, symbol: str) -> str:
    """Run the full SMC analysis on raw candle JSON and return a human-readable
    summary string.

    Parameters
    ----------
    candle_data_json : str
        JSON string of OHLCV candle data (as returned by the MCP
        ``get_candles_latest`` tool).
    symbol : str
        The trading symbol (e.g. ``"EURUSD"``, ``"XAUUSD"``).

    Returns
    -------
    str
        A structured text report of the SMC analysis.
    """
    try:
        df = _parse_candle_json(candle_data_json)
    except Exception as exc:
        return f"❌ Failed to parse candle data: {exc}"

    if len(df) < 20:
        return "❌ Insufficient candle data for reliable SMC analysis (need at least 20 bars)."

    cfg = DEFAULT_SMC_CONFIG.copy()

    try:
        signal, sl_price, current_bar = generate_smc_signals(df, cfg)
    except Exception as exc:
        return f"❌ Error during SMC analysis: {exc}"

    # --- Build the summary ------------------------------------------------
    signal_map = {1: "🟢 BUY", -1: "🔴 SELL", 0: "⚪ NEUTRAL"}
    signal_label = signal_map.get(signal, "⚪ NEUTRAL")

    # Determine trend from last BOS
    last_bullish_bos = df["Bullish_Break"].iloc[-10:].any() if "Bullish_Break" in df.columns else False
    last_bearish_bos = df["Bearish_Break"].iloc[-10:].any() if "Bearish_Break" in df.columns else False
    if last_bullish_bos and not last_bearish_bos:
        trend = "📈 Bullish (recent Break of Structure to the upside)"
    elif last_bearish_bos and not last_bullish_bos:
        trend = "📉 Bearish (recent Break of Structure to the downside)"
    elif last_bullish_bos and last_bearish_bos:
        trend = "↔️ Transitional / Choppy (BOS in both directions recently)"
    else:
        trend = "↔️ No recent structural break detected"

    # Active FVGs on current bar
    bullish_fvg = bool(current_bar.get("Recent_Bullish_FVG", False))
    bearish_fvg = bool(current_bar.get("Recent_Bearish_FVG", False))
    fvg_status = []
    if bullish_fvg:
        fvg_status.append("Bullish FVG active")
    if bearish_fvg:
        fvg_status.append("Bearish FVG active")
    fvg_text = ", ".join(fvg_status) if fvg_status else "No active FVGs"

    # OTE zone
    in_bull_ote = bool(current_bar.get("In_Bullish_OTE", False))
    in_bear_ote = bool(current_bar.get("In_Bearish_OTE", False))
    ote_parts = []
    if in_bull_ote:
        ote_parts.append("Price is in a Bullish OTE zone (62-79% Fib retracement)")
    if in_bear_ote:
        ote_parts.append("Price is in a Bearish OTE zone (62-79% Fib retracement)")
    ote_text = "; ".join(ote_parts) if ote_parts else "Price is NOT in an OTE zone"

    # Liquidity sweeps
    bull_sweep = bool(current_bar.get("Recent_Bullish_Sweep", False))
    bear_sweep = bool(current_bar.get("Recent_Bearish_Sweep", False))
    sweep_parts = []
    if bull_sweep:
        sweep_parts.append("Recent bullish liquidity sweep (stop hunt below support)")
    if bear_sweep:
        sweep_parts.append("Recent bearish liquidity sweep (stop hunt above resistance)")
    sweep_text = "; ".join(sweep_parts) if sweep_parts else "No recent liquidity sweeps"

    # Kill Zone
    in_kz = bool(current_bar.get("Active_Kill_Zone", False))
    london = bool(current_bar.get("London_KZ", False))
    ny = bool(current_bar.get("NY_KZ", False))
    if london:
        kz_text = "✅ Currently in London Kill Zone"
    elif ny:
        kz_text = "✅ Currently in New York Kill Zone"
    elif in_kz:
        kz_text = "✅ Currently in an active Kill Zone"
    else:
        kz_text = "❌ Outside Kill Zone hours"

    # Volatility
    high_vol = bool(current_bar.get("High_Volatility", False))
    vol_text = "High volatility (ATR above average)" if high_vol else "Low volatility (ATR below average)"

    # Key price levels
    swing_high = current_bar.get("Last_Swing_High_Val", "N/A")
    swing_low = current_bar.get("Last_Swing_Low_Val", "N/A")
    close_price = current_bar.get("close", "N/A")

    report = (
        f"📊 **SMC Analysis for {symbol}**\n"
        f"{'=' * 40}\n"
        f"**Signal**: {signal_label}\n"
        f"**Current Trend**: {trend}\n\n"
        f"**Fair Value Gaps**: {fvg_text}\n"
        f"**OTE Zone**: {ote_text}\n"
        f"**Liquidity Sweeps**: {sweep_text}\n"
        f"**Kill Zone**: {kz_text}\n"
        f"**Volatility**: {vol_text}\n\n"
        f"**Key Levels**:\n"
        f"  • Last Swing High: {swing_high}\n"
        f"  • Last Swing Low: {swing_low}\n"
        f"  • Current Close: {close_price}\n"
    )

    if signal != 0:
        report += f"  • Suggested Stop Loss: {sl_price}\n"

    return report


def calculate_trade_risk_impl(
    account_balance: float,
    risk_percent: float,
    entry_price: float,
    stop_loss_price: float,
    symbol_type: str = "forex",
) -> str:
    """Calculate position sizing and risk breakdown.

    Parameters
    ----------
    account_balance : float
        Current account balance in USD.
    risk_percent : float
        Percentage of the account to risk (e.g. 1.0 for 1%).
    entry_price : float
        Intended entry price.
    stop_loss_price : float
        Stop-loss price level.
    symbol_type : str
        One of ``"forex"``, ``"gold"``, ``"jpy_pair"``.

    Returns
    -------
    str
        Formatted risk breakdown.
    """
    risk_amount = account_balance * (risk_percent / 100.0)
    sl_distance = abs(entry_price - stop_loss_price)

    if sl_distance == 0:
        return "❌ Entry and stop-loss prices are the same — cannot calculate risk."

    # Pip value assumptions (standard lot = 100 000 units)
    if symbol_type.lower() == "gold":
        # Gold: 1 pip = $0.01, tick value ~$1 per standard lot per pip
        pip_size = 0.01
        pip_value_per_lot = 1.0  # USD per pip per lot
    elif symbol_type.lower() == "jpy_pair":
        # JPY pairs: 1 pip = 0.01
        pip_size = 0.01
        pip_value_per_lot = 6.50  # approximate for XXX/JPY
    else:
        # Standard forex: 1 pip = 0.0001
        pip_size = 0.0001
        pip_value_per_lot = 10.0  # USD per pip per standard lot

    sl_pips = sl_distance / pip_size
    lot_size = risk_amount / (sl_pips * pip_value_per_lot) if (sl_pips * pip_value_per_lot) > 0 else 0.01

    # Clamp
    lot_size = max(0.01, round(lot_size, 2))

    rr_target = DEFAULT_SMC_CONFIG["RR_TARGET"]
    potential_reward = risk_amount * rr_target
    tp_distance = sl_distance * rr_target
    tp_price = entry_price + tp_distance if entry_price > stop_loss_price else entry_price - tp_distance

    direction = "BUY" if entry_price > stop_loss_price else "SELL"

    return (
        f"📐 **Position Size Calculation**\n"
        f"{'=' * 40}\n"
        f"**Direction**: {direction}\n"
        f"**Account Balance**: ${account_balance:,.2f}\n"
        f"**Risk**: {risk_percent}% = ${risk_amount:,.2f}\n"
        f"**Entry Price**: {entry_price}\n"
        f"**Stop Loss**: {stop_loss_price}\n"
        f"**SL Distance**: {sl_pips:.1f} pips\n"
        f"**Recommended Lot Size**: {lot_size} lots\n\n"
        f"**Risk/Reward Target**: {rr_target}R\n"
        f"**Take Profit Price**: {tp_price}\n"
        f"**Potential Reward**: ${potential_reward:,.2f}\n"
        f"**Symbol Type**: {symbol_type}\n"
    )


def get_smc_config_impl() -> str:
    """Return the current SMC configuration as a readable string."""
    lines = ["⚙️ **Active SMC Configuration**", "=" * 40]
    for key, value in DEFAULT_SMC_CONFIG.items():
        lines.append(f"  • {key}: {value}")
    return "\n".join(lines)


def get_htf_bias_impl(candle_data_json: str, symbol: str) -> str:
    """Determine the higher-timeframe macro bias from 4H candle data.

    Parameters
    ----------
    candle_data_json : str
        JSON string of 4H OHLCV candle data.
    symbol : str
        The trading symbol.

    Returns
    -------
    str
        English explanation of the HTF directional bias.
    """
    try:
        df = _parse_candle_json(candle_data_json)
    except Exception as exc:
        return f"❌ Failed to parse HTF candle data: {exc}"

    if len(df) < 15:
        return "❌ Insufficient 4H candle data for HTF bias calculation (need at least 15 bars)."

    cfg = DEFAULT_SMC_CONFIG.copy()

    try:
        bias = get_htf_bias(df, cfg)
    except Exception as exc:
        return f"❌ Error calculating HTF bias: {exc}"

    if bias == 1:
        direction = "🟢 BULLISH"
        explanation = (
            f"The higher-timeframe (4H) structure for {symbol} is **bullish**. "
            "The most recent structural break was to the upside, indicating "
            "institutional order flow is favouring longs. Look for buy setups "
            "on lower timeframes that align with this bias."
        )
    elif bias == -1:
        direction = "🔴 BEARISH"
        explanation = (
            f"The higher-timeframe (4H) structure for {symbol} is **bearish**. "
            "The most recent structural break was to the downside, indicating "
            "institutional order flow is favouring shorts. Look for sell setups "
            "on lower timeframes that align with this bias."
        )
    else:
        direction = "⚪ NEUTRAL"
        explanation = (
            f"The higher-timeframe (4H) structure for {symbol} is **neutral/undefined**. "
            "No clear structural break has been detected. It may be best to stay "
            "flat or wait for a decisive BOS before entering trades."
        )

    return f"🔭 **HTF Bias for {symbol}**: {direction}\n\n{explanation}"
