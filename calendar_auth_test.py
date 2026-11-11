
import os
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

CREDENTIALS_FILE = "calendar_credentials.json"
TOKEN_FILE = "token.json"
def get_calendar_service():

    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            TOKEN_FILE, SCOPES
        )

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE, SCOPES
        )

        creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    service = build("calendar", "v3", credentials=creds)

    return service


if __name__ == "__main__":

    try:
        service = get_calendar_service()

        now = datetime.now(timezone.utc).isoformat()

        events_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])

        print("\nGoogle Calendar connected successfully!")

        if not events:
            print("No upcoming events found.")

        for event in events:
            print(
                event.get("summary", "No title"),
                "-",
                event.get("start", {}).get("dateTime",
                event.get("start", {}).get("date"))
            )

    except Exception as e:
        print("Error:", e)
