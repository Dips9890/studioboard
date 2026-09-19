"""JSON-backed persistence and domain helpers for StudioBoard."""

import json
import os

STATUSES = ["todo", "doing", "done"]
STATUS_LABELS = {"todo": "To do", "doing": "In progress", "done": "Done"}
SORTS = {"manual": "Manual order", "alpha": "A–Z", "status": "By status"}
VIEWS = ["list", "board"]

DEFAULT_DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")


def data_file():
    return os.environ.get("STUDIOBOARD_DATA", DEFAULT_DATA_FILE)


def load_data():
    path = data_file()
    if not os.path.exists(path):
        return {"clients": []}
    with open(path, "r") as f:
        data = json.load(f)
    return _migrate(data)


def save_data(data):
    with open(data_file(), "w") as f:
        json.dump(data, f, indent=2)


def _migrate(data):
    """Upgrade records written by older versions of the app.

    v1 stored a boolean `done`; v2 stores a three-state `status`.
    """
    for client in data.get("clients", []):
        for project in client.get("projects", []):
            for task in project.get("tasks", []):
                if "status" not in task:
                    task["status"] = "done" if task.get("done") else "todo"
                task.pop("done", None)
    return data


def next_id(items):
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


def find_client(data, client_id):
    return next((c for c in data["clients"] if c["id"] == client_id), None)


def find_project(client, project_id):
    return next((p for p in client["projects"] if p["id"] == project_id), None)


def find_task(project, task_id):
    return next((t for t in project["tasks"] if t["id"] == task_id), None)


def project_progress(project):
    total = len(project["tasks"])
    done = sum(1 for t in project["tasks"] if t["status"] == "done")
    return done, total


def sort_tasks(tasks, sort):
    if sort == "alpha":
        return sorted(tasks, key=lambda t: t["text"].lower())
    if sort == "status":
        return sorted(tasks, key=lambda t: STATUSES.index(t["status"]))
    return list(tasks)
