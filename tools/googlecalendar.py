from flask import Flask, redirect, request, session, url_for
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# Allow HTTP for local testing
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Initialize OAuth Flow
flow = Flow.from_client_secrets_file(
    "credentials.json",
    scopes=SCOPES,
    redirect_uri="http://localhost:5000/callback"
)


def credentials_to_dict(creds):
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }


def dict_to_credentials(data):
    from google.oauth2.credentials import Credentials
    return Credentials(
        token=data["token"],
        refresh_token=data["refresh_token"],
        token_uri=data["token_uri"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=data["scopes"]
    )


@app.route("/")
def home():
    return """
    <h2>Google Calendar AI Agent</h2>
    <a href='/login'>Login with Google</a><br><br>
    <a href='/create_event'>Create Test Event</a><br><br>
    <a href='/list_events'>List Events</a><br><br>
    <a href='/logout'>Logout</a>
    """


@app.route("/login")
def login():
    auth_url, _ = flow.authorization_url(prompt="consent")
    return redirect(auth_url)


@app.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    session["credentials"] = credentials_to_dict(credentials)

    return redirect(url_for("home"))


@app.route("/create_event")
def create_event():
    if "credentials" not in session:
        return redirect(url_for("login"))

    creds = dict_to_credentials(session["credentials"])
    service = build("calendar", "v3", credentials=creds)

    start_time = datetime.now() + timedelta(hours=1)
    end_time = start_time + timedelta(hours=1)

    event = {
        "summary": "AI Agent Meeting",
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "Asia/Kolkata"
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "Asia/Kolkata"
        }
    }

    result = service.events().insert(
        calendarId="primary",
        body=event
    ).execute()

    return f"Event created: <a href='{result.get('htmlLink')}' target='_blank'>View Event</a>"


@app.route("/list_events")
def list_events():
    if "credentials" not in session:
        return redirect(url_for("login"))

    creds = dict_to_credentials(session["credentials"])
    service = build("calendar", "v3", credentials=creds)

    events_result = service.events().list(
        calendarId="primary",
        maxResults=10,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = events_result.get("items", [])

    if not events:
        return "No upcoming events found."

    output = "<h3>Upcoming Events:</h3>"
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        output += f"<p>{start} - {event.get('summary')}</p>"

    return output


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)