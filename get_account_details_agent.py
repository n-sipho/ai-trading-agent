import asyncio
from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.mcp import MCPToolset
from fastmcp.client.transports import StdioTransport

load_dotenv()

# Initialize the Pydantic AI agent
model = GoogleModel(
    model_name="gemma-4-31b-it",  # Target the flagship open model
)

# Connect to the MT5 MCP server using the stdio transport
mcp_transport = StdioTransport(command="uvx", args=["--from", "mcp-metatrader5-server", "mt5mcp"])
mcp_toolset = MCPToolset(mcp_transport, init_timeout=60)

agent = Agent(
    model,
    system_prompt="""You are a trading assistant with access to MetaTrader 5.
You can help analyze markets, retrieve data, and execute trades safely.

CRITICAL INSTRUCTION: Before getting account details or checking the balance, you MUST call the `initialize` tool with the argument path="C:\\Program Files\\MetaTrader 5\\terminal64.exe" to connect to MT5. This is required before any other MT5 action.""",
    toolsets=[mcp_toolset],
)

async def use_mt5_with_pydantic_ai():
    # Run the agent
    print("Running Agent and initializing MT5 connection...")
    result = await agent.run(
        "Initialize MT5, then get my account information and summarize the balance and equity.",
        message_history=[],
    )
    print(f"Agent response: {result.output}")

if __name__ == "__main__":
    asyncio.run(use_mt5_with_pydantic_ai())
