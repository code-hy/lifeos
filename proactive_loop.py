import os
import json
import sqlite3
import asyncio
import logging
from datetime import datetime
from core.orchestrator import ExecutiveOrchestrator

logger = logging.getLogger("LifeOS.ProactiveLoop")

class ProactiveMonitor:
    def __init__(self, orchestrator: ExecutiveOrchestrator = None):
        self.orchestrator = orchestrator or ExecutiveOrchestrator()
        self.db_path = self.orchestrator.db_path
        self.is_running = False
        self._init_db()
        self.pending_triggers = asyncio.Queue()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Table to store logs of autonomous events triggered by the loop
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proactive_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                query TEXT NOT NULL,
                status TEXT NOT NULL,
                response TEXT,
                details TEXT
            )
        """)
        conn.commit()
        conn.close()

    def log_proactive_event(self, event_type: str, query: str, status: str, response: str = "", details: dict = None) -> int:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO proactive_logs (timestamp, event_type, query, status, response, details)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.utcnow().isoformat(),
                    event_type,
                    query,
                    status,
                    response,
                    json.dumps(details) if details else "{}"
                )
            )
            inserted_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return inserted_id
        except Exception as e:
            logger.error(f"Failed to log proactive event: {e}")
            return -1

    def update_proactive_log_status(self, log_id: int, status: str, response: str, details: dict = None):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE proactive_logs SET status = ?, response = ?, details = ? WHERE id = ?",
                (status, response, json.dumps(details) if details else "{}", log_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update proactive log {log_id}: {e}")

    def get_proactive_logs(self, limit: int = 50) -> list[dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM proactive_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [
                {
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "event_type": r["event_type"],
                    "query": r["query"],
                    "status": r["status"],
                    "response": r["response"],
                    "details": json.loads(r["details"]) if r["details"] else {}
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Error fetching proactive logs: {e}")
            return []

    async def trigger_event(self, event_type: str):
        """Queue a manual proactive trigger for immediate execution."""
        await self.pending_triggers.put(event_type)
        logger.info(f"Queued proactive trigger event: {event_type}")

    async def run_loop(self):
        self.is_running = True
        logger.info("LifeOS Proactive Loop started.")
        
        # Scan frequency (e.g. check every 30 seconds for pending triggers or scheduled checks)
        scan_interval = 30 
        counter = 0

        while self.is_running:
            try:
                # 1. Check for queued manual triggers first (immediate)
                try:
                    event_type = await asyncio.wait_for(self.pending_triggers.get(), timeout=1.0)
                    await self._process_event(event_type)
                    self.pending_triggers.task_done()
                    continue  # loop immediately to check if there are more
                except asyncio.TimeoutError:
                    pass

                # 2. Simulated periodic scan (e.g. check every 5 minutes in background)
                counter += 1
                if counter >= (300 / scan_interval):  # 5 minutes
                    counter = 0
                    logger.info("LifeOS: Background scan running...")
                    # Simulating passive event check
                    # In a real environment, we'd query IMAP for emails, APIs for flights, etc.
                    # Here we check if there are specific new updates
                    pass

                await asyncio.sleep(scan_interval)

            except asyncio.CancelledError:
                logger.info("Proactive loop execution cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in proactive loop execution: {e}")
                await asyncio.sleep(5)

    async def _process_event(self, event_type: str):
        logger.info(f"Processing proactive event: {event_type}")
        
        query = ""
        if event_type == "flight_delay":
            query = "My flight UA102 is delayed. Reschedule my evening and notify my wife."
        elif event_type == "bill_spike":
            query = "Analyze the unread utility bill email for spending spikes and recommend alternative cheaper utility providers."
        elif event_type == "workout_reminder":
            query = "Retrieve weekly health metrics and recommend a workout routine."
        else:
            logger.warning(f"Unknown event type: {event_type}")
            return

        # Log running state
        log_id = self.log_proactive_event(event_type, query, "RUNNING")
        
        try:
            # Execute autonomously
            result = await self.orchestrator.handle_request(query)
            status = result.get("status")
            response = result.get("response", "")
            
            # Map statuses
            log_status = "SUCCESS"
            if status == "HOLD":
                log_status = "HOLD"
            elif status == "BLOCKED":
                log_status = "BLOCKED"
            elif status == "ERROR":
                log_status = "ERROR"

            self.update_proactive_log_status(log_id, log_status, response, result)
            logger.info(f"Autonomous event '{event_type}' processed with status: {log_status}")
            
        except Exception as e:
            logger.error(f"Error processing proactive event {event_type}: {e}")
            self.update_proactive_log_status(log_id, "ERROR", str(e))

    def stop(self):
        self.is_running = False
        logger.info("LifeOS Proactive Loop stopped.")
