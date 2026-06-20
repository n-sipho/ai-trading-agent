"""
Pydantic AI Agent — Conversational SMC Trading Assistant.

Connects to the MetaTrader 5 MCP server via StdioTransport and registers custom
SMC analysis tools so the LLM can fetch market data *and* run institutional-grade
Smart Money Concepts analysis in a single conversation turn.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.mcp import MCPToolset
from fastmcp.client.transports import StdioTransport

from smc_tools import (
    analyze_candle_data_impl,
    calculate_trade_risk_impl,
    get_smc_config_impl,
    get_htf_bias_impl,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
# .env lives in the project root (one level above backend/)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

MT5_LOGIN = os.getenv("MT5_LOGIN", "")
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

if not all([MT5_LOGIN, MT5_PASSWORD, MT5_SERVER]):
    logger.warning(
        "MT5 credentials not fully configured. "
        "Set MT5_LOGIN, MT5_PASSWORD, and MT5_SERVER in %s",
        _ENV_PATH,
    )

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
model = GoogleModel(model_name="gemma-4-31b-it")

# ---------------------------------------------------------------------------
# MCP Transport — connects to metatrader-mcp-server via stdio
# ---------------------------------------------------------------------------
mcp_transport = StdioTransport(
    command="uvx",
    args=[
        "--from", "metatrader-mcp-server",
        "metatrader-mcp-server",
        "--login", MT5_LOGIN,
        "--password", MT5_PASSWORD,
        "--server", MT5_SERVER,
        "--transport", "stdio",
    ],
)

mcp_toolset = MCPToolset(mcp_transport, init_timeout=60)

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are an **expert institutional Smart Money Concepts (SMC) trading assistant** \
connected to a live MetaTrader 5 account via the metatrader-mcp-server.

## Your Capabilities
- **Account management**: Query account balance, equity, margin, open positions, and trade history.
- **Market data**: Fetch real-time quotes, OHLCV candle data for any symbol and timeframe.
- **SMC analysis**: Run institutional-grade structural analysis including Fair Value Gaps (FVG), \
Break of Structure (BOS), Change of Character (ChoCH), Optimal Trade Entry (OTE) zones, \
Liquidity Sweeps, Kill Zone filtering, and ATR-based volatility assessment.
- **Trade execution**: Place, modify, and close trades with proper risk management.
- **Position sizing**: Calculate precise lot sizes based on account risk percentage.

## How to Analyse a Symbol
When asked to analyse a symbol:
1. First, use the MCP tool `get_candles_latest` to fetch candle data for the symbol \
   (use the timeframe the user requests, defaulting to M15 if unspecified).
2. Then call `analyze_candle_data` with the raw candle JSON to get the full SMC breakdown.
3. Optionally, fetch 4H candle data and call `get_htf_bias` for the macro directional bias.
4. Present the analysis in a clear, professional format.

## How to Size a Position
When the user wants to take a trade or asks about position sizing:
1. Get the account info (balance) via the MCP tools.
2. Determine entry and stop-loss levels from the SMC analysis.
3. Call `calculate_trade_risk` with the account balance, risk %, entry, stop loss, \
   and symbol type (forex/gold/jpy_pair).
4. Always confirm lot size and risk with the user before executing.

## Important Rules
- **Never execute a trade without explicit user confirmation.**
- Always explain your reasoning in clear, professional language.
- When analysing, clearly state the signal (BUY / SELL / NEUTRAL) and the \
  confluence factors supporting it.
- If a signal is NEUTRAL, explain what conditions are missing and what would \
  need to change for a valid setup.
- Use the SMC configuration tool to show the user what parameters are active \
  if they ask.
- Be concise but thorough. Traders value precision.
"""

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
agent = Agent(
    model,
    system_prompt=SYSTEM_PROMPT,
    toolsets=[mcp_toolset],
)


# ---------------------------------------------------------------------------
# Register custom SMC tools on the agent
# ---------------------------------------------------------------------------
@agent.tool_plain
def analyze_candle_data(candle_data_json: str, symbol: str) -> str:
    """Run full SMC structural analysis on candle data.

    Call this AFTER fetching candle data with the MCP `get_candles_latest` tool.
    Pass the raw candle JSON directly as ``candle_data_json``.

    Args:
        candle_data_json: JSON string of OHLCV candle data from the MCP server.
        symbol: The trading symbol (e.g. "EURUSD", "XAUUSD").

    Returns:
        A formatted SMC analysis report including trend, FVGs, OTE zones,
        liquidity sweeps, kill-zone status, and the final signal.
    """
    return analyze_candle_data_impl(candle_data_json, symbol)


@agent.tool_plain
def calculate_trade_risk(
    account_balance: float,
    risk_percent: float,
    entry_price: float,
    stop_loss_price: float,
    symbol_type: str = "forex",
) -> str:
    """Calculate position sizing and risk/reward breakdown.

    Args:
        account_balance: Current account balance in USD.
        risk_percent: Percentage of account to risk (e.g. 1.0 for 1%).
        entry_price: Intended entry price.
        stop_loss_price: Stop-loss price level.
        symbol_type: One of "forex", "gold", or "jpy_pair".

    Returns:
        Formatted risk breakdown with lot size, risk amount, and TP target.
    """
    return calculate_trade_risk_impl(
        account_balance, risk_percent, entry_price, stop_loss_price, symbol_type
    )


@agent.tool_plain
def get_active_smc_config() -> str:
    """Return the currently active SMC analysis configuration parameters.

    Returns:
        A formatted list of all SMC config values (swing length, kill zone
        hours, ATR settings, risk/reward target, etc.).
    """
    return get_smc_config_impl()


@agent.tool_plain
def get_htf_bias(candle_data_json: str, symbol: str) -> str:
    """Determine the higher-timeframe (4H) macro directional bias.

    Call this AFTER fetching 4H candle data with the MCP `get_candles_latest`
    tool. Pass the raw candle JSON directly.

    Args:
        candle_data_json: JSON string of 4H OHLCV candle data from MCP.
        symbol: The trading symbol (e.g. "EURUSD").

    Returns:
        An explanation of whether the HTF bias is bullish, bearish, or neutral,
        along with trading guidance.
    """
    return get_htf_bias_impl(candle_data_json, symbol)


# ---------------------------------------------------------------------------
# Public API — called by main.py
# ---------------------------------------------------------------------------
async def run_agent(user_message: str, message_history: list | None = None) -> str:
    """Run the agent with a user message and return the response text.

    Parameters
    ----------
    user_message : str
        The latest message from the user.
    message_history : list, optional
        The Pydantic AI message history list from prior turns (enables
        multi-turn conversation context).

    Returns
    -------
    str
        The agent's text response.
    """
    try:
        result = await agent.run(
            user_message,
            message_history=message_history or [],
        )
        return result.output
    except Exception as exc:
        logger.exception("Agent execution error")
        return f"⚠️ An error occurred while processing your request: {exc}"
