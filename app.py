import os
from flask import Flask, jsonify, request, send_from_directory
from crm_api import CRMRestClient

app = Flask(__name__, static_folder=None)

CRM_API_URL = os.environ.get("CRM_API_URL", "https://salesforceteste.vercel.app")
CRM_ACCESS_TOKEN = os.environ.get("CRM_ACCESS_TOKEN", "")

def crm():
    return CRMRestClient(CRM_API_URL, CRM_ACCESS_TOKEN)

def get_tasks():
    data = crm().get_records("/api/tasks")
    return data if isinstance(data, list) else []

def get_notes():
    data = crm().get_records("/api/notes")
    return data if isinstance(data, list) else []

def answer(message, supplied_tasks=None, supplied_notes=None):
    from datetime import date, datetime
    text = (message or "").strip().lower()
    tasks = supplied_tasks if isinstance(supplied_tasks, list) else get_tasks()
    notes = supplied_notes if isinstance(supplied_notes, list) else get_notes()

    def is_overdue(task):
        try:
            due = datetime.strptime(str(task.get("due", ""))[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return False
        status = str(task.get("status", "")).strip().lower()
        return due < date.today() and status not in ("concluída", "concluida", "completed", "done")

    def task_label(task):
        task_id = task.get("id")
        prefix = f"Tarefa #{task_id}" if task_id else "Tarefa"
        return f"{prefix} — {task.get('title', 'Tarefa')} — {task.get('owner', 'sem responsável')} — {task.get('due', 'sem prazo')} — {task.get('status', 'sem status')}"

    if any(x in text for x in ("atrasad", "vencid")):
        result = [task for task in tasks if is_overdue(task)]
        if not result:
            return "Não encontrei tarefas em atraso no momento."
        lines = [
            "• {} | contrato {} | prazo {} | responsável {}".format(
                task.get("title", "Tarefa"), task.get("contract", "—"),
                task.get("due", "—"), task.get("owner", "—")
            ) for task in result[:10]
        ]
        return "Encontrei {} tarefa(s) em atraso:\n{}".format(len(result), "\n".join(lines))

    if any(x in text for x in ("anotação", "anotacoes", "nota", "notas")):
        if not notes:
            return "Não encontrei anotações no CRM no momento."
        lines = [
            "• {}: {} | contrato {}".format(
                note.get("contact", "Contato"), note.get("text", ""),
                note.get("contract") or "não informado"
            ) for note in notes[:8]
        ]
        return "Estas são as anotações encontradas:\n" + "\n".join(lines)

    if any(x in text for x in ("tarefa", "tarefas", "pendência", "pendencias")):
        if not tasks:
            return "Não encontrei tarefas no CRM no momento."
        return "Encontrei estas tarefas no CRM:\n" + "\n".join(
            "• " + task_label(task) for task in tasks[:8]
        )

    if any(x in text for x in ("oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "tudo bem")):
        return "Olá! Estou conectado ao CRM. Posso consultar tarefas, anotações, responsáveis, prazos e status para você."

    return "Posso consultar o CRM para você. Experimente perguntar: “quais tarefas estão atrasadas?”, “mostre as anotações” ou “quais são minhas tarefas?”"

@app.get("/")
def index():
    return send_from_directory(".", "index.html")

@app.get("/assets/<path:filename>")
def assets(filename):
    return send_from_directory("assets", filename)

@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})

@app.get("/api/tasks")
def api_tasks():
    try:
        return jsonify(get_tasks())
    except Exception as exc:
        return jsonify({"error": "Não foi possível consultar as tarefas do CRM.", "detail": str(exc)}), 502

@app.get("/api/notes")
def api_notes():
    try:
        return jsonify(get_notes())
    except Exception as exc:
        return jsonify({"error": "Não foi possível consultar as anotações do CRM.", "detail": str(exc)}), 502

@app.post("/api/chat")
def api_chat():
    body = request.get_json(silent=True) or {}
    message = body.get("message", "")
    supplied_tasks = body.get("tasks")
    supplied_notes = body.get("notes")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Envie uma mensagem em 'message'."}), 400
    try:
        return jsonify({"reply": answer(message, supplied_tasks, supplied_notes)})
    except Exception as exc:
        return jsonify({"reply": "Não consegui consultar o CRM agora.", "error": str(exc)}), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
