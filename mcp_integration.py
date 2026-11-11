
import asyncio
import sys
import traceback
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# Locate calendar_server.py in the same project folder
BASE_DIR = Path(__file__).resolve().parent
SERVER_FILE = BASE_DIR / "calendar_server.py"


def get_server_parameters():
    """Configure the local Google Calendar MCP server."""

    if not SERVER_FILE.exists():
        raise FileNotFoundError(
            f"Could not find calendar_server.py at: {SERVER_FILE}"
        )

    return StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_FILE)]
    )


async def list_calendar_tools():
    """Get the available tools from the Calendar MCP server."""

    server_params = get_server_parameters()

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            await session.initialize()

            result = await session.list_tools()

            return [
                {
                    "name": tool.name,
                    "description": tool.description
                }
                for tool in result.tools
            ]


async def call_calendar_tool(tool_name, arguments=None):
    """Call a Google Calendar MCP tool."""

    server_params = get_server_parameters()

    if arguments is None:
        arguments = {}

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            await session.initialize()

            result = await session.call_tool(
                tool_name,
                arguments=arguments
            )

            if result.isError:
                raise RuntimeError(
                    f"Calendar MCP error: {result.content}"
                )

            output = []

            for item in result.content:
                if hasattr(item, "text"):
                    output.append(item.text)

            return "\n".join(output)



if __name__ == "__main__":

    async def test_calendar():

        print("Connecting to Google Calendar...")

        try:
            result = await call_calendar_tool(
                "get_events",
                {"max_results": 10}
            )

            print("\nGoogle Calendar Events:")
            print(result)

        except Exception as e:

            print("\nFULL MCP ERROR:")
            traceback.print_exception(
                type(e), e, e.__traceback__
            )

            if isinstance(e, BaseExceptionGroup):
                for error in e.exceptions:
                    print("\nINNER ERROR:")
                    traceback.print_exception(
                        type(error),
                        error,
                        error.__traceback__
                    )

    asyncio.run(test_calendar())

