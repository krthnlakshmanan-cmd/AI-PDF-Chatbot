
import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BASE_DIR = Path(__file__).resolve().parent

server_params = StdioServerParameters(
    command=sys.executable,
    args=[str(BASE_DIR / "calendar_server.py")],
    env=None
)


async def main():

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            await session.initialize()

            print("Google Calendar MCP connected!")

            result = await session.call_tool(
                "get_events",
                arguments={"max_results": 10}
            )

            for item in result.content:
                if item.type == "text":
                    print(item.text)


if __name__ == "__main__":
    asyncio.run(main())
