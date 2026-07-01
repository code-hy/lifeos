from mcp.server import mcp_tool
import logging

logger = logging.getLogger("LifeOS.Tools.Health")

mock_workouts = [
    {"exercise": "Running", "duration": 30},
    {"exercise": "Strength Training", "duration": 45}
]

@mcp_tool()
def log_workout(exercise: str, duration: int) -> str:
    """
    Log a physical exercise activity.
    """
    logger.info(f"Health Tool: Logging workout '{exercise}' for {duration} minutes.")
    mock_workouts.append({"exercise": exercise, "duration": duration})
    return f"Successfully logged {duration}-minute workout: {exercise}."

@mcp_tool()
def get_health_metrics() -> dict:
    """
    Retrieve summaries of your active health tracker data.
    """
    logger.info("Health Tool: Querying health metrics.")
    return {
        "weekly_active_minutes": sum(w["duration"] for w in mock_workouts),
        "logged_workouts": mock_workouts,
        "average_sleep_hours": 7.4,
        "avg_daily_steps": 8450
    }
