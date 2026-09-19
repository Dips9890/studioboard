import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import storage  # noqa: E402
from app import app  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    data_file = tmp_path / "data.json"
    data_file.write_text(json.dumps({"clients": []}))
    monkeypatch.setenv("STUDIOBOARD_DATA", str(data_file))
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        test_client.data_file = data_file
        yield test_client


def read(client):
    return json.loads(client.data_file.read_text())


def seed_project(client):
    client.post("/clients/add", data={"name": "Acme Co"})
    client.post("/clients/1/projects/add", data={"name": "Website"})


# ---------- Clients ----------

def test_empty_state_lists_no_clients(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"No clients yet" in response.data


def test_add_client_persists(client):
    client.post("/clients/add", data={"name": "Acme Co"})
    assert [c["name"] for c in read(client)["clients"]] == ["Acme Co"]


def test_blank_client_name_is_rejected(client):
    client.post("/clients/add", data={"name": "   "})
    assert read(client)["clients"] == []


def test_delete_client_removes_it(client):
    client.post("/clients/add", data={"name": "Acme Co"})
    client.post("/clients/1/delete")
    assert read(client)["clients"] == []


def test_missing_client_returns_404(client):
    assert client.get("/clients/99").status_code == 404


# ---------- Tasks ----------

def test_add_task_defaults_to_todo(client):
    seed_project(client)
    client.post("/clients/1/projects/1/tasks/add", data={"text": "Design homepage"})
    task = read(client)["clients"][0]["projects"][0]["tasks"][0]
    assert task["text"] == "Design homepage"
    assert task["status"] == "todo"


def test_toggle_task_flips_between_todo_and_done(client):
    seed_project(client)
    client.post("/clients/1/projects/1/tasks/add", data={"text": "Ship it"})
    client.post("/clients/1/projects/1/tasks/1/done")
    assert read(client)["clients"][0]["projects"][0]["tasks"][0]["status"] == "done"
    client.post("/clients/1/projects/1/tasks/1/done")
    assert read(client)["clients"][0]["projects"][0]["tasks"][0]["status"] == "todo"


def test_set_status_moves_task_across_board(client):
    seed_project(client)
    client.post("/clients/1/projects/1/tasks/add", data={"text": "Ship it"})
    client.post("/clients/1/projects/1/tasks/1/status", data={"status": "doing"})
    assert read(client)["clients"][0]["projects"][0]["tasks"][0]["status"] == "doing"


def test_unknown_status_is_rejected(client):
    seed_project(client)
    client.post("/clients/1/projects/1/tasks/add", data={"text": "Ship it"})
    response = client.post("/clients/1/projects/1/tasks/1/status", data={"status": "archived"})
    assert response.status_code == 400
    assert read(client)["clients"][0]["projects"][0]["tasks"][0]["status"] == "todo"


def test_ids_do_not_collide_after_deletion(client):
    seed_project(client)
    for text in ("first", "second"):
        client.post("/clients/1/projects/1/tasks/add", data={"text": text})
    client.post("/clients/1/projects/1/tasks/2/delete")
    client.post("/clients/1/projects/1/tasks/add", data={"text": "third"})
    ids = [t["id"] for t in read(client)["clients"][0]["projects"][0]["tasks"]]
    assert len(ids) == len(set(ids))


# ---------- Views and sorting ----------

def test_board_view_renders_status_columns(client):
    seed_project(client)
    response = client.get("/clients/1/projects/1?view=board")
    assert b"In progress" in response.data


def test_invalid_view_falls_back_to_list(client):
    seed_project(client)
    client.post("/clients/1/projects/1/tasks/add", data={"text": "Ship it"})
    response = client.get("/clients/1/projects/1?view=gantt&sort=nonsense")
    assert response.status_code == 200
    assert b"In progress" not in response.data


def test_task_actions_preserve_the_active_view(client):
    seed_project(client)
    client.post("/clients/1/projects/1/tasks/add", data={"text": "Ship it"})
    response = client.post("/clients/1/projects/1/tasks/1/status?view=board&sort=alpha",
                           data={"status": "doing"})
    assert "view=board" in response.headers["Location"]
    assert "sort=alpha" in response.headers["Location"]


# ---------- Storage helpers ----------

def test_sort_tasks_alphabetically_is_case_insensitive():
    tasks = [{"text": "beta", "status": "todo"}, {"text": "Alpha", "status": "todo"}]
    assert [t["text"] for t in storage.sort_tasks(tasks, "alpha")] == ["Alpha", "beta"]


def test_sort_tasks_by_status_follows_board_order():
    tasks = [
        {"text": "c", "status": "done"},
        {"text": "a", "status": "todo"},
        {"text": "b", "status": "doing"},
    ]
    assert [t["status"] for t in storage.sort_tasks(tasks, "status")] == ["todo", "doing", "done"]


def test_manual_sort_preserves_insertion_order():
    tasks = [{"text": "b", "status": "done"}, {"text": "a", "status": "todo"}]
    assert [t["text"] for t in storage.sort_tasks(tasks, "manual")] == ["b", "a"]


def test_legacy_done_flag_migrates_to_status(tmp_path, monkeypatch):
    legacy = {
        "clients": [
            {
                "id": 1,
                "name": "Acme Co",
                "projects": [
                    {
                        "id": 1,
                        "name": "Website",
                        "tasks": [
                            {"id": 1, "text": "old done", "done": True},
                            {"id": 2, "text": "old open", "done": False},
                        ],
                    }
                ],
            }
        ]
    }
    data_file = tmp_path / "legacy.json"
    data_file.write_text(json.dumps(legacy))
    monkeypatch.setenv("STUDIOBOARD_DATA", str(data_file))

    tasks = storage.load_data()["clients"][0]["projects"][0]["tasks"]
    assert [t["status"] for t in tasks] == ["done", "todo"]
    assert all("done" not in t for t in tasks)


def test_progress_counts_only_completed_tasks():
    project = {
        "tasks": [
            {"status": "done"},
            {"status": "doing"},
            {"status": "todo"},
        ]
    }
    assert storage.project_progress(project) == (1, 3)
