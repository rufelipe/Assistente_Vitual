import os
from datetime import date, datetime
from flask import Flask, jsonify, request, send_from_directory

from crm_api import CRMRestClient, CRM_API_URL

app = Flask(__name__, static_folder=".", static_url_path="")
CRM_URL = os.environ.get("CRM_API_URL", CRM_API_URL)
TOKEN = os.environ.get("CRM_ACCESS_TOKEN", "")
client = CRMRestClient(CRM_URL, TOKEN)


def load_tasks():
    records = client.get_records(os.environ.get("CRM_TASKS_ENDPOINT", "/api/tasks"))
    tasks = []
    for item in records:
        if not isinstance(item, dict):
            continue
        due = item.get("due")
        parsed_due = None
        if due:
            try:
                parsed_due = datetime.strptime(str(due)[:10], "%Y-%m-%d").date().isoformat()
            except ValueError:
                parsed_due = None
        tasks.append({
            "cliente": item.get("related") or "Não informado",
            "titulo": item.get("title") or "Tarefa sem título",
            "responsavel": item.get("owner") or "Não informado",
            "vencimento": parsed_due,
            "vencimento_original": due,
            "prioridade": item.get("priority") or "Não informada",
            "status": item.get("status") or "Não informado",
            "etapa": item.get("stage"),
            "contrato": item.get("contract"),
            "resposta": item.get("response"),
            "observacao": item.get("observation"),
            "relacionado": item.get("related"),
        })
    return tasks


def load_notes():
    records = client.get_records(os.environ.get("CRM_NOTES_ENDPOINT", "/api/notes"))
    return [
        {"contato": item.get("contact") or "Contato não informado",
         "texto": item.get("text") or ""}
        for item in records if isinstance(item, dict)
    ]


def is_open(task):
    status = str(task.get("status", "")).strip().lower()
    return status not in ("concluída", "concluida", "completed", "complete", "done", "finalizada", "finalizado")


def dashboard_data():
    tasks, notes = load_tasks(), load_notes()
    today = date.today().isoformat()
    open_tasks = [t for t in tasks if is_open(t)]
    overdue = [t for t in open_tasks if t["vencimento"] and t["vencimento"] < today]
    due_today = [t for t in open_tasks if t["vencimento"] == today]
    high = [t for t in open_tasks if str(t["prioridade"]).lower() in ("alta", "high", "urgent", "urgente")]
    waiting = [t for t in open_tasks if any(word in str(t.get("status", "")).lower() for word in ("aguardando", "pendente", "waiting", "pending"))]
    return {
        "tasks": tasks, "notes": notes,
        "summary": {"total": len(tasks), "abertas": len(open_tasks),
                    "atrasadas": len(overdue), "vencem_hoje": len(due_today),
                    "prioridade_alta": len(high), "aguardando_resposta": len(waiting)},
        "lists": {"atrasadas": overdue, "vencem_hoje": due_today, "prioridade_alta": high,
                  "aguardando_resposta": waiting},
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": CRM_URL,
    }


@app.get("/")
def home():
    return send_from_directory(".", "index.html")


@app.get("/healthz")
def health():
    return jsonify({"ok": True, "service": "assistente-virtual"})


@app.get("/api/dashboard")
def dashboard():
    try:
        return jsonify(dashboard_data())
    except Exception as exc:
        app.logger.exception("Falha ao consultar Salesforce")
        return jsonify({"error": "Não foi possível consultar o Salesforce.", "detail": str(exc)}), 502


@app.get("/api/tasks")
def tasks_endpoint():
    try:
        return jsonify({"tasks": load_tasks()})
    except Exception as exc:
        app.logger.exception("Falha ao consultar tarefas")
        return jsonify({"error": "Não foi possível carregar as tarefas.", "detail": str(exc)}), 502


@app.get("/api/notes")
def notes_endpoint():
    try:
        return jsonify({"notes": load_notes()})
    except Exception as exc:
        app.logger.exception("Falha ao consultar anotações")
        return jsonify({"error": "Não foi possível carregar as anotações.", "detail": str(exc)}), 502


@app.post("/api/chat")
def chat():
    body = request.get_json(silent=True) or {}
    question = str(body.get("question", "")).strip()
    if not question:
        return jsonify({"error": "Envie uma pergunta no campo question."}), 400
    try:
        data = dashboard_data()
    except Exception as exc:
        app.logger.exception("Falha ao montar resposta")
        return jsonify({"error": "Não consegui consultar o Salesforce agora.", "detail": str(exc)}), 502

    q = question.lower()
    lists = data["lists"]
    if any(word in q for word in ("atrasad", "vencid", "em atraso")):
        label, selected = "Tarefas atrasadas", lists["atrasadas"]
    elif any(word in q for word in ("hoje", "vencem hoje", "para hoje")):
        label, selected = "Tarefas com vencimento hoje", lists["vencem_hoje"]
    elif any(word in q for word in ("prioridade", "urgente", "alta")):
        label, selected = "Tarefas de prioridade alta", lists["prioridade_alta"]
    elif any(word in q for word in ("resposta", "retorno", "aguardando")):
        label, selected = "Tarefas com status de espera ou pendência", lists["aguardando_resposta"]
    elif any(word in q for word in ("anota", "observa", "nota")):
        label, selected = "Anotações do Salesforce", data["notes"]
    else:
        label, selected = "Tarefas do Salesforce", data["tasks"]

    if not selected:
        answer = "Não encontrei registros nessa categoria no Salesforce."
    elif label == "Anotações do Salesforce":
        answer = "{}: {} registro(s).".format(label, len(selected))
    else:
        answer = "{}: {} registro(s).".format(label, len(selected))
    return jsonify({"question": question, "answer": answer, "category": label,
                    "results": selected, "summary": data["summary"]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
