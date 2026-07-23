"""Unified Tool Registry - Wraps all agent capabilities as discoverable tools.

Merged from NEO-AGENT's ToolRegistry pattern with the Desktop Agent's ActionRegistry.
Allows LLMs to discover and call tools by name with typed parameters.
"""
import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ToolSpec:
    """Specification for a callable tool."""
    name: str
    description: str
    handler: Callable
    parameters: dict = field(default_factory=dict)
    category: str = "general"
    returns: str = "any"


class ToolRegistry:
    """Registry of all tools the agent can use, with schema introspection."""

    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        description: str,
        handler: Callable,
        category: str = "general",
        returns: str = "any",
        params: list = None,
        icon: str = None,
    ):
        """Register a tool with automatic parameter detection.

        Args:
            name: Tool name
            description: Tool description
            handler: Callable function
            category: Tool category
            returns: Return type description
            params: Optional list of param dicts with {name, type, required, description}
            icon: Optional icon emoji
        """
        sig = inspect.signature(handler)
        detected_params = {}
        for pname, param in sig.parameters.items():
            if pname in ("self", "cls"):
                continue
            ptype = "string"
            if param.annotation != inspect.Parameter.empty:
                ptype = {
                    str: "string",
                    int: "integer",
                    float: "number",
                    bool: "boolean",
                    list: "array",
                    dict: "object",
                }.get(param.annotation, "string")

            default = None
            if param.default != inspect.Parameter.empty:
                default = param.default

            detected_params[pname] = {
                "type": ptype,
                "required": param.default == inspect.Parameter.empty,
                "default": default,
                "description": "",
            }

        # Merge custom param descriptions if provided
        if params:
            for p in params:
                pname = p.get("name")
                if pname and pname in detected_params:
                    if p.get("description"):
                        detected_params[pname]["description"] = p["description"]
                    if p.get("type"):
                        detected_params[pname]["type"] = p["type"]
                    if "required" in p:
                        detected_params[pname]["required"] = p["required"]

        self._tools[name] = ToolSpec(
            name=name,
            description=description,
            handler=handler,
            parameters=detected_params,
            category=category,
            returns=returns,
        )

    def register_simple(self, fn: Callable, name: Optional[str] = None,
                        category: str = "general"):
        """Register a tool using function docstring and name."""
        fn_name = name or fn.__name__
        description = (fn.__doc__ or "").strip().split("\n")[0] if fn.__doc__ else fn_name
        self.register(fn_name, description, fn, category=category)

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def call(self, name: str, **kwargs) -> Any:
        """Call a tool by name with parameters."""
        tool = self.get(name)
        if not tool:
            return {"error": f"Unknown tool: {name}"}

        try:
            result = tool.handler(**kwargs)
            return {"success": True, "result": result}
        except Exception as e:
            import traceback
            return {"error": str(e), "traceback": traceback.format_exc()}

    def list_tools(self, category: Optional[str] = None) -> list[dict]:
        """List all tools with their schemas."""
        tools = []
        for name, spec in sorted(self._tools.items()):
            if category and spec.category != category:
                continue
            tools.append({
                "name": name,
                "description": spec.description,
                "parameters": spec.parameters,
                "category": spec.category,
                "returns": spec.returns,
            })
        return tools

    def ollama_tools_format(self) -> list[dict]:
        """Return tools in Ollama function-calling format."""
        tools = []
        for name, spec in self._tools.items():
            properties = {}
            required = []
            for pname, pinfo in spec.parameters.items():
                properties[pname] = {
                    "type": pinfo["type"],
                    "description": pinfo.get("description", f"Parameter {pname}"),
                }
                if pinfo["required"]:
                    required.append(pname)

            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": spec.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required if required else None,
                    },
                },
            })
        return tools

    def __len__(self):
        return len(self._tools)

    def __contains__(self, name):
        return name in self._tools


# Global singleton
registry = ToolRegistry()
