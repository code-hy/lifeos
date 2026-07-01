import os
import json
import logging
import google.generativeai as genai

logger = logging.getLogger("LifeOS.Agents.Planner")

class Planner:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
        # Using Gemini 2.0 Flash
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        
    def generate_plan(self, query: str, tools_schema: list, context: str = "") -> dict:
        """
        Decomposes a query into a structured execution plan.
        Returns a dictionary with a list of steps.
        """
        if not self.api_key:
            logger.warning("No Gemini API key found. Generating simple static plan.")
            return self._generate_static_plan(query)

        tools_str = json.dumps(tools_schema, indent=2)
        
        system_instruction = (
            "You are the Executive Planner Agent of LifeOS, a personal autonomous operating system.\n"
            "Your job is to analyze the User's query and generate a structured JSON plan to resolve it "
            "using the available MCP tools.\n\n"
            "AVAILABLE TOOLS:\n"
            f"{tools_str}\n\n"
            "CONTEXT (User Preferences & History):\n"
            f"{context}\n\n"
            "INSTRUCTIONS:\n"
            "1. Decompose the request into logical sequential steps.\n"
            "2. Each step should be either a tool call or a reasoning step.\n"
            "3. If a tool call requires arguments that are outputs from a previous step, "
            "use a placeholder like '{{step_1.result}}' or reference the parameter value. But provide actual values if they are known.\n"
            "4. You MUST output a JSON object strictly containing a 'steps' key, which is a list of step objects.\n"
            "5. Do NOT include any markdown blocks (like ```json) or explanation outside the JSON. Return raw JSON only.\n\n"
            "JSON SCHEMA:\n"
            "{\n"
            "  \"steps\": [\n"
            "    {\n"
            "      \"step_id\": 1,\n"
            "      \"type\": \"tool\" | \"reason\",\n"
            "      \"tool_name\": \"name_of_tool_to_call_if_tool_type\",\n"
            "      \"args\": { \"arg_name\": \"value\" },\n"
            "      \"description\": \"Brief text describing what this step achieves\"\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        try:
            model = genai.GenerativeModel(
                self.model_name,
                generation_config={"response_mime_type": "application/json"}
            )
            response = model.generate_content(
                contents=[
                    {"role": "user", "parts": [f"System:\n{system_instruction}\n\nUser Query: {query}"]}
                ]
            )
            
            plan_data = json.loads(response.text)
            logger.info(f"Generated plan via LLM: {plan_data}")
            return plan_data
        except Exception as e:
            logger.error(f"Error generating LLM plan: {e}. Falling back to rule-based planner.")
            return self._generate_static_plan(query)

    def _generate_static_plan(self, query: str) -> dict:
        """Rule-based backup planner if LLM call fails or API key is missing."""
        query_lower = query.lower()
        steps = []
        
        if "flight" in query_lower or "delayed" in query_lower:
            steps.append({
                "step_id": 1,
                "type": "tool",
                "tool_name": "check_flight_status",
                "args": {"flight_number": "UA102"},
                "description": "Checking flight delay status."
            })
            steps.append({
                "step_id": 2,
                "type": "tool",
                "tool_name": "get_events",
                "args": {},
                "description": "Retrieve current evening calendar events."
            })
            steps.append({
                "step_id": 3,
                "type": "tool",
                "tool_name": "create_calendar_event",
                "args": {
                    "title": "Delayed Flight Arrival (Rescheduled)",
                    "start_time": "2026-07-01T21:30:00",
                    "end_time": "2026-07-01T22:30:00",
                    "description": "Automated update from LifeOS due to UA102 delay."
                },
                "description": "Add new calendar entry for delay."
            })
            steps.append({
                "step_id": 4,
                "type": "tool",
                "tool_name": "send_email",
                "args": {
                    "to": "wife@family.com",
                    "subject": "Flight Delayed - Update",
                    "body": "Hey, my flight UA102 is delayed. Rescheduling my evening, see you around 9:30 PM."
                },
                "description": "Notify wife of the delay."
            })
        elif "balance" in query_lower or "how much" in query_lower:
            steps.append({
                "step_id": 1,
                "type": "tool",
                "tool_name": "get_balance",
                "args": {},
                "description": "Check current accounts balances."
            })
        elif "transfer" in query_lower or "send money" in query_lower:
            steps.append({
                "step_id": 1,
                "type": "tool",
                "tool_name": "transfer_funds",
                "args": {"amount": 250.0, "recipient": "Alice"},
                "description": "Transfer funds."
            })
        elif "workout" in query_lower or "exercise" in query_lower:
            steps.append({
                "step_id": 1,
                "type": "tool",
                "tool_name": "log_workout",
                "args": {"exercise": "Running", "duration": 30},
                "description": "Log exercise."
            })
        elif any(w in query_lower for w in ["utility bill", "electricity bill", "power bill", "bill spike", "spending spike", "spending"]):
            steps.append({
                "step_id": 1,
                "type": "tool",
                "tool_name": "read_emails",
                "args": {},
                "description": "Read unread emails to find the utility bill."
            })
            steps.append({
                "step_id": 2,
                "type": "tool",
                "tool_name": "get_balance",
                "args": {},
                "description": "Check account balance."
            })
            steps.append({
                "step_id": 3,
                "type": "reason",
                "tool_name": "",
                "args": {},
                "description": "Analyze bill spike and recommend cheaper providers."
            })
        elif any(w in query_lower for w in ["weather", "forecast", "temperature"]):
            # Extract city if mentioned, default to current location
            city = "New York"
            import re
            m = re.search(r'\b(?:in|for|at)\s+([A-Za-z\s]+?)(?:\?|$|\.)', query)
            if m:
                city = m.group(1).strip()
            steps.append({
                "step_id": 1,
                "type": "tool",
                "tool_name": "get_forecast",
                "args": {"city": city},
                "description": f"Fetch weather forecast for {city}."
            })
        elif any(w in query_lower for w in ["search", "look up", "find", "what is", "who is", "tell me about"]):
            # Extract the search query after the trigger word
            search_query = query
            import re
            for trigger in ["search for ", "search ", "look up ", "find ", "what is ", "who is ", "tell me about "]:
                if trigger in query_lower:
                    idx = query_lower.index(trigger) + len(trigger)
                    search_query = query[idx:].strip().rstrip("?.")
                    break
            steps.append({
                "step_id": 1,
                "type": "tool",
                "tool_name": "search_web",
                "args": {"query": search_query},
                "description": f"Search the web for '{search_query}'."
            })
        elif "day" in query_lower or "schedule" in query_lower or "calendar" in query_lower:
            steps.append({
                "step_id": 1,
                "type": "tool",
                "tool_name": "get_events",
                "args": {},
                "description": "Fetch today's calendar events."
            })
            steps.append({
                "step_id": 2,
                "type": "reason",
                "tool_name": "",
                "args": {},
                "description": "Summarize the day's schedule."
            })
        else:
            # General reasoning
            steps.append({
                "step_id": 1,
                "type": "reason",
                "tool_name": "",
                "args": {},
                "description": "General life management request."
            })
            
        return {"steps": steps}
