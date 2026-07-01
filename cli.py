import os
import asyncio
import json
import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Initialize Typer and Console
app = typer.Typer(help="LifeOS Executive CLI - Control your agentic workflow")
console = Console()

# We import orchestrator lazily when command executes to speed up CLI boot
_orchestrator = None

def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        from core.orchestrator import ExecutiveOrchestrator
        _orchestrator = ExecutiveOrchestrator()
    return _orchestrator

# Helper to run async functions
def run_async(coro):
    return asyncio.run(coro)

@app.command()
def ask(query: str = typer.Argument(..., help="The query/instruction for LifeOS")):
    """
    Send an instruction or question to the Executive Orchestrator.
    """
    orch = get_orchestrator()
    
    with console.status("[bold cyan]Executive Orchestrator is thinking..."):
        result = run_async(orch.handle_request(query))
        
    status = result.get("status")
    
    if status == "BLOCKED":
        rprint(f"[bold red]❌ Request Blocked by Security Guard[/]")
        rprint(f"[red]{result.get('response')}[/]")
    
    elif status == "HOLD":
        rprint(f"[bold yellow]⚠️ Security Hold Alert[/]")
        rprint(f"[yellow]{result.get('response')}[/]")
        rprint(f"\n[bold]Tool to execute:[/ bold] {result.get('tool_name')}")
        rprint(f"[bold]Parameters:[/ bold]")
        rprint(json.dumps(result.get("args"), indent=2))
        rprint(f"\n[green]To approve, run:[/] python cli.py approve {result.get('approval_id')}")
        rprint(f"[red]To reject, run:[/] python cli.py reject {result.get('approval_id')}")
        
    elif status == "SUCCESS":
        rprint(f"[bold green]✔ Plan Completed successfully[/]")
        rprint("\n" + result.get("response"))
        
        # Show step list
        table = Table(title="Execution Step Log", show_header=True, header_style="bold magenta")
        table.add_column("Step", style="dim")
        table.add_column("Status")
        table.add_column("Details")
        
        for step_key, step_res in result.get("results", {}).items():
            s_status = step_res.get("status")
            s_color = "green" if s_status == "SUCCESS" else "red"
            res_val = step_res.get("result") or step_res.get("error")
            table.add_row(
                step_key, 
                f"[{s_color}]{s_status}[/]", 
                str(res_val)[:80] + "..." if len(str(res_val)) > 80 else str(res_val)
            )
        console.print(table)

@app.command()
def approvals():
    """
    List all pending security approvals.
    """
    orch = get_orchestrator()
    pending = orch.security.get_pending_approvals()
    
    if not pending:
        rprint("[bold green]No pending approvals found. Everything is secure.[/]")
        return
        
    table = Table(title="Pending Security Approvals", show_header=True, header_style="bold yellow")
    table.add_column("Approval ID", style="dim", width=36)
    table.add_column("Tool Name", style="bold cyan")
    table.add_column("Parameters", style="white")
    table.add_column("Requested At", style="dim")
    
    for appr in pending:
        table.add_row(
            appr["id"],
            appr["tool_name"],
            json.dumps(appr["parameters"]),
            appr["created_at"]
        )
        
    console.print(table)

@app.command()
def approve(approval_id: str = typer.Argument(..., help="The UUID of the pending approval request")):
    """
    Approve a pending tool call and resume plan execution.
    """
    orch = get_orchestrator()
    
    # 1. Update status
    success = orch.security.decide_action(approval_id, approve=True)
    if not success:
        rprint(f"[bold red]Error:[/] Approval ID '{approval_id}' not found or already decided.")
        return
        
    rprint(f"[bold green]✔ Tool call approved. Resuming plan execution...[/]")
    
    with console.status("[bold cyan]Resuming execution..."):
        result = run_async(orch.resume_execution(approval_id))
        
    if result.get("status") == "SUCCESS":
        rprint(f"[bold green]✔ Resumed Plan Completed successfully[/]")
        rprint("\n" + result.get("response"))
    else:
        rprint(f"[bold red]❌ Execution failed on resumption[/]")
        rprint(result.get("error"))

@app.command()
def reject(approval_id: str = typer.Argument(..., help="The UUID of the pending approval request")):
    """
    Reject a pending tool call, aborting the plan execution.
    """
    orch = get_orchestrator()
    success = orch.security.decide_action(approval_id, approve=False)
    if not success:
        rprint(f"[bold red]Error:[/] Approval ID '{approval_id}' not found or already decided.")
        return
        
    rprint(f"[bold red]❌ Action '{approval_id}' rejected. Paused execution flow has been aborted.[/]")

@app.command()
def memory_list():
    """
    List all stored user preferences in ChromaDB.
    """
    orch = get_orchestrator()
    prefs = orch.memory.get_all_preferences()
    
    if not prefs:
        rprint("[bold yellow]No preferences stored in memory yet.[/]")
        return
        
    table = Table(title="Long-Term Memory Bank (User Preferences)", show_header=True, header_style="bold green")
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", style="white")
    
    for p in prefs:
        table.add_row(p.get("key", "N/A"), p.get("value", "N/A"))
        
    console.print(table)

@app.command()
def memory_add(
    key: str = typer.Argument(..., help="The preference key (e.g. favorite_airline)"),
    value: str = typer.Argument(..., help="The preference value (e.g. United Airlines)")
):
    """
    Manually add a user preference to ChromaDB memory.
    """
    orch = get_orchestrator()
    orch.memory.add_preference(key, value)
    rprint(f"[bold green]✔ Preference '{key}' stored in ChromaDB memory.[/]")

@app.command()
def trigger_proactive(event_type: str = typer.Argument(..., help="Event type: flight_delay, bill_spike, workout_reminder")):
    """
    Trigger a proactive monitor event via FastAPI server.
    """
    import httpx
    url = "http://localhost:8000/api/proactive/trigger"
    try:
        response = httpx.post(url, json={"event_type": event_type})
        if response.status_code == 200:
            rprint(f"[bold green]✔ Proactive event '{event_type}' successfully triggered on running server.[/]")
        else:
            rprint(f"[bold red]Failed to trigger event via server (Status Code {response.status_code}): {response.text}[/]")
    except httpx.RequestError:
        rprint("[bold red]Error: Could not connect to running FastAPI server on http://localhost:8000[/]")
        rprint("[yellow]The proactive background loop only runs inside the web server. Please start the server using 'python main.py' first.[/]")

if __name__ == "__main__":
    app()
