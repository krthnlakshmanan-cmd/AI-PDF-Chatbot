
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
import sys
from google.auth.transport.requests import Request

from mcp.server.fastmcp import FastMCP
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parent

CREDENTIALS_FILE = BASE_DIR / "calendar_credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events"
]


def get_calendar_service():

    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(
            str(TOKEN_FILE), SCOPES
        )

    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build("calendar", "v3", credentials=creds)

mcp = FastMCP("Google Calendar MCP")
@mcp.tool()
def get_events(max_results: int = 10) -> str:
    """Retrieve upcoming events from Google Calendar."""

    try:
        service = get_calendar_service()

        events_result = service.events().list(
            calendarId="primary",
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
            timeMin=datetime.now().astimezone().isoformat()
        ).execute()

        events = events_result.get("items", [])

        if not events:
            return "No upcoming events found."

        return json.dumps(events, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        })
@mcp.tool()
def create_event(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: str = "",
    location: str = "",
    attendees: list[str] | None = None,
    create_meet_link: bool = True
) -> str:

    """
    Create a meeting or event in Google Calendar.

    Datetime format:
    2026-11-12T10:00:00+05:30
    """

    try:
        # Validate date and time
        start = datetime.fromisoformat(start_datetime)
        end = datetime.fromisoformat(end_datetime)

        if start.tzinfo is None or end.tzinfo is None:
            return "Error: Please provide timezone-aware date and time."

        if end <= start:
            return "Error: End time must be after start time."

        # Get Google Calendar service
        service = get_calendar_service()

        # Prepare event
        event = {
            "summary": summary,
            "description": description,
            "location": location,
            "start": {
                "dateTime": start.isoformat()
            },
            "end": {
                "dateTime": end.isoformat()
            }
        }

        # Add attendees
        if attendees:
            event["attendees"] = [
                {"email": email} for email in attendees
            ]

        # Create Google Meet link
        if create_meet_link:
            event["conferenceData"] = {
                "createRequest": {
                    "requestId": str(uuid4()),
                    "conferenceSolutionKey": {
                        "type": "hangoutsMeet"
                    }
                }
            }

        # Insert event into Google Calendar
        created_event = service.events().insert(
            calendarId="primary",
            body=event,
            conferenceDataVersion=1
        ).execute()

        # Extract Google Meet link
        meet_link = ""

        for entry in created_event.get(
            "conferenceData", {}
        ).get("entryPoints", []):

            if entry.get("entryPointType") == "video":
                meet_link = entry.get("uri", "")

        result = {
            "status": "success",
            "message": "Meeting created successfully!",
            "title": created_event.get("summary"),
            "start": created_event.get("start"),
            "end": created_event.get("end"),
            "htmlLink": created_event.get("htmlLink"),
            "google_meet_link": meet_link
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        })
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr
    )
    mcp.run(transport="stdio")