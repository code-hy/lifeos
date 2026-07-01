from mcp.server import mcp_tool
import logging
import urllib.request
import urllib.parse
import json

logger = logging.getLogger("LifeOS.Tools.Weather")

@mcp_tool()
def get_forecast(city: str) -> str:
    """
    Get the current weather and a 3-day forecast for a given city.
    Uses wttr.in (no API key required).
    """
    logger.info(f"Weather Tool: Fetching forecast for '{city}'")
    try:
        encoded = urllib.parse.quote(city)
        url = f"https://wttr.in/{encoded}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "LifeOS/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        current = data.get("current_condition", [{}])[0]
        weather_desc = current.get("weatherDesc", [{}])[0].get("value", "Unknown")
        temp_c = current.get("temp_C", "?")
        feels_like = current.get("FeelsLikeC", "?")
        humidity = current.get("humidity", "?")
        wind = current.get("windspeedKmph", "?")
        uv = current.get("uvIndex", "?")

        lines = [
            f"Weather in {city}:",
            f"  Condition: {weather_desc}",
            f"  Temperature: {temp_c}°C (feels like {feels_like}°C)",
            f"  Humidity: {humidity}%",
            f"  Wind: {wind} km/h",
            f"  UV Index: {uv}",
        ]

        forecast = data.get("weather", [])
        if forecast:
            lines.append("\n3-Day Forecast:")
            for day in forecast[:3]:
                date = day.get("date", "?")
                desc = day.get("hourly", [{}])[4].get("weatherDesc", [{}])[0].get("value", "?") if len(day.get("hourly", [])) > 4 else "?"
                max_c = day.get("maxtempC", "?")
                min_c = day.get("mintempC", "?")
                lines.append(f"  {date}: {desc}, {min_c}–{max_c}°C")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Weather fetch failed: {e}")
        return f"Weather data unavailable for '{city}': {e}"
