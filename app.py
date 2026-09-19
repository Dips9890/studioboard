"""StudioBoard — a lightweight client/project/task manager for freelancers."""

import os

from flask import Flask, abort, redirect, render_template, request, url_for

from storage import (
    SORTS,
    STATUS_LABELS,
    STATUSES,
    VIEWS,
    find_client,
    find_project,
    find_task,
    load_data,
    next_id,
    project_progress,
    save_data,
    sort_tasks,
)

app = Flask(__name__)


def get_client(data, client_id):
    client = find_client(data, client_id)
    if client is None:
        abort(404, description="Client not found")
    return client


def get_project(client, project_id):
    project = find_project(client, project_id)
    if project is None:
        abort(404, description="Project not found")
    return project


def get_task(project, task_id):
    task = find_task(project, task_id)
    if task is None:
        abort(404, description="Task not found")
    return task


def view_params():
    view = request.args.get("view", "list")
    sort = request.args.get("sort", "manual")
    return {
        "view": view if view in VIEWS else "list",
        "sort": sort if sort in SORTS else "manual",
    }


def back_to_project(client_id, project_id):
    return redirect(
        url_for("project_detail", client_id=client_id, project_id=project_id, **view_params())
    )


# ---------- Clients ----------

@app.route("/")
def clients():
    data = load_data()
    return render_template("clients.html", clients=data["clients"])


@app.route("/clients/add", methods=["POST"])
def add_client():
    name = request.form.get("name", "").strip()
    if name:
        data = load_data()
        data["clients"].append({"id": next_id(data["clients"]), "name": name, "projects": []})
        save_data(data)
    return redirect(url_for("clients"))


@app.route("/clients/<int:client_id>/delete", methods=["POST"])
def delete_client(client_id):
    data = load_data()
    data["clients"] = [c for c in data["clients"] if c["id"] != client_id]
    save_data(data)
    return redirect(url_for("clients"))


# ---------- Projects ----------

@app.route("/clients/<int:client_id>")
def client_detail(client_id):
    data = load_data()
    client = get_client(data, client_id)
    projects = [
        {"project": p, "done": project_progress(p)[0], "total": project_progress(p)[1]}
        for p in client["projects"]
    ]
    breadcrumbs = [
        {"label": "Clients", "url": url_for("clients")},
        {"label": client["name"], "url": None},
    ]
    return render_template(
        "client.html", client=client, projects=projects, breadcrumbs=breadcrumbs
    )


@app.route("/clients/<int:client_id>/projects/add", methods=["POST"])
def add_project(client_id):
    name = request.form.get("name", "").strip()
    data = load_data()
    client = get_client(data, client_id)
    if name:
        client["projects"].append({"id": next_id(client["projects"]), "name": name, "tasks": []})
        save_data(data)
    return redirect(url_for("client_detail", client_id=client_id))


@app.route("/clients/<int:client_id>/projects/<int:project_id>/delete", methods=["POST"])
def delete_project(client_id, project_id):
    data = load_data()
    client = get_client(data, client_id)
    client["projects"] = [p for p in client["projects"] if p["id"] != project_id]
    save_data(data)
    return redirect(url_for("client_detail", client_id=client_id))


# ---------- Tasks ----------

@app.route("/clients/<int:client_id>/projects/<int:project_id>")
def project_detail(client_id, project_id):
    data = load_data()
    client = get_client(data, client_id)
    project = get_project(client, project_id)
    params = view_params()

    tasks = sort_tasks(project["tasks"], params["sort"])
    columns = [
        {
            "status": status,
            "label": STATUS_LABELS[status],
            "tasks": [t for t in tasks if t["status"] == status],
        }
        for status in STATUSES
    ]
    breadcrumbs = [
        {"label": "Clients", "url": url_for("clients")},
        {"label": client["name"], "url": url_for("client_detail", client_id=client["id"])},
        {"label": project["name"], "url": None},
    ]
    return render_template(
        "project.html",
        client=client,
        project=project,
        tasks=tasks,
        columns=columns,
        statuses=STATUSES,
        status_labels=STATUS_LABELS,
        sorts=SORTS,
        breadcrumbs=breadcrumbs,
        **params,
    )


@app.route("/clients/<int:client_id>/projects/<int:project_id>/tasks/add", methods=["POST"])
def add_task(client_id, project_id):
    text = request.form.get("text", "").strip()
    data = load_data()
    client = get_client(data, client_id)
    project = get_project(client, project_id)
    if text:
        project["tasks"].append({"id": next_id(project["tasks"]), "text": text, "status": "todo"})
        save_data(data)
    return back_to_project(client_id, project_id)


@app.route("/clients/<int:client_id>/projects/<int:project_id>/tasks/<int:task_id>/done", methods=["POST"])
def toggle_task(client_id, project_id, task_id):
    data = load_data()
    client = get_client(data, client_id)
    project = get_project(client, project_id)
    task = get_task(project, task_id)
    task["status"] = "todo" if task["status"] == "done" else "done"
    save_data(data)
    return back_to_project(client_id, project_id)


@app.route("/clients/<int:client_id>/projects/<int:project_id>/tasks/<int:task_id>/status", methods=["POST"])
def set_task_status(client_id, project_id, task_id):
    status = request.form.get("status")
    if status not in STATUSES:
        abort(400, description="Unknown status")
    data = load_data()
    client = get_client(data, client_id)
    project = get_project(client, project_id)
    task = get_task(project, task_id)
    task["status"] = status
    save_data(data)
    return back_to_project(client_id, project_id)


@app.route("/clients/<int:client_id>/projects/<int:project_id>/tasks/<int:task_id>/delete", methods=["POST"])
def delete_task(client_id, project_id, task_id):
    data = load_data()
    client = get_client(data, client_id)
    project = get_project(client, project_id)
    project["tasks"] = [t for t in project["tasks"] if t["id"] != task_id]
    save_data(data)
    return back_to_project(client_id, project_id)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=int(os.environ.get("PORT", 5050)))
