# Hubscape ADK Studio

Welcome to the **Hubscape ADK Studio**! This is the official template and local development suite for building, testing, and previewing custom Hubscape Modular Agents.

By using this studio, you can write agents, define tool catalogs, create visual UI widgets, and test them locally in a high-fidelity sandbox—all without needing access to the core Hubscape platform code or a direct live database connection.

---

## 🚀 Quick Start

### 1. Prerequisites
Make sure you have **Python 3.10+** installed on your system.

### 2. Launch the Studio
We provide a cross-platform launcher script that automatically sets up a python virtual environment, installs the required dependencies, launches the sandbox server, and opens your browser:
```bash
python start_adk_studio.py
```
This will activate the environment and open your browser automatically to:
**[http://localhost:8090](http://localhost:8090)**


---

## 🛠️ Folder Structure

When building your agent, you only need to modify three files:

```text
├── config.json         # REQUIRED: Metadata, System Prompt, and Tool Schemas
├── logic.py            # REQUIRED: Python logic handlers for the tools
├── api.py              # OPTIONAL: Custom REST endpoints (Webhooks, etc.)
└── widgets/            # OPTIONAL: Predefined custom UI templates (JSON format)
```

1.  **`config.json`**: Declare your agent's identity, system instructions, and tool schemas.
2.  **`logic.py`**: Implement python handlers for each tool declared in `config.json`.
3.  **`api.py`**: Define custom FastAPI APIRouter endpoints for external webhooks or direct frontend queries.
4.  **`widgets/`**: Put any JSON templates for standard visual layouts (Lego UI blocks) in this directory.

---

## 🤖 AI Pair-Programming with Antigravity

This repository comes preloaded with the `.agent/skills/` directory containing Hubscape's domain-specific expertise.
If you use the **Antigravity** AI assistant in your editor:
*   Antigravity will automatically read these skills.
*   The assistant will understand how to help you define JSON widget templates, write secure database code via `HubscapeContext`, and debug tool schemas.

---

## 🧪 Local Testing Modes

The ADK Studio supports two modes of database execution:

### A. Local Offline Mode (Default)
By default, the sandbox uses a local file-based database (`local_db.json`) to emulate Firestore. This requires **zero setup**, runs offline, and is instantaneous.

### B. Dev DB Proxy Mode (Transceiver)
If you need to test against real schemas in the `hubscape-dev` database, you can run the sandbox in proxy mode:
```bash
export HUBSCAPE_DEV_GATEWAY=true
export HUBSCAPE_DEV_PAT="your_developer_personal_access_token"
python run_sandbox.py
```
All database queries will automatically route through the secure Hubscape API Dev Gateway, restricting your operations strictly to your assigned sandbox user, organization, and hub scopes.
