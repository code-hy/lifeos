import os
import sys
import logging
import inspect
import importlib
import pkgutil
from core.security import SecurityGuard

logger = logging.getLogger("LifeOS.MCPServer")

# Global registry for tools
registered_tools = {}

def mcp_tool(name=None):
    """
    Decorator to register a function as an MCP tool.
    Extracts description from docstring and parameter details from type hints.
    """
    def decorator(func):
        tool_name = name or func.__name__
        sig = inspect.signature(func)
        
        parameters = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            # Skip self, args, kwargs
            if param_name in ("self", "args", "kwargs"):
                continue
            
            # Map Python types to JSON schema types
            py_type = param.annotation
            json_type = "string"  # default fallback
            
            if py_type == int:
                json_type = "integer"
            elif py_type == float:
                json_type = "number"
            elif py_type == bool:
                json_type = "boolean"
            elif py_type == dict:
                json_type = "object"
            elif py_type == list:
                json_type = "array"
            
            param_desc = ""
            # Extract description from parameter default value if it's a string, or leave empty
            # Standard type annotations can be improved with annotated metadata, but this is simple and robust
            
            parameters[param_name] = {
                "type": json_type,
                "description": param_desc or f"Parameter {param_name}"
            }
            
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        registered_tools[tool_name] = {
            "func": func,
            "name": tool_name,
            "description": func.__doc__.strip() if func.__doc__ else f"Execute {tool_name}",
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required
            }
        }
        return func
    return decorator

class MCPServer:
    def __init__(self, security_guard: SecurityGuard = None):
        self.security = security_guard or SecurityGuard()
        self._discover_and_load_tools()

    def _discover_and_load_tools(self):
        """Dynamically import all tools in the mcp/tools folder."""
        try:
            # Ensure the lifeos directory is in sys.path
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if base_dir not in sys.path:
                sys.path.insert(0, base_dir)
            
            # Import tools package
            import mcp.tools
            
            # Walk and import each module under mcp.tools
            path = os.path.dirname(mcp.tools.__file__)
            for _, name, _ in pkgutil.iter_modules([path]):
                module_name = f"mcp.tools.{name}"
                logger.info(f"Loading tool module: {module_name}")
                importlib.import_module(module_name)
                
            logger.info(f"Loaded {len(registered_tools)} tools: {list(registered_tools.keys())}")
        except Exception as e:
            logger.error(f"Error discovering tools: {e}")

    def list_tools(self) -> list[dict]:
        """Return the schema of all registered tools."""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"]
            }
            for t in registered_tools.values()
        ]

    def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """
        Execute a tool by name with arguments.
        Includes a Security Interceptor to check against SecurityGuard validation.
        """
        if tool_name not in registered_tools:
            return {
                "status": "ERROR",
                "error": f"Tool '{tool_name}' not found."
            }

        # 1. Security Guard Interception Check
        guard_result = self.security.validate_action(tool_name, arguments)
        if guard_result.get("status") == "HOLD":
            logger.warning(f"Security Alert: Execution of '{tool_name}' put on HOLD.")
            return {
                "status": "HOLD",
                "approval_id": guard_result["approval_id"],
                "reason": guard_result["reason"]
            }

        # 2. Execution
        tool_entry = registered_tools[tool_name]
        try:
            # Extract expected parameters to avoid passing extra arguments
            func = tool_entry["func"]
            sig = inspect.signature(func)
            valid_args = {}
            for name, param in sig.parameters.items():
                if name in arguments:
                    valid_args[name] = arguments[name]
                elif param.default != inspect.Parameter.empty:
                    # Optional parameter, let python use default
                    pass
                elif param.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL):
                    # VAR keywords, can pass remaining
                    pass
            
            # Execute
            result = func(**valid_args)
            return {
                "status": "SUCCESS",
                "result": result
            }
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}")
            return {
                "status": "ERROR",
                "error": str(e)
            }
