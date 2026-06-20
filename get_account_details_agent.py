import asyncio
import os
import sys
from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.mcp import MCPToolset
from fastmcp.client.transports import StdioTransport

load_dotenv()

# Get MT5 credentials from environment
MT5_LOGIN = os.getenv("MT5_LOGIN")
MT5_PASSWORD = os.getenv("MT5_PASSWORD")
MT5_SERVER = os.getenv("MT5_SERVER")

if not all([MT5_LOGIN, MT5_PASSWORD, MT5_SERVER]):
    print("Error: Missing MT5 credentials in environment (.env).")
    print("Please set MT5_LOGIN, MT5_PASSWORD, and MT5_SERVER.")
    sys.exit(1)

# Initialize the Pydantic AI agent
model = GoogleModel(
    model_name="gemma-4-31b-it",  # Target the flagship open model
)

# Connect to the MT5 MCP server using the stdio transport
mcp_transport = StdioTransport(
    command="uvx", 
    args=[
        "--from", "metatrader-mcp-server", 
        "metatrader-mcp-server",
        "--login", MT5_LOGIN,
        "--password", MT5_PASSWORD,
        "--server", MT5_SERVER,
        "--transport", "stdio"
    ]
)
mcp_toolset = MCPToolset(mcp_transport, init_timeout=60)

agent = Agent(
    model,
    system_prompt="""You are an expert trading assistant. You are connected to MetaTrader 5 via the metatrader-mcp-server.
You can safely query account details, fetch market data, and execute trades using the available tools.
If you need to close all profitable positions, you can use the built-in helper tools.""",
    toolsets=[mcp_toolset],
)

async def use_mt5_with_pydantic_ai():
    # Run the agent
    print("Running Agent and connecting to MT5...")
    result = await agent.run(
        "Get my account information and summarize the balance, equity, and margin.",
        message_history=[],
    )
    print(f"\nAgent response:\n{result.output}")

if __name__ == "__main__":
    asyncio.run(use_mt5_with_pydantic_ai())
