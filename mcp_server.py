#!/usr/bin/env python3
"""Small MCP stdio server for the open Visual Paradigm project, standard library only."""
import json
import sys
from transport import request

TEXT = {"type": "string", "minLength": 1}
INTEGER = {"type": "integer"}
BOUNDS = {"x": INTEGER, "y": INTEGER, "width": {"type": "integer", "minimum": 1}, "height": {"type": "integer", "minimum": 1}}
POINTS = {"type": "array", "maxItems": 100, "items": {"type": "array", "items": INTEGER, "minItems": 2, "maxItems": 2}}


def tool(name, description, fields=None, required=(), readonly=False, destructive=None):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": fields or {}, "required": list(required), "additionalProperties": False},
            "annotations": {"readOnlyHint": readonly, "destructiveHint": not readonly if destructive is None else destructive,
                            "idempotentHint": readonly, "openWorldHint": False}}


TOOLS = [
    tool("get_project", "Read the currently open project's file, modified flag, and active diagram. No file path is hardcoded.", readonly=True),
    tool("list_diagrams", "List all native diagrams in the open project with their IDs and types.", readonly=True),
    tool("get_diagram", "Read a diagram's elements, model IDs, text, bounds, and connector endpoints.",
         {"diagram_id": TEXT}, ["diagram_id"], True),
    tool("get_connector", "Read a connector's actual waypoints, shape endpoint IDs, bounds, and caption visibility/bounds. Rejects non-connectors.",
         {"diagram_id": TEXT, "element_id": TEXT}, ["diagram_id", "element_id"], True),
    tool("create_diagram", "Create a native diagram. Examples of diagram_type: UseCaseDiagram, ActivityDiagram, ClassDiagram. Does not save automatically.",
         {"name": TEXT, "diagram_type": TEXT}, ["name", "diagram_type"]),
    tool("create_element", "Create a native node. model_type examples: Actor, UseCase, System, ActivityAction, DecisionNode, InitialNode, ActivityFinalNode, ObjectNode. parent_id optionally nests the shape. Bounds use VP diagram coordinates. Does not save.",
         {"diagram_id": TEXT, "model_type": TEXT, "name": {"type": "string"}, **BOUNDS, "parent_id": TEXT},
         ["diagram_id", "model_type", "name", *BOUNDS]),
    tool("rename_element", "Rename the underlying model. Shared views of that model in other diagrams also change. Does not save.",
         {"diagram_id": TEXT, "element_id": TEXT, "name": TEXT}, ["diagram_id", "element_id", "name"]),
    tool("set_bounds", "Move or resize one shape view. Bounds use VP diagram coordinates; other views of the same model are unaffected. Does not save.",
         {"diagram_id": TEXT, "element_id": TEXT, **BOUNDS}, ["diagram_id", "element_id", *BOUNDS]),
    tool("set_connector_points", "Replace a connector's waypoints with the supplied [x,y] points and reset its caption layout. Does not change the relationship model or its endpoints. Does not save; read get_connector afterwards to verify actual geometry.",
         {"diagram_id": TEXT, "element_id": TEXT, "points": {**POINTS, "minItems": 2}},
         ["diagram_id", "element_id", "points"]),
    tool("set_connector_style", "Set a connector view's native routing style. Rectilinear uses right-angle bends. Does not change endpoints, guards or the relationship model; does not save. Read actual points and inspect an export afterwards.",
         {"diagram_id": TEXT, "element_id": TEXT, "style": {"type": "string", "enum": ["rectilinear", "oblique"]}},
         ["diagram_id", "element_id", "style"]),
    tool("set_connector_caption", "Set a connector caption's position and size, and make it visible. Rejects non-connectors and missing captions. Does not reset caption layout, change waypoints, endpoints, or the model. Does not save.",
         {"diagram_id": TEXT, "element_id": TEXT, **BOUNDS}, ["diagram_id", "element_id", *BOUNDS]),
    tool("connect_elements", "Create a native relationship between two shape IDs in one diagram. model_type examples: Association, Include, Extend, ControlFlow, ActivityObjectFlow. Condition is supported for Extend and activity flows. Optional points are [x,y] waypoints. Does not save.",
         {"diagram_id": TEXT, "model_type": TEXT, "from_id": TEXT, "to_id": TEXT,
          "name": {"type": "string"}, "condition": {"type": "string"}, "points": POINTS},
         ["diagram_id", "model_type", "from_id", "to_id"]),
    tool("delete_relationship", "Delete a relationship model and its sole connector view. Rejects nodes, connectors without a relationship, and relationships with any other view in the project. Does not save; create a backup first.",
         {"diagram_id": TEXT, "element_id": TEXT}, ["diagram_id", "element_id"]),
    tool("delete_disconnected_node", "Delete a disconnected leaf node and its sole view. Rejects shared nodes, children, subdiagrams and any relationships. Disconnect explicitly first; back up before deletion. Does not save.",
         {"diagram_id": TEXT, "element_id": TEXT}, ["diagram_id", "element_id"]),
    tool("set_flow_guard", "Set the native guard of a ControlFlow or ActivityObjectFlow and clear its old display name to avoid duplicate conditions. Shared views change. Does not save.",
         {"diagram_id": TEXT, "element_id": TEXT, "guard": TEXT}, ["diagram_id", "element_id", "guard"]),
    tool("set_object_type", "Set an ObjectNode's textual type (replacing its type reference if any). Does not rename or delete the old classifier. Shared views change; does not save.",
         {"diagram_id": TEXT, "element_id": TEXT, "type_name": TEXT}, ["diagram_id", "element_id", "type_name"]),
    tool("export_diagram", "Export a diagram PNG to the bridge exports directory. Refuses to overwrite an existing file.",
         {"diagram_id": TEXT, "filename": TEXT}, ["diagram_id", "filename"]),
    tool("save_project", "Save the current project, including all its pending user and agent changes."),
    tool("backup_project", "Save the current project through OpenAPI, including pending changes, then create a uniquely named .vpp copy in the bridge backups directory. Never overwrites an existing backup; returns its path.", destructive=False),
]
BY_NAME = {t["name"]: t for t in TOOLS}


def validate(value, schema, path="arguments"):
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} must be one of {schema['enum']}")
    kind = schema["type"]
    if kind == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{path} must be an object")
        missing = set(schema["required"]) - value.keys()
        unknown = value.keys() - schema["properties"].keys()
        if missing or unknown:
            raise ValueError(f"{path}: missing {sorted(missing)}, unknown {sorted(unknown)}")
        for key, item in value.items():
            validate(item, schema["properties"][key], f"{path}.{key}")
    elif kind == "string":
        if not isinstance(value, str) or len(value) < schema.get("minLength", 0):
            raise ValueError(f"{path} must be a string of length >= {schema.get('minLength', 0)}")
    elif kind == "integer":
        if type(value) is not int or not -(2**31) <= value < 2**31 or value < schema.get("minimum", -(2**31)):
            raise ValueError(f"{path} must be an integer within the allowed bounds")
    elif kind == "array":
        if not isinstance(value, list) or not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 10000):
            raise ValueError(f"{path} has an invalid array length")
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{i}]")


def call_tool(name, arguments):
    if name not in BY_NAME:
        raise ValueError(f"Unknown tool: {name}")
    validate(arguments, BY_NAME[name]["inputSchema"])
    if name in {"get_project", "list_diagrams", "get_diagram"}:
        project = request()
        if project is None:
            raise RuntimeError("No project open")
        if name == "get_project":
            return {k: v for k, v in project.items() if k != "diagrams"}
        if name == "list_diagrams":
            return [{k: v for k, v in d.items() if k != "elements"} for d in project["diagrams"]]
        for diagram in project["diagrams"]:
            if diagram["id"] == arguments["diagram_id"]:
                return diagram
        raise ValueError("Diagram not found")
    parameters = {"operation": name, **arguments}
    if "points" in parameters:
        parameters["points"] = ";".join(f"{x},{y}" for x, y in parameters["points"])
    result = json.loads(request("run", "Command", parameters))
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def handle(message):
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
    if "id" not in message:
        return None
    response = {"jsonrpc": "2.0", "id": message["id"]}
    method, params = message["method"], message.get("params", {})
    if not isinstance(params, dict):
        response["error"] = {"code": -32602, "message": "params must be an object"}
        return response
    if method == "initialize":
        versions = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
        version = params.get("protocolVersion")
        response["result"] = {"protocolVersion": version if version in versions else "2025-03-26",
                              "capabilities": {"tools": {"listChanged": False}},
                              "serverInfo": {"name": "visual-paradigm-local", "version": "1.0.0"},
                              "instructions": "Use IDs returned by read tools. Changes stay in the open project until save_project. Never replay a timed-out write; inspect its outcome. rename_element affects all views of its model."}
    elif method == "ping":
        response["result"] = {}
    elif method == "tools/list":
        response["result"] = {"tools": TOOLS}
    elif method == "tools/call":
        try:
            result = call_tool(params.get("name"), params.get("arguments", {}))
            response["result"] = {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "isError": False}
        except Exception as error:
            response["result"] = {"content": [{"type": "text", "text": str(error)}], "isError": True}
    else:
        response["error"] = {"code": -32601, "message": f"Method not found: {method}"}
    return response


def main():
    # MCP stdio is newline-delimited JSON-RPC; stdout contains only protocol messages.
    for line in sys.stdin.buffer:
        try:
            if len(line) > 1024 * 1024:
                raise ValueError("Message too large")
            response = handle(json.loads(line))
        except (ValueError, UnicodeError) as error:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(error)}}
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
