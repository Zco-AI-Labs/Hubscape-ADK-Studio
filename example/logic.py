import logging
import uuid

logger = logging.getLogger(__name__)

async def list_tasks(context, args: dict) -> dict:
    """
    Retrieves all tasks for the user and renders them in a visual list widget.
    """
    logger.info("Listing tasks...")
    
    # Check permissions
    if not context.auth.has_permission("list_tasks"):
        return {"error": "Access Denied"}

    # Fetch tasks using context helpers
    tasks = context.list_agent_data(scope="user", collection_name="tasks")
    
    # Sort tasks in python by priority and created_at
    priority_order = {"high": 0, "medium": 1, "low": 2}
    tasks.sort(key=lambda x: (priority_order.get(x.get("priority", "medium"), 1), x.get("created_at", "")))
    
    # Construct a Generative Custom UI payload (Lego UI elements)
    task_elements = []
    
    if not tasks:
        task_elements.append({
            "type": "text",
            "props": {
                "text": "🎉 All caught up! No tasks found.",
                "className": "text-center text-gray-500 py-4 italic"
            }
        })
    else:
        for t in tasks:
            is_completed = t.get("completed", False)
            status_indicator = "✅" if is_completed else "⭕"
            priority_label = f"[{t.get('priority', 'medium').upper()}]"
            priority_color = "text-red-500" if t.get("priority") == "high" else "text-amber-500" if t.get("priority") == "medium" else "text-blue-500"
            
            task_elements.append({
                "type": "container",
                "props": {
                    "className": "flex items-center justify-between p-3 border-b border-gray-100 hover:bg-gray-50"
                },
                "children": [
                    {
                        "type": "container",
                        "props": {"className": "flex items-center gap-2"},
                        "children": [
                            {"type": "text", "props": {"text": status_indicator, "className": "text-lg"}},
                            {
                                "type": "text", 
                                "props": {
                                    "text": t.get("title", ""), 
                                    "className": f"font-medium {'line-through text-gray-400' if is_completed else 'text-gray-800'}"
                                }
                            }
                        ]
                    },
                    {
                        "type": "container",
                        "props": {"className": "flex items-center gap-3"},
                        "children": [
                            {"type": "text", "props": {"text": priority_label, "className": f"text-xs font-bold {priority_color}"}},
                            # If not completed, show complete button
                            *( [] if is_completed else [{
                                "type": "button",
                                "props": {
                                    "label": "Done",
                                    "actionUrl": "/api/plugins/todo_agent/complete",
                                    "payload": {"task_id": t.get("id")}
                                }
                            }])
                        ]
                    }
                ]
            })

    custom_layout = {
        "type": "container",
        "props": {
            "className": "bg-white border border-gray-200 rounded-xl p-4 shadow-sm max-w-md w-full"
        },
        "children": [
            {
                "type": "text",
                "props": {
                    "text": f"📋 {context.auth.name}'s Task List",
                    "className": "text-lg font-bold border-b pb-2 mb-2 text-emerald-700"
                }
            },
            {
                "type": "container",
                "props": {"className": "divide-y divide-gray-100"},
                "children": task_elements
            }
        ]
    }

    # Register visual UI in context
    context.show_custom_ui(layout=custom_layout, data={"total_tasks": len(tasks)})

    return {
        "status": "success",
        "tasks_count": len(tasks),
        "tasks": [{"id": t.get("id"), "title": t.get("title"), "completed": t.get("completed")} for t in tasks]
    }

async def add_task(context, args: dict) -> dict:
    """
    Adds a new task to the user's todo collection.
    """
    title = args.get("title")
    priority = args.get("priority", "medium")
    
    if not title:
        return {"status": "error", "message": "Missing task title."}

    logger.info(f"Adding task: {title} ({priority})")
    
    # Generate unique ID for task
    task_id = str(uuid.uuid4())
    
    # Save using context helpers
    saved_doc = context.save_agent_data(
        scope="user",
        collection_name="tasks",
        doc_id=task_id,
        data={
            "title": title,
            "priority": priority,
            "completed": False
        }
    )
    
    # Refresh the UI by showing the updated list of tasks
    await list_tasks(context, {})

    return {
        "status": "success",
        "message": f"Added task '{title}' successfully.",
        "task": saved_doc
    }

async def complete_task(context, args: dict) -> dict:
    """
    Marks a task as completed in the database.
    """
    task_id = args.get("task_id")
    if not task_id:
        return {"status": "error", "message": "Missing task_id."}

    logger.info(f"Completing task: {task_id}")
    
    # Fetch existing task
    task_data = context.get_agent_data(scope="user", collection_name="tasks", doc_id=task_id)
    if not task_data:
        return {"status": "error", "message": "Task not found."}

    # Update completed flag
    task_data["completed"] = True
    
    # Save back
    context.save_agent_data(
        scope="user",
        collection_name="tasks",
        doc_id=task_id,
        data=task_data
    )

    # Refresh the UI
    await list_tasks(context, {})

    return {
        "status": "success",
        "message": f"Marked task '{task_data.get('title')}' as completed."
    }
