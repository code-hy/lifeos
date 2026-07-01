import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("LifeOS")

from core.orchestrator import ExecutiveOrchestrator
from proactive_loop import ProactiveMonitor

# Setup orchestrator & monitor
orchestrator = ExecutiveOrchestrator()
proactive_monitor = ProactiveMonitor(orchestrator)
proactive_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background proactive loop task
    global proactive_task
    logger.info("Starting background proactive monitor loop...")
    proactive_task = asyncio.create_task(proactive_monitor.run_loop())
    yield
    # Shutdown: Stop proactive loop task
    logger.info("Stopping background proactive monitor loop...")
    proactive_monitor.stop()
    if proactive_task:
        proactive_task.cancel()
        try:
            await proactive_task
        except asyncio.CancelledError:
            pass
        logger.info("Background proactive loop task stopped.")

app = FastAPI(
    title="LifeOS - Executive Agent Dashboard",
    description="Autonomous Agentic OS with RAG Memory and Security Firewalls",
    lifespan=lifespan
)

# API schemas
class QueryPayload(BaseModel):
    query: str

class DecisionPayload(BaseModel):
    approve: bool

class PreferencePayload(BaseModel):
    key: str
    value: str

class ProactiveTriggerPayload(BaseModel):
    event_type: str

# Templates setup
base_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(base_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)

# Create templates dir if not exists
os.makedirs(templates_dir, exist_ok=True)

# ----------------- HTML Dashboard Route -----------------

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Serve the central LifeOS Dashboard UI."""
    return templates.TemplateResponse(request, "index.html", {"request": request})

# ----------------- API Endpoints -----------------

@app.post("/api/ask")
async def ask_orchestrator(payload: QueryPayload):
    """Send a user request to the Executive Orchestrator."""
    try:
        result = await orchestrator.handle_request(payload.query)
        orchestrator.save_chat_message(payload.query, result)
        return result
    except Exception as e:
        logger.exception("Error processing request")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/history")
async def get_chat_history():
    """Retrieve persisted chat message history."""
    return orchestrator.get_chat_history()

@app.get("/api/approvals")
async def list_approvals():
    """List all pending security approvals."""
    return orchestrator.security.get_pending_approvals()

@app.post("/api/approvals/{approval_id}/decide")
async def decide_approval(approval_id: str, payload: DecisionPayload):
    """Approve or reject a pending security approval."""
    # 1. Process choice in SecurityGuard
    success = orchestrator.security.decide_action(approval_id, payload.approve)
    if not success:
        raise HTTPException(status_code=404, detail="Approval request not found or already processed.")
    
    if payload.approve:
        # 2. Resume execution and return final result
        try:
            result = await orchestrator.resume_execution(approval_id)
            return {"status": "RESUMED", "result": result}
        except Exception as e:
            logger.exception("Error resuming execution")
            raise HTTPException(status_code=500, detail=f"Failed to resume execution: {str(e)}")
    else:
        return {"status": "REJECTED", "response": f"Action {approval_id} rejected by user."}

@app.get("/api/memory")
async def list_memory():
    """Get all stored user preferences."""
    return orchestrator.memory.get_all_preferences()

@app.post("/api/memory")
async def add_memory(payload: PreferencePayload):
    """Manually add a user preference to memory."""
    orchestrator.memory.add_preference(payload.key, payload.value)
    return {"status": "SUCCESS", "message": f"Preference '{payload.key}' stored."}

@app.post("/api/memory/clear")
async def clear_memory():
    """Clear memory database."""
    orchestrator.memory.clear_memory()
    return {"status": "SUCCESS", "message": "Memory cleared."}

@app.post("/api/proactive/trigger")
async def trigger_proactive_event(payload: ProactiveTriggerPayload):
    """Manually inject/trigger an autonomous proactive event (flight_delay, bill_spike, workout_reminder)."""
    await proactive_monitor.trigger_event(payload.event_type)
    return {"status": "QUEUED", "message": f"Proactive event '{payload.event_type}' queued for execution."}

@app.get("/api/proactive/logs")
async def list_proactive_logs():
    """Retrieve logs of autonomous background runs."""
    return proactive_monitor.get_proactive_logs()

@app.get("/api/security/logs")
async def list_security_logs():
    """Retrieve audit logs of Security Guard checks."""
    return orchestrator.security.get_logs()

@app.get("/api/status")
async def get_status():
    """Get system health and status."""
    return {
        "status": "HEALTHY",
        "proactive_loop_active": proactive_monitor.is_running,
        "chroma_active": orchestrator.memory.active,
        "database_path": orchestrator.db_path,
        "gemini_model": orchestrator.model_name,
        "gemini_api_key_configured": bool(orchestrator.api_key)
    }

if __name__ == "__main__":
    import uvicorn
    # Run the server locally
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
