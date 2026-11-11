import asyncio
from mcp_integration import call_calendar_tool

async def main():

    result = await call_calendar_tool(
        "create_event",
        {
            "summary": "MCP Test Meeting",
            "start_datetime": "2026-11-12T10:00:00+05:30",
            "end_datetime": "2026-11-12T10:30:00+05:30",
            "description": "Testing Google Calendar MCP integration",
            "location": "",
            "attendees": [],
            "create_meet_link": True
        }
    )

    print("\nCreate Event Result:")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())