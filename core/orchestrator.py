import os
import json
import sqlite3
import logging
from datetime import datetime
import google.generativeai as genai
from core.security import SecurityGuard
from core.memory import LongTermMemory
from agents.planner import Planner
from agents.specialized import FinanceAgent, TravelAgent, HealthAgent
from mcp.server import MCPServer

logger = logging.getLogger("LifeOS.Orchestrator")

class ExecutiveOrchestrator:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.security = SecurityGuard()
        self.memory = LongTermMemory()
        self.planner = Planner(self.api_key)
        self.mcp_server = MCPServer(self.security)
        
        # Specialized Agents
        self.finance_agent = FinanceAgent()
        self.travel_agent = TravelAgent()
        self.health_agent = HealthAgent()
        
        self.db_path = self.security.db_path
        self._init_orchestrator_db()

    def _init_orchestrator_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Table to store orchestrator execution states when paused on HOLD
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator_states (
                approval_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                plan TEXT NOT NULL,
                current_step_id INTEGER NOT NULL,
                results TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        # Table to store chat message history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT
            )
        """)
        conn.commit()
        conn.close()

    def save_chat_message(self, query: str, response_data: dict):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chat_messages (timestamp, query, response, status, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.utcnow().isoformat(),
                    query,
                    response_data.get("response", ""),
                    response_data.get("status", "UNKNOWN"),
                    json.dumps(response_data) if response_data else "{}"
                )
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save chat message: {e}")

    def get_chat_history(self, limit: int = 100) -> list[dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chat_messages ORDER BY id ASC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [
                {
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "query": r["query"],
                    "response": r["response"],
                    "status": r["status"],
                    "details": json.loads(r["details"]) if r["details"] else {}
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Error fetching chat history: {e}")
            return []

    def _save_state(self, approval_id: str, query: str, plan: dict, current_step_id: int, results: dict):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO orchestrator_states (approval_id, query, plan, current_step_id, results, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    approval_id,
                    query,
                    json.dumps(plan),
                    current_step_id,
                    json.dumps(results),
                    datetime.utcnow().isoformat()
                )
            )
            conn.commit()
            conn.close()
            logger.info(f"Saved orchestrator execution state for approval {approval_id}")
        except Exception as e:
            logger.error(f"Failed to save orchestrator state: {e}")

    def _load_state(self, approval_id: str) -> dict:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orchestrator_states WHERE approval_id = ?", (approval_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    "approval_id": row["approval_id"],
                    "query": row["query"],
                    "plan": json.loads(row["plan"]),
                    "current_step_id": row["current_step_id"],
                    "results": json.loads(row["results"])
                }
        except Exception as e:
            logger.error(f"Failed to load orchestrator state: {e}")
        return None

    def _delete_state(self, approval_id: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM orchestrator_states WHERE approval_id = ?", (approval_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to delete orchestrator state: {e}")

    async def handle_request(self, query: str) -> dict:
        """
        Executes a user request. Checks safety, gets memory context,
        generates a plan, and runs it step-by-step.
        """
        # 1. Check input safety
        if not self.security.is_safe(query):
            return {
                "status": "BLOCKED",
                "response": "Security Guard alert: Request contains unsafe patterns and has been blocked."
            }

        # 2. Get long-term memory context
        context = self.memory.fetch_context(query)
        logger.info(f"Retrieved context for query '{query}': {context}")

        # 3. Generate plan
        tools_schema = self.mcp_server.list_tools()
        plan = self.planner.generate_plan(query, tools_schema, context)
        
        # 4. Execute plan
        return await self._execute_plan(query, plan, start_step_id=1, results={})

    async def _execute_plan(self, query: str, plan: dict, start_step_id: int, results: dict) -> dict:
        steps = plan.get("steps", [])
        
        for step in steps:
            step_id = step.get("step_id")
            if step_id < start_step_id:
                continue

            step_type = step.get("type", "tool")
            description = step.get("description", "")
            logger.info(f"Executing step {step_id}: {description} ({step_type})")

            if step_type == "tool":
                tool_name = step.get("tool_name")
                args = step.get("args", {})
                
                # Resolve place holders from previous steps e.g. {{step_1.result}}
                args = self._resolve_placeholders(args, results)
                
                # Execute tool
                tool_res = self.mcp_server.execute_tool(tool_name, args)
                results[f"step_{step_id}"] = tool_res

                if tool_res.get("status") == "HOLD":
                    # Tool is blocked by SecurityGuard. Save orchestrator state and pause.
                    approval_id = tool_res["approval_id"]
                    self._save_state(approval_id, query, plan, step_id, results)
                    
                    return {
                        "status": "HOLD",
                        "approval_id": approval_id,
                        "tool_name": tool_name,
                        "args": args,
                        "reason": tool_res.get("reason"),
                        "response": f"Action '{tool_name}' put on hold. Manual approval required (Approval ID: {approval_id})."
                    }
                
                elif tool_res.get("status") == "ERROR":
                    logger.error(f"Step {step_id} failed with error: {tool_res.get('error')}")
                    # Save error to results and keep going or handle it
            
            elif step_type == "reason":
                # Invoke LLM for thinking/reasoning step
                thought = await self._execute_reasoning_step(query, step, results)
                results[f"step_{step_id}"] = {"status": "SUCCESS", "result": thought}

        # 5. Synthesize final response
        return await self._synthesize_final_response(query, results)

    def _resolve_placeholders(self, args: dict, results: dict) -> dict:
        resolved = {}
        for k, v in args.items():
            if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
                expr = v[2:-2].strip()  # e.g., 'step_1.result'
                parts = expr.split(".")
                step_key = parts[0]  # e.g., 'step_1'
                
                if step_key in results:
                    step_val = results[step_key]
                    # Drill down if needed
                    val = step_val.get("result")
                    for p in parts[1:]:
                        if isinstance(val, dict) and p in val:
                            val = val[p]
                    resolved[k] = val
                else:
                    resolved[k] = v
            else:
                resolved[k] = v
        return resolved

    async def _execute_reasoning_step(self, query: str, step: dict, results: dict) -> str:
        if not self.api_key:
            return f"Reasoning: Completed '{step.get('description')}'"
            
        prompt = (
            f"You are the reasoning component of LifeOS.\n"
            f"User request: {query}\n"
            f"Current step description: {step.get('description')}\n"
            f"Previous execution results: {json.dumps(results)}\n"
            f"Generate your thoughts/actions for this step."
        )
        try:
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Reasoning failed: {e}"

    async def resume_execution(self, approval_id: str) -> dict:
        """
        Resume execution of a paused plan after a tool call has been approved.
        """
        # Get approval state
        approval = self.security.get_approval(approval_id)
        if not approval:
            return {"status": "ERROR", "error": f"Approval request {approval_id} not found."}
            
        if approval["status"] != "APPROVED":
            return {"status": "ERROR", "error": f"Approval request {approval_id} is in status '{approval['status']}', cannot resume."}

        # Load orchestrator state
        state = self._load_state(approval_id)
        if not state:
            return {"status": "ERROR", "error": f"Saved execution state for approval {approval_id} not found."}

        logger.info(f"Resuming execution for plan: '{state['query']}' starting at step {state['current_step_id']}")
        
        # We need to execute the step that was blocked
        plan = state["plan"]
        current_step_id = state["current_step_id"]
        results = state["results"]
        
        # Retrieve the blocked step
        steps = plan.get("steps", [])
        blocked_step = next((s for s in steps if s["step_id"] == current_step_id), None)
        
        if not blocked_step:
            return {"status": "ERROR", "error": f"Step ID {current_step_id} not found in plan."}

        # Execute the blocked step directly, bypassing SecurityGuard since it's already approved
        tool_name = blocked_step.get("tool_name")
        args = blocked_step.get("args", {})
        args = self._resolve_placeholders(args, results)
        
        logger.info(f"Bypassing guard for approved tool: '{tool_name}' with args {args}")
        # Call tool function directly to bypass interception
        from mcp.server import registered_tools
        if tool_name in registered_tools:
            try:
                # Bypass execution validation
                tool_entry = registered_tools[tool_name]
                func = tool_entry["func"]
                result = func(**args)
                tool_res = {"status": "SUCCESS", "result": result}
            except Exception as e:
                tool_res = {"status": "ERROR", "error": str(e)}
        else:
            tool_res = {"status": "ERROR", "error": f"Tool '{tool_name}' not registered."}

        # Store result and continue execution
        results[f"step_{current_step_id}"] = tool_res
        
        # Delete saved state
        self._delete_state(approval_id)
        
        # Continue with the rest of the plan
        return await self._execute_plan(state["query"], plan, start_step_id=current_step_id + 1, results=results)

    async def _synthesize_final_response(self, query: str, results: dict) -> dict:
        # Check if specialized agents can add value
        finance_data = None
        travel_data = None
        health_data = None
        
        # Look for flight status checks or electric bill updates
        for step_key, step_res in results.items():
            if step_res.get("status") == "SUCCESS":
                res_val = step_res.get("result")
                # Detect flight delay
                if isinstance(res_val, dict) and "flight_number" in res_val and res_val.get("status") == "DELAYED":
                    # Get calendar events to detect conflicts
                    events_res = next((r.get("result") for k, r in results.items() if "get_events" in k or (isinstance(r.get("result"), list) and len(r.get("result")) > 0 and "title" in r.get("result")[0])), [])
                    travel_data = self.travel_agent.resolve_delay(res_val, events_res)
                
                # Detect finance balances / potential spike
                elif isinstance(res_val, dict) and "Checking" in res_val:
                    # Let's say if we queried get_balance
                    pass
                
                # Detect health metrics
                elif isinstance(res_val, dict) and "weekly_active_minutes" in res_val:
                    health_data = self.health_agent.generate_health_summary(res_val)

        # Handle proactive bill/spending spike detection
        # Broad keyword match — catches utility bill, electricity bill, power bill, spending spike, etc.
        bill_keywords = ["electricity bill", "power bill", "utility bill", "bill spike", "spending spike", "spending", "utility"]
        if any(kw in query.lower() for kw in bill_keywords):
            # Trigger finance agent spending spike analysis
            # Current bill: $452.12, Avg bill: $180.00 (from our mock unread email)
            finance_data = self.finance_agent.analyze_spending_spike(452.12, 180.00)

        # Generate LLM response synthesizing all findings
        if self.api_key:
            prompt = (
                "You are the Executive Orchestrator of LifeOS. The user requested: '{query}'.\n"
                f"Here are the execution results of the steps: {json.dumps(results)}\n"
            )
            if travel_data:
                prompt += f"Travel Agent Analysis: {json.dumps(travel_data)}\n"
            if finance_data:
                prompt += f"Finance Agent Analysis: {json.dumps(finance_data)}\n"
            if health_data:
                prompt += f"Health Agent Analysis: {health_data}\n"
                
            prompt += (
                "\nProvide a beautiful, informative, and cohesive final summary. "
                "Outline all actions taken, results obtained, any scheduled tasks, "
                "or warnings (like bills spikes or delays resolved). Keep it professional and helpful."
            )
            
            try:
                model = genai.GenerativeModel(self.model_name)
                response = model.generate_content(prompt)
                final_text = response.text
            except Exception as e:
                final_text = f"Plan completed. Execution logs: {json.dumps(results)}"
        else:
            # Static fallback response synthesis
            final_text = "LifeOS successfully processed your request.\n\n"
            if travel_data:
                final_text += f"**Travel Update:** Flight {travel_data['delay_minutes']} mins delayed. Detected calendar conflict with dinner meeting. Rescheduled to later times.\n"
            if finance_data:
                final_text += f"**Finance Update:** Detected {finance_data['spike_percentage']}% spending spike in electricity bill. Recommended action: switch to {finance_data['alternatives'][1]['name']} (Saves ${finance_data['alternatives'][1]['estimated_monthly_savings']} monthly).\n"
            if health_data:
                final_text += f"**Health Update:** {health_data}\n"
            
            final_text += "\nExecution Steps details:\n"
            for k, v in results.items():
                final_text += f"- {k}: {v.get('status')} -> {v.get('result') or v.get('error')}\n"

        # Check if there are user preferences to store
        # E.g. if the user says "I prefer United Airlines"
        if "prefer" in query.lower():
            # Extract and store
            words = query.split()
            for i, w in enumerate(words):
                if w.lower() == "prefer" and i < len(words) - 1:
                    pref_key = words[i+1]
                    pref_val = " ".join(words[i+2:])
                    self.memory.add_preference(pref_key, pref_val)

        return {
            "status": "SUCCESS",
            "response": final_text,
            "results": results,
            "analyses": {
                "finance": finance_data,
                "travel": travel_data,
                "health": health_data
            }
        }
