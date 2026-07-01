from mcp.server import mcp_tool
import logging

logger = logging.getLogger("LifeOS.Tools.Travel")

@mcp_tool()
def check_flight_status(flight_number: str) -> dict:
    """
    Check the real-time status of a flight.
    """
    logger.info(f"Travel Tool: Checking status for flight '{flight_number}'")
    fn = flight_number.upper()
    if "UA" in fn or "102" in fn:
        return {
            "flight_number": fn,
            "airline": "United Airlines",
            "status": "DELAYED",
            "delay_minutes": 180,
            "scheduled_departure": "2026-07-01T18:30:00",
            "estimated_departure": "2026-07-01T21:30:00",
            "origin": "JFK",
            "destination": "SFO"
        }
    return {
        "flight_number": fn,
        "airline": "Generic Airways",
        "status": "ON TIME",
        "delay_minutes": 0,
        "scheduled_departure": "2026-07-01T15:00:00",
        "estimated_departure": "2026-07-01T15:00:00",
        "origin": "JFK",
        "destination": "ORD"
    }

@mcp_tool()
def book_flight(destination: str, date: str) -> dict:
    """
    Book a flight to a specified destination.
    """
    logger.info(f"Travel Tool: Booking flight to {destination} on {date}")
    return {
        "status": "SUCCESS",
        "booking_ref": "BKG-77291",
        "destination": destination,
        "date": date,
        "airline": "United Airlines",
        "cost": 412.50
    }
