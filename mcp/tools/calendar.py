from mcp.server import mcp_tool
import logging

logger = logging.getLogger("LifeOS.Tools.Calendar")

# Mock database of calendar events
mock_calendar = [
    {
        "id": "event_1",
        "title": "Strategy Meeting with Team",
        "start": "2026-07-01T10:00:00",
        "end": "2026-07-01T11:00:00",
        "description": "Weekly alignment meeting."
    },
    {
        "id": "event_2",
        "title": "Dinner with Wife",
        "start": "2026-07-01T19:00:00",
        "end": "2026-07-01T21:00:00",
        "description": "Date night at standard restaurant."
    }
]

@mcp_tool()
def get_events() -> list[dict]:
    """
    Retrieve all scheduled calendar events.
    """
    logger.info("Calendar Tool: Fetching scheduled events.")
    return mock_calendar

@mcp_tool()
def create_calendar_event(title: str, start_time: str, end_time: str, description: str = "") -> dict:
    """
    Create a new event in the calendar.
    """
    logger.info(f"Calendar Tool: Creating event '{title}' from {start_time} to {end_time}")
    new_event = {
        "id": f"event_{len(mock_calendar) + 1}",
        "title": title,
        "start": start_time,
        "end": end_time,
        "description": description
    }
    mock_calendar.append(new_event)
    return {"status": "SUCCESS", "event": new_event}

@mcp_tool()
def delete_calendar(calendar_id: str) -> str:
    """
    Delete a specific calendar event.
    RESTRICTED: Requires manual user approval.
    """
    logger.info(f"Calendar Tool: Deleting calendar event ID '{calendar_id}'")
    global mock_calendar
    original_len = len(mock_calendar)
    mock_calendar = [e for e in mock_calendar if e["id"] != calendar_id]
    if len(mock_calendar) < original_len:
        return f"Successfully deleted calendar event '{calendar_id}'."
    return f"Calendar event ID '{calendar_id}' not found."
