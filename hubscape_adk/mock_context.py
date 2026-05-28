import os
import json
import logging
import datetime
from typing import Optional, Dict, List, Any
from fastapi import Request

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

class AuthContext:
    """Wrapper for user authentication details and permissions in the ADK context."""
    def __init__(self, user_id: str, name: Optional[str] = None, email: Optional[str] = None, phone_number: Optional[str] = None, hub_id: Optional[str] = None, org_id: Optional[str] = None, roles: Optional[list] = None, permissions: Optional[dict] = None, agent_id: Optional[str] = None):
        self.uid = user_id
        self.name = name or "Dev User"
        self.email = email or "dev@hubscape.com"
        self.phone_number = phone_number or "+15550199"
        self.hub_id = hub_id
        self.org_id = org_id
        self.roles = roles or ["member"]
        self.permissions = permissions or {}
        self.agent_id = agent_id or "unknown_agent"

    def get_user_id(self) -> str:
        return self.uid

    def has_permission(self, capability_id: str) -> bool:
        """
        Local permissions check.
        Superuser check for 'Hub Admin', otherwise matches roles declared in config.json.
        """
        if "Hub Admin" in self.roles:
            return True
            
        allowed_roles = self.permissions.get(capability_id, [])
        for role in self.roles:
            if role in allowed_roles:
                return True
        return False

    def is_hub_admin(self) -> bool:
        return "Hub Admin" in self.roles

class HubscapeContext:
    """
    Mock implementation of the core HubscapeContext.
    Persists data to a local 'local_db.json' file instead of Cloud Firestore.
    """
    def __init__(self, user_id: str, user_name: Optional[str] = None, user_email: Optional[str] = None, phone_number: Optional[str] = None, hub_id: Optional[str] = None, org_id: Optional[str] = None, user_roles: Optional[list] = None, agent_permissions: Optional[dict] = None, agent_id: Optional[str] = None):
        self.auth = AuthContext(
            user_id=user_id, 
            name=user_name, 
            email=user_email, 
            phone_number=phone_number,
            hub_id=hub_id, 
            org_id=org_id, 
            roles=user_roles, 
            permissions=agent_permissions, 
            agent_id=agent_id
        )
        self.user_preferences = {}
        self._widget_payload = None
        self.dev_gateway = os.getenv("HUBSCAPE_DEV_GATEWAY") == "true"
        self.dev_pat = os.getenv("HUBSCAPE_DEV_PAT")
        self.dev_gateway_url = os.getenv("HUBSCAPE_DEV_GATEWAY_URL", "https://hubscape-b9558.web.app")
        self.db_filepath = "local_db.json"
        self._init_local_db()

    def _proxy_request(self, endpoint: str, payload: dict) -> Any:
        import requests
        url = f"{self.dev_gateway_url.rstrip('/')}/api/dev-gateway/db/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.dev_pat}",
            "Content-Type": "application/json"
        }
        try:
            logger.info(f"📡 Transceiver: Proxying POST request to {url}...")
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None
            elif response.status_code == 401:
                logger.error("❌ Dev Gateway Authentication Failed: Invalid HUBSCAPE_DEV_PAT.")
                raise PermissionError("Unauthorized: Invalid Personal Access Token.")
            elif response.status_code == 403:
                logger.error(f"❌ Dev Gateway Authorization Failed: {response.text}")
                raise PermissionError(f"Forbidden: {response.text}")
            else:
                logger.error(f"❌ Dev Gateway Error {response.status_code}: {response.text}")
                raise RuntimeError(f"Server Error: {response.text}")
        except Exception as e:
            logger.error(f"❌ Dev Gateway Connection Failed: {e}")
            raise e

    def _init_local_db(self):
        """Initializes empty JSON DB structure if not present."""
        if not os.path.exists(self.db_filepath):
            with open(self.db_filepath, "w") as f:
                json.dump({"user": {}, "hub": {}, "org": {}, "tokens": {}, "preferences": {}}, f, indent=4)

    def _load_db(self) -> dict:
        try:
            with open(self.db_filepath, "r") as f:
                return json.load(f)
        except Exception:
            return {"user": {}, "hub": {}, "org": {}, "tokens": {}, "preferences": {}}

    def _write_db(self, db_data: dict):
        with open(self.db_filepath, "w") as f:
            json.dump(db_data, f, indent=4)

    def show_widget(self, widget_template_id: str, data: dict = None) -> dict:
        """Loads visual widget template from the local widgets folder."""
        try:
            filename = widget_template_id if widget_template_id.endswith(".json") else f"{widget_template_id}.json"
            template_path = os.path.join("widgets", filename)
            if not os.path.exists(template_path):
                return {"error": f"Widget template {filename} not found in widgets/ folder."}
            with open(template_path, "r") as f:
                widget_config = json.load(f)
            self._widget_payload = {
                "widgetId": widget_template_id,
                "widgetConfig": widget_config,
                "data": data or {}
            }
            return {"status": "success", "message": f"Widget '{widget_template_id}' loaded successfully."}
        except Exception as e:
            return {"error": f"Failed to load widget: {str(e)}"}

    def show_custom_ui(self, layout: dict, data: dict = None) -> dict:
        """Saves dynamic layout for the Holodeck client to fetch and render."""
        self._widget_payload = {
            "widgetId": "generative_custom_ui",
            "widgetConfig": layout,
            "data": data or {}
        }
        return {"status": "success", "message": "Custom UI loaded successfully."}

    def save_user_preferences(self, preferences: dict):
        db = self._load_db()
        user_id = self.auth.get_user_id()
        agent_id = self.auth.agent_id
        
        pref_key = f"{user_id}::{agent_id}"
        existing = db.setdefault("preferences", {}).setdefault(pref_key, {})
        existing.update(preferences)
        self._write_db(db)
        self.user_preferences = existing

    def get_agent_db_path(self, scope: str, collection_name: str, doc_id: Optional[str] = None) -> str:
        """Resolves target scope paths in local format."""
        user_id = self.auth.get_user_id()
        agent_id = self.auth.agent_id
        org_id = self.auth.org_id
        hub_id = self.auth.hub_id

        if scope == "user":
            base = f"user/{user_id}/agent_data/{agent_id}/{collection_name}"
        elif scope == "hub":
            base = f"hub/{org_id}/{hub_id}/agent_data/{agent_id}/{collection_name}"
        elif scope == "org":
            base = f"org/{org_id}/agent_data/{agent_id}/{collection_name}"
        else:
            raise ValueError(f"Invalid database scope: '{scope}'")
            
        if doc_id:
            return f"{base}/{doc_id}"
        return base

    def save_agent_data(self, scope: str, collection_name: str, doc_id: str, data: dict) -> dict:
        """Saves a document. Proxies to live database if Transceiver mode is active."""
        if self.dev_gateway and self.dev_pat:
            return self._proxy_request("save", {
                "scope": scope,
                "collection_name": collection_name,
                "doc_id": doc_id,
                "agent_id": self.auth.agent_id,
                "org_id": self.auth.org_id,
                "hub_id": self.auth.hub_id,
                "data": data
            })
            
        db = self._load_db()
        path = self.get_agent_db_path(scope, collection_name, doc_id)
        
        # Resolve target location in dictionary
        parts = path.split("/")
        curr = db
        for p in parts[:-1]:
            curr = curr.setdefault(p, {})
            
        doc_key = parts[-1]
        existing = curr.get(doc_key, {})
        
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        user_id = self.auth.get_user_id()

        merged_data = dict(data)
        if existing:
            merged_data["created_at"] = existing.get("created_at", now)
            merged_data["created_by"] = existing.get("created_by", user_id)
            merged_data["updated_at"] = now
            merged_data["updated_by"] = user_id
            merged_data["version"] = existing.get("version", 1) + 1
        else:
            merged_data["created_at"] = now
            merged_data["created_by"] = user_id
            merged_data["updated_at"] = now
            merged_data["updated_by"] = user_id
            merged_data["version"] = 1

        curr[doc_key] = merged_data
        self._write_db(db)
        return merged_data

    def get_agent_data(self, scope: str, collection_name: str, doc_id: str) -> Optional[dict]:
        """Gets a document. Proxies to live database if Transceiver mode is active."""
        if self.dev_gateway and self.dev_pat:
            return self._proxy_request("get", {
                "scope": scope,
                "collection_name": collection_name,
                "doc_id": doc_id,
                "agent_id": self.auth.agent_id,
                "org_id": self.auth.org_id,
                "hub_id": self.auth.hub_id
            })
            
        db = self._load_db()
        path = self.get_agent_db_path(scope, collection_name, doc_id)
        parts = path.split("/")
        
        curr = db
        for p in parts:
            if not isinstance(curr, dict) or p not in curr:
                return None
            curr = curr[p]
            
        if isinstance(curr, dict):
            curr_copy = dict(curr)
            curr_copy["id"] = doc_id
            return curr_copy
        return None

    def delete_agent_data(self, scope: str, collection_name: str, doc_id: str):
        """Deletes a document. Proxies to live database if Transceiver mode is active."""
        if self.dev_gateway and self.dev_pat:
            self._proxy_request("delete", {
                "scope": scope,
                "collection_name": collection_name,
                "doc_id": doc_id,
                "agent_id": self.auth.agent_id,
                "org_id": self.auth.org_id,
                "hub_id": self.auth.hub_id
            })
            return
            
        db = self._load_db()
        path = self.get_agent_db_path(scope, collection_name, doc_id)
        parts = path.split("/")
        
        curr = db
        for p in parts[:-1]:
            if not isinstance(curr, dict) or p not in curr:
                return
            curr = curr[p]
            
        doc_key = parts[-1]
        if isinstance(curr, dict) and doc_key in curr:
            del curr[doc_key]
            self._write_db(db)

    def list_agent_data(self, scope: str, collection_name: str) -> list[dict]:
        """Lists documents. Proxies to live database if Transceiver mode is active."""
        if self.dev_gateway and self.dev_pat:
            res = self._proxy_request("list", {
                "scope": scope,
                "collection_name": collection_name,
                "agent_id": self.auth.agent_id,
                "org_id": self.auth.org_id,
                "hub_id": self.auth.hub_id
            })
            return res or []
            
        db = self._load_db()
        path = self.get_agent_db_path(scope, collection_name)
        parts = path.split("/")
        
        curr = db
        for p in parts:
            if not isinstance(curr, dict) or p not in curr:
                return []
            curr = curr[p]
            
        if isinstance(curr, dict):
            results = []
            for k, v in curr.items():
                if isinstance(v, dict):
                    v_copy = dict(v)
                    v_copy["id"] = k
                    results.append(v_copy)
            return results
        return []

    def save_agent_token(self, token_name: str, data: dict) -> dict:
        """Saves integration token credentials. Proxies to live database if Transceiver mode is active."""
        if self.dev_gateway and self.dev_pat:
            return self._proxy_request("save-token", {
                "token_name": token_name,
                "agent_id": self.auth.agent_id,
                "data": data
            })
            
        db = self._load_db()
        user_id = self.auth.get_user_id()
        agent_id = self.auth.agent_id
        
        token_key = f"{user_id}::{agent_id}::{token_name}"
        existing = db.setdefault("tokens", {}).get(token_key, {})
        
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        merged_data = dict(data)
        
        if existing:
            merged_data["created_at"] = existing.get("created_at", now)
            merged_data["created_by"] = existing.get("created_by", user_id)
            merged_data["updated_at"] = now
            merged_data["updated_by"] = user_id
            merged_data["version"] = existing.get("version", 1) + 1
        else:
            merged_data["created_at"] = now
            merged_data["created_by"] = user_id
            merged_data["updated_at"] = now
            merged_data["updated_by"] = user_id
            merged_data["version"] = 1
            
        db["tokens"][token_key] = merged_data
        self._write_db(db)
        return merged_data

    def get_agent_token(self, token_name: str) -> Optional[dict]:
        """Gets integration token credentials. Proxies to live database if Transceiver mode is active."""
        if self.dev_gateway and self.dev_pat:
            return self._proxy_request("get-token", {
                "token_name": token_name,
                "agent_id": self.auth.agent_id
            })
            
        db = self._load_db()
        user_id = self.auth.get_user_id()
        agent_id = self.auth.agent_id
        token_key = f"{user_id}::{agent_id}::{token_name}"
        
        token = db.get("tokens", {}).get(token_key)
        if token:
            token_copy = dict(token)
            token_copy["id"] = token_name
            return token_copy
        return None


async def get_adk_context(request: Request) -> HubscapeContext:
    """FastAPI Dependency for local APIRouter testing."""
    app_state = getattr(request.app, "state", None)
    
    # Check if dev_gateway is True in settings
    dev_gateway_active = False
    if app_state and hasattr(app_state, "settings"):
        dev_gateway_active = app_state.settings.get("dev_gateway", False)
        
    user_source = "live_user" if dev_gateway_active else "mock_user"
    mock_user = getattr(app_state, user_source, {
        "user_id": "dev-user-123",
        "name": "Dev User",
        "email": "dev@hubscape.com",
        "phone_number": "+15550199",
        "roles": ["member", "Hub Admin"],
        "hub_id": "dev-hub-abc",
        "org_id": "dev-org-xyz"
    })
    
    # Load default permissions from config.json
    permissions = {}
    agent_id = "unknown_agent"
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                config_data = json.load(f)
                permissions = config_data.get("permissions", {})
                agent_id = config_data.get("id", "unknown_agent")
        except Exception:
            pass

    context = HubscapeContext(
        user_id=mock_user.get("user_id", "dev-user-123"),
        user_name=mock_user.get("name", "Dev User"),
        user_email=mock_user.get("email", "dev@hubscape.com"),
        phone_number=mock_user.get("phone_number", "+15550199"),
        user_roles=mock_user.get("roles", ["member"]),
        hub_id=mock_user.get("hub_id"),
        org_id=mock_user.get("org_id"),
        agent_permissions=permissions,
        agent_id=agent_id
    )

    # Apply dynamic settings overrides from application state on the fly
    if app_state and hasattr(app_state, "settings"):
        settings = app_state.settings
        context.dev_gateway = settings.get("dev_gateway", context.dev_gateway)
        if "dev_pat" in settings:
            context.dev_pat = settings["dev_pat"]
        if "dev_gateway_url" in settings:
            context.dev_gateway_url = settings["dev_gateway_url"]

    return context
