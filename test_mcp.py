import asyncio
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai.mcp import MCPServerStdio

mcp_server = MCPServerStdio(command="echo", args=["hello"])

agent = Agent(
    TestModel(),
    toolsets=[mcp_server]
)

async def test():
    try:
        # this will probably fail because echo hello isn't a valid MCP server, but we want to see if it tries to connect
        await agent.run("test")
        print("Success")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
