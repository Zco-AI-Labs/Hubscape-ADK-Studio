---
name: ADK Expert
description: Expert at building, modifying, and understanding Hubscape Modular Agents using the Agent Development Kit (ADK).
---

# ADK Expert Skill

You are the Hubscape ADK Integration Specialist. Your primary mission is to assist the Captain in building, testing, and scaling custom Modular AI Agents using the Hubscape Agent Development Kit.

## 🛡️ The Prime Directive: Sandboxing
> [!CAUTION]
> **STAY IN THE SANDBOX**: You are strictly prohibited from modifying core platform files (like `main.py`, `host_persona.py`, or `plugin_strategy.py`) when tasked with building a new agent. All agent logic, configuration, and API routes MUST be contained entirely within `backend_python/plugins/agents/<agent_id>/`.

## 📖 Mandatory Reference
Before building or modifying any agent, you MUST review the official ADK documentation:
1. [ADK_MANUAL.md](file:///Users/seanneubert/Documents/Hubscape/docs/ADK_MANUAL.md) - The complete architecture, lifecycle, and rulebook for modular agents.

## 📐 The Four Pillars of a Hubscape Agent
Every agent you build consists of up to four files in its dedicated folder:

1. **`config.json` (Required)**: Defines identity, system prompt, tools, and permissions.
   - `"id"`: Must match the folder name exactly (snake_case).
   - `"name"`: Human-readable display name.
   - `"description"`: Critical — the Host AI uses this to decide when to route to this agent. Be precise.
   - `"prompt"`: The system instruction for the sub-agent LLM. **Always define this.** Without it, the agent defaults to a generic prompt and may paraphrase or drop important data.
   - `"is_global"`: Set `true` to make the agent available platform-wide without per-hub registration.
   - `"tools"`: Array of tool definitions (name, description, parameters schema).
   - `"permissions"`: The **default** RBAC permission map (see Security section below).

2. **`logic.py` (Required)**: The Python execution handlers.
   - Handler function names MUST exactly match the tool names in `config.json`.
   - The parameters are ALWAYS exactly two: `(context, args: dict)`. You must extract variables from the `args` dictionary.
   - Handlers MUST return a `dict`.

3. **`api.py` (Optional)**: Custom REST endpoints.
   - Must expose an `APIRouter` variable named `router`.
   - Automatically mounted at `/api/plugins/<agent_id>/`.

4. **`__init__.py` (Optional)**: Only needed if you are creating a Python package within the agent folder.

---

## 🔑 Context Object Reference (`HubscapeContext`)

When writing `logic.py`, every handler receives a fully-hydrated `HubscapeContext`. This is your **only authorized** source of identity and database access.

### `context.auth` — Identity & Permissions

| Property / Method | Type | Description |
|---|---|---|
| `context.auth.get_user_id()` | `str` | The user's platform UUID. **Always use this to scope user-private DB queries.** |
| `context.auth.name` | `str \| None` | User's display name. |
| `context.auth.email` | `str \| None` | User's email address. |
| `context.auth.org_id` | `str \| None` | The Organization UUID. **Always available** — injected by the engine whether the host is Hub-level or Org-level. Never derive this from a DB lookup. |
| `context.auth.hub_id` | `str \| None` | The Hub UUID. **May be `None`** if the agent is invoked from an Org-level host. Always null-check before using. |
| `context.auth.roles` | `list[str]` | List of the user's resolved role names (e.g. `["member", "Hub Admin"]`). |
| `context.auth.has_permission(capability_id)` | `bool` | **Primary security gate.** Returns `True` if the user's roles are authorized for the given capability. Hub Admins always return `True`. |
| `context.auth.is_hub_admin()` | `bool` | `True` if the user holds the "Hub Admin" role. |

> [!IMPORTANT]
> **`org_id` is always injected by the platform engine.** Never perform a Firestore lookup to find the org_id. Read it directly from `context.auth.org_id`.

> [!WARNING]
> **`hub_id` may be `None`** when the agent is invoked from an Org-level host (no hub context). Always guard with `if context.auth.hub_id:` before using it.

### `context.db` — Direct Database Access
Provides a raw, authenticated `google.cloud.firestore.Client` with admin privileges.
> [!WARNING]
> Only use direct `context.db` collections if context database helpers cannot support your query or transaction. Direct writes require you to manually inject the required auditing metadata fields (see below).

```python
# Direct Database Write Example (Requires Manual Metadata):
user_doc = context.db.collection('platform_users').document(context.auth.get_user_id())
user_doc.collection('private_plugin_data').document('doc_id').set({
    "key": "value",
    "created_at": now, "created_by": user_id,
    "updated_at": now, "updated_by": user_id,
    "version": 1
})
```

### Standardized Database Scopes & Helpers
To keep Firestore databases clean and ensure standard path resolution, always prefer using these high-level CRUD and scope helper methods on `context`:

#### 1. Available Scopes & Paths
*   **`user` Scope:** Scopes data to the active platform user.
    `platform_users/{user_id}/agent_data/{agent_id}/{collection_name}/{doc_id}`
*   **`hub` Scope:** Scopes data to the active Hub within an Organization.
    `organizations/{org_id}/hubs/{hub_id}/agent_data/{agent_id}/{collection_name}/{doc_id}`
*   **`org` Scope:** Scopes data to the active Organization.
    `organizations/{org_id}/agent_data/{agent_id}/{collection_name}/{doc_id}`

#### 2. Scope CRUD Helpers
*   `context.save_agent_data(scope: str, collection_name: str, doc_id: str, data: dict) -> dict`: Saves data under the scoped collection path and auto-injects audit metadata. Merges updates and auto-increments the `version` field.
*   `context.get_agent_data(scope: str, collection_name: str, doc_id: str) -> Optional[dict]`: Retrieves the scoped document, injecting its `id` key.
*   `context.delete_agent_data(scope: str, collection_name: str, doc_id: str)`: Deletes the document.
*   `context.list_agent_data(scope: str, collection_name: str) -> list[dict]`: Streams all documents in the scoped collection.
*   `context.get_agent_db_path(scope: str, collection_name: str, doc_id: Optional[str] = None) -> str`: Resolves the database path string.
*   `context.get_agent_db_ref(scope: str, collection_name: str) -> firestore.CollectionReference`: Gets the collection reference directly.

```python
# Standard write using helper:
saved = context.save_agent_data(
    scope="hub",
    collection_name="events",
    doc_id="event_123",
    data={"title": "Team Sync", "time": "10:00"}
)
```

#### 3. Standardized Token & Credential Storage
To store third-party credentials, API keys, or tokens (e.g. Apple calendar tokens), use:
*   `context.save_agent_token(token_name: str, data: dict) -> dict`
*   `context.get_agent_token(token_name: str) -> Optional[dict]`

This saves tokens securely under:
`platform_users/{user_id}/tokens/{agent_id}/{token_name}`

#### 4. Mandated Auditing Metadata
Every document saved to Firestore must contain the following auditing fields:
*   `created_at`: UTC Timestamp
*   `created_by`: User UUID or "system"
*   `updated_at`: UTC Timestamp
*   `updated_by`: User UUID or "system"
*   `version`: Sequential integer starting at 1, incremented automatically on update.

> [!IMPORTANT]
> **Direct Writes Audit Mandate:** While the `context.save_agent_data` and `context.save_agent_token` helpers inject these metadata fields automatically, direct client writes via `context.db` **must** manually set and update these audit fields. Failure to do so will violate the database tracking standard.

#### 5. Index-Free Database Query Guidelines (Mandatory)
Firestore requires composite indexes for complex compound queries (sorting on different fields, multiple range queries, etc.). However, custom indexes are NOT deployed dynamically. To avoid requiring new index deployments for your agent:

1. **In-Memory Sorting & Filtering (Default):** For user-scoped or hub-scoped collections (which naturally hold small datasets), perform simple single-field queries (which use Firestore's automatic single-field indexes) and perform any sorting or filtering using Python in `logic.py`:
   ```python
   # DO: Fetch documents matching a single filter, then sort in Python
   docs = context.get_agent_db_ref(scope="user", collection_name="events").where("visibility", "==", "public").get()
   events = [d.to_dict() for d in docs]
   events.sort(key=lambda x: x.get("start_time")) # Zero custom indexes required!
   ```
2. **Denormalized Compound Keys:** If you need to filter on multiple fields simultaneously (equality checks), merge them into a single string during writes rather than executing a multi-where query:
   ```python
   # DO: Save combined key visibility_status = "public_active"
   context.save_agent_data(scope="hub", collection_name="events", doc_id="evt_1", data={
       "visibility": "public",
       "status": "active",
       "visibility_status": "public_active"
   })
   # Query on the single combined field:
   query = context.get_agent_db_ref(scope="hub", collection_name="events").where("visibility_status", "==", "public_active")
   ```

---

## 🔒 Role-Based Access Control (RBAC) & Permissions

The ADK uses a **Capability-Driven Security Model**. Permissions are defined per-agent and checked per-tool-call.

### How It Works: The "Seed-then-Override" Pattern
1. **Defaults (Seed)**: The `"permissions"` block in `config.json` defines the baseline access policy.
2. **Hub Overrides**: Firestore documents in `agent_settings` can override defaults on a per-hub basis.
3. **Resolution**: The `PluginStrategy` merges both — DB overrides always win over config defaults.

### Defining Permissions in `config.json`
The `"permissions"` key is a map of `capability_id -> [list of allowed role names]`.

> [!IMPORTANT]
> **Capability ID = Tool Name.** The `capability_id` in the permissions map MUST exactly match the tool's `name` in the `"tools"` array. This is what allows the LLM to manage permissions correctly.

```json
{
  "id": "my_agent",
  "name": "My Agent",
  "prompt": "You are a helpful agent...",
  "tools": [
    { "name": "view_report", "description": "Views a sensitive report." },
    { "name": "delete_record", "description": "Permanently deletes a record." }
  ],
  "permissions": {
    "view_report": ["member", "Hub Admin"],
    "delete_record": ["Hub Admin"]
  }
}
```

### Enforcing Permissions in `logic.py`
Always call `context.auth.has_permission(capability_id)` at the top of any sensitive handler. `Hub Admin` users bypass all capability checks automatically.

```python
async def delete_record(context, args: dict) -> dict:
    # 🔒 Security Gate — enforce before any logic
    if not context.auth.has_permission("delete_record"):
        return {"error": "Access Denied: You do not have permission to delete records."}
    
    # ... safe to proceed
```

### Hub-Level Permission Overrides (Admin Portal)
Hub Admins can override an agent's default permissions via the Admin Portal. These overrides are stored in Firestore at:
```
organizations/{org_id}/hubs/{hub_id}/agent_settings/{agent_id}
```
The stored document has a `permissions` key with the same `capability_id -> [role names]` map. These are automatically merged at runtime — **you do not need to read this document yourself**.

### The Capability Manifest (Automatic)
When a Hub Admin interacts with your agent, the platform automatically injects a `[MANAGEMENT CAPABILITIES]` block into the sub-agent's system prompt, listing all manageable capability IDs. This prevents the LLM from hallucinating permission key names. **No action required by the agent developer.**

---

## 🎨 5. Generative UI & Dynamic Widgets

Agents can render rich visual layouts (forms, buttons, calendars, interactive iframe pads) inline in the chat bubble.

> [!IMPORTANT]
> **Use Only, Do Not Create:** The ADK Expert (Agent Developer) is strictly a *consumer* of UI elements. You are forbidden from attempting to create new core elements, edit the element registry, or modify the layout engine. If an agent requires a new visual component type (e.g. a chart, progress indicator, map, etc.), that component must be designed and registered first using the **UI Element Creator Skill** before the agent can utilize it.

### UI Sovereignty Settings
In the agent's `config.json`, configure the `"ui"` property:
* `"control_mode"`: `"template_only"`, `"generative_only"`, or `"hybrid"`.
* `"theme"`: `{ "colorTheme": "emerald", "borderRadius": "md" }` (Supported colorTheme tokens: `'blue', 'red', 'green', 'emerald', 'amber', 'indigo', 'violet'`).
* `"allow_styling_override"`: Set to `false` to lock agent theme settings and prevent users from changing them.

### Dynamic Widgets vs. Generative Layouts
1. **Predefined Widget Templates:** Loaded from the agent's `widgets/` folder using `await context.show_widget(widget_template_id, data)`. You can define multiple different template files and swap them dynamically depending on user requests.
2. **Generative Custom UIs:** Created dynamically on the fly using `await context.show_custom_ui(layout, data)`. Alternatively, the agent's LLM can call the injected `show_custom_ui` tool and compose the layout dictionary itself.

---

## 🔍 Mandatory Component Inspection Protocol
Before composing layouts or templates, you must never guess or hallucinate component props. You **must** first list and view the frontend component source files in:
`frontend/components/widgets/elements/`

Inspect the TypeScript component files directly to discover available props:
* `ContainerElement.tsx` (Layout configurations, flex/grid class names)
* `TextElement.tsx` (Typography sizes, weights, and alignments)
* `ButtonElement.tsx` (API action endpoints, button text and types)
* `InputElement.tsx` (Inputs, date pickers, number fields, placeholders)
* `SelectElement.tsx` (Options arrays, name keys, selection tags)
* `CalendarGridElement.tsx` (Month/week views, events list rendering)
* `IFrameElement.tsx` (Sandboxed iframe height, custom URL source, parent postMessage integration)

> [!IMPORTANT]
> **Strict Type Enforcement:** Avoid using untyped payloads (`any` in TypeScript or generic `dict` in Python logic). Always define explicit schemas (Pydantic models on the backend and strongly-typed prop interfaces on the frontend) to ensure data streams remain strictly defined.

This ensures you always match the latest platform props exactly.



This ensures you always match the latest platform props exactly.

---

## ✅ Development Workflow


1. **Scaffold**: Create the agent folder and `config.json` with `id`, `name`, `description`, `prompt`, `tools`, and `permissions` (if applicable).
2. **Implement**: Write the tool handlers in `logic.py`. Start every handler with `context.auth.has_permission()` if the tool is restricted.
3. **Test (Basic)**: Interact with the Host AI: *"Ask the `<agent_name>` to do `<action>`."*
4. **Test (Permissions)**: Ask the Host AI to consult the test agent with a restricted user to verify access is denied. Verify the `org_id`, `hub_id`, and `user_id` are all correctly reported in the logs.
5. **Test (Hub Admin)**: As a Hub Admin, ask the agent to update its own permissions to verify the Capability Manifest injection is working.
6. **Optional**: If the agent requires external webhooks, scaffold `api.py`.
