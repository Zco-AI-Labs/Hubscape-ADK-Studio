from fastapi import APIRouter, Depends
from pydantic import BaseModel

# Dual-Mode Import: Resolves correctly both in Hubscape production and local ADK Studio
try:
    from services.host_core.adk_context import get_adk_context, HubscapeContext
except ImportError:
    from hubscape_adk.mock_context import get_adk_context, HubscapeContext

router = APIRouter()

class CompleteRequest(BaseModel):
    task_id: str

@router.post("/complete")
async def handle_complete_button(
    req: CompleteRequest, 
    context: HubscapeContext = Depends(get_adk_context)
):
    """
    POST /api/plugins/todo_agent/complete
    Triggered when a user clicks the 'Done' button in the Lego UI widget.
    """
    from logic import complete_task
    
    # Run the logic tool handler
    result = await complete_task(context, {"task_id": req.task_id})
    
    # Return response along with the newly updated widget payload so the UI redraws
    return {
        "status": "success",
        "result": result,
        "widgetPayload": context._widget_payload
    }
