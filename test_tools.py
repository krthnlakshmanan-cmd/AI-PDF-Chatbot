import asyncio
from mcp_integration import list_calendar_tools

async def main():
    tools = await list_calendar_tools()
    print("Available Calendar MCP Tools:")
    print(tools)

asyncio.run(main())