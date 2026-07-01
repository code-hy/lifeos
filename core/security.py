import os
import sqlite3
import uuid
import json
import logging
from datetime import datetime

logger = logging.getLogger("LifeOS.Security")

class SecurityGuard:
    def __init__(self):
        # Restricted tools that require manual approval
        self.restricted_tools = ["transfer_funds", "delete_calendar", "send_email"]
        
        # Determine database directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_dir = os.path.join(base_dir, "data")
        os.makedirs(self.db_dir, exist_ok=True)
        self.db_path = os.path.join(self.db_dir, "lifeos.db")
        
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create approvals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                tool_name TEXT NOT NULL,
                parameters TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                decided_at TEXT
            )
        """)
        
        # Create security logs table for auditing
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                detail TEXT NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()

    def log_event(self, event_type: str, detail: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO security_logs (timestamp, event_type, detail) VALUES (?, ?, ?)",
                (datetime.utcnow().isoformat(), event_type, detail)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")

    def is_safe(self, query: str) -> bool:
        """Perform basic prompt injection & safety validation."""
        # Check for simple dangerous injections
        malicious_patterns = [
            "ignore all previous instructions",
            "bypass security",
            "disable guardrails",
            "system override",
            "sudo rm",
            "delete database"
        ]
        query_lower = query.lower()
        for pattern in malicious_patterns:
            if pattern in query_lower:
                self.log_event("BLOCKED_INPUT", f"Query contained blocked pattern: {pattern}")
                return False
        
        self.log_event("VALIDATED_INPUT", f"Query passed safety check: {query[:50]}...")
        return True

    def validate_action(self, tool_name: str, params: dict) -> dict:
        """
        Validate whether a tool execution is safe.
        Returns:
            {"status": "APPROVED"} or {"status": "HOLD", "reason": "...", "approval_id": "..."}
        """
        if tool_name in self.restricted_tools:
            approval_id = str(uuid.uuid4())
            params_str = json.dumps(params)
            
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO approvals (id, tool_name, parameters, status, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (approval_id, tool_name, params_str, "PENDING", datetime.utcnow().isoformat())
                )
                conn.commit()
                conn.close()
                
                self.log_event("APPROVAL_CREATED", f"Tool '{tool_name}' put on HOLD. Approval ID: {approval_id}")
                return {
                    "status": "HOLD",
                    "reason": f"Manual approval required for restricted tool: {tool_name}",
                    "approval_id": approval_id
                }
            except Exception as e:
                logger.error(f"Error logging approval request: {e}")
                return {
                    "status": "HOLD",
                    "reason": f"Database logging error. Safe-blocking tool: {tool_name}",
                    "approval_id": "ERROR"
                }
        
        self.log_event("TOOL_AUTO_APPROVED", f"Tool '{tool_name}' auto-approved.")
        return {"status": "APPROVED"}

    def get_pending_approvals(self) -> list[dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM approvals WHERE status = 'PENDING' ORDER BY created_at DESC")
            rows = cursor.fetchall()
            conn.close()
            
            approvals = []
            for row in rows:
                approvals.append({
                    "id": row["id"],
                    "tool_name": row["tool_name"],
                    "parameters": json.loads(row["parameters"]),
                    "status": row["status"],
                    "created_at": row["created_at"]
                })
            return approvals
        except Exception as e:
            logger.error(f"Error fetching pending approvals: {e}")
            return []

    def get_approval(self, approval_id: str) -> dict:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    "id": row["id"],
                    "tool_name": row["tool_name"],
                    "parameters": json.loads(row["parameters"]),
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "decided_at": row["decided_at"]
                }
        except Exception as e:
            logger.error(f"Error fetching approval {approval_id}: {e}")
        return None

    def decide_action(self, approval_id: str, approve: bool) -> bool:
        status = "APPROVED" if approve else "REJECTED"
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if it exists and is pending
            cursor.execute("SELECT status FROM approvals WHERE id = ?", (approval_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return False
            
            cursor.execute(
                "UPDATE approvals SET status = ?, decided_at = ? WHERE id = ?",
                (status, datetime.utcnow().isoformat(), approval_id)
            )
            conn.commit()
            conn.close()
            
            self.log_event("APPROVAL_DECIDED", f"Approval {approval_id} set to {status}")
            return True
        except Exception as e:
            logger.error(f"Error deciding approval {approval_id}: {e}")
            return False

    def get_logs(self, limit: int = 50) -> list[dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM security_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [{"timestamp": r["timestamp"], "event_type": r["event_type"], "detail": r["detail"]} for r in rows]
        except Exception as e:
            logger.error(f"Error fetching logs: {e}")
            return []
