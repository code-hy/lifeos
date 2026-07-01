import logging

logger = logging.getLogger("LifeOS.Agents.Specialized")

class FinanceAgent:
    def __init__(self):
        pass
    
    def analyze_spending_spike(self, current_bill: float, average_bill: float) -> dict:
        """
        Analyze a spending spike and suggest alternative cheaper utility providers.
        """
        spike_percent = ((current_bill - average_bill) / average_bill) * 100
        alternative_providers = [
            {"name": "EcoGreen Power", "rate_per_kwh": 0.12, "estimated_monthly_savings": 45.00},
            {"name": "GridChoice Energy", "rate_per_kwh": 0.11, "estimated_monthly_savings": 58.00}
        ]
        return {
            "current_bill": current_bill,
            "average_bill": average_bill,
            "spike_amount": round(current_bill - average_bill, 2),
            "spike_percentage": round(spike_percent, 1),
            "alternatives": alternative_providers,
            "recommendation": "Switching to GridChoice Energy could save you approximately $58.00 per month."
        }

class TravelAgent:
    def __init__(self):
        pass
        
    def resolve_delay(self, flight_info: dict, calendar_events: list) -> dict:
        """
        Calculate conflicts and schedule revisions based on flight delay.
        """
        delay_min = flight_info.get("delay_minutes", 0)
        conflicts = []
        for event in calendar_events:
            # Check for dinner or team alignment events that overlap with delayed flight
            if "Dinner" in event["title"] or "Meeting" in event["title"]:
                conflicts.append(event)
        
        suggested_actions = []
        for c in conflicts:
            if "Dinner" in c["title"]:
                # Reschedule dinner to later
                suggested_actions.append({
                    "action": "reschedule_calendar_event",
                    "event_id": c["id"],
                    "title": c["title"],
                    "original_time": c["start"],
                    "suggested_time": "2026-07-01T21:30:00",
                    "reason": f"Rescheduled due to flight delay of {delay_min} mins"
                })
            else:
                # Postpone team meeting to next day
                suggested_actions.append({
                    "action": "reschedule_calendar_event",
                    "event_id": c["id"],
                    "title": c["title"],
                    "original_time": c["start"],
                    "suggested_time": "2026-07-02T10:00:00",
                    "reason": "Postponed to tomorrow morning due to late flight arrival"
                })
        
        return {
            "delay_minutes": delay_min,
            "conflicts": conflicts,
            "suggested_actions": suggested_actions
        }

class HealthAgent:
    def __init__(self):
        pass
        
    def generate_health_summary(self, metrics: dict) -> str:
        """
        Generate a nice textual report of health metrics.
        """
        active_min = metrics.get("weekly_active_minutes", 0)
        workouts = metrics.get("logged_workouts", [])
        
        summary = (
            f"Weekly Health Summary:\n"
            f"- Total active time: {active_min} minutes.\n"
            f"- Workouts logged: {len(workouts)} session(s).\n"
            f"- Daily average steps: {metrics.get('avg_daily_steps', 0)} steps.\n"
            f"- Average sleep: {metrics.get('average_sleep_hours', 0.0)} hours.\n"
        )
        if active_min > 60:
            summary += "Keep it up! You're meeting your fitness goals."
        else:
            summary += "Try to sneak in a 15-minute walk today to boost your active minutes!"
        return summary
