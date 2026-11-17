"""Start the MCP server, list its tools, and call one, without any AI involved."""
import asyncio
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

SERVER_FILE = Path(__file__).resolve().parents[1] / "src" / "support_agent" / "mcp_server.py"

# How to start the server: "run mcp_server.py with this same Python"
server = StdioServerParameters(command=sys.executable, args=[str(SERVER_FILE)])


async def main(): # function that can wait without freezing everything
    async with Client(server) as client:           # starts the server as a background process, connects
        tools = await client.list_tools()          # "what tools do you have?", await: marks the exact spots where it waits (“send the request, wait for the answer”).
        for tool in tools.tools:
            print("TOOL:", tool.name)
            print("  description:", tool.description)
            print("  inputs:", tool.input_schema)
            print()

        result = await client.call_tool(           # "run this tool for me"
            "get_order",
            {"order_id": "ORD-1003", "email": "sophie.bakker@example.com"},
        )
        print("is_error:", result.is_error)
        print("result:", result.content[0].text)


asyncio.run(main())                               # starts it all