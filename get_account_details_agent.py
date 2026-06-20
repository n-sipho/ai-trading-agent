import asyncio
# from datetime import datetime
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel

load_dotenv()

# Initialize the Pydantic AI agent
model = GoogleModel(
    model_name="gemma-4-31b-it",  # Target the flagship open model
)
agent = Agent(
    model,
    system_prompt="""You are a trading assistant with access to MetaTrader 5.
    You can help analyze markets, retrieve data, and execute trades safely.""",
)


async def use_mt5_with_pydantic_ai():
    # Start the MCP server connection
    server_params = StdioServerParameters(
        command="uvx", args=["--from", "mcp-metatrader5-server", "mt5mcp"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()

            # List available tools from the MCP server
            tools_result = await session.list_tools()
            print(f"Available tools: {[tool.name for tool in tools_result.tools]}")

            # Call a tool - Initialize MT5
            init_result = await session.call_tool(
                "initialize",
                arguments={"path": r"C:\Program Files\MetaTrader 5\terminal64.exe"},
            )
            print(f"MT5 Initialization: {init_result.content}")

            # Get account info using the agent
            result = await agent.run(
                "Get my account information and summarize the balance and equity.",
                message_history=[],
            )
            print(f"Agent response: {result.data}")


# Run the async function
asyncio.run(use_mt5_with_pydantic_ai())
