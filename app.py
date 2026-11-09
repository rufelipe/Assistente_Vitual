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

    call_question = any(term in text for term in (
        "ligar", "ligação", "ligacoes", "ligações", "telefonar",
        "retornar contato", "quem devo contatar", "contato primeiro"
    ))
    if call_question:
        active = [
            task for task in tasks
            if str(task.get("status", "")).strip().lower()
            not in ("concluída", "concluida", "completed", "done")
        ]
        call_tasks = []
        for task in active:
            response = str(task.get("response", "")).lower()
            title = str(task.get("title", "")).lower()
            observation = str(task.get("observation", "")).lower()
            if (
                "retornar contato" in response
                or any(term in title + " " + observation for term in
                       ("ligação", "ligar", "telefon", "retorno", "retornar"))
            ):
                call_tasks.append(task)

        if not call_tasks:
            return "Não encontrei ligações pendentes no CRM. Verifique se as tarefas estão marcadas com 'Retornar contato' ou possuem uma observação de ligação."

        def call_sort_key(task):
            try:
                due = datetime.strptime(str(task.get("due", ""))[:10], "%Y-%m-%d").date()
            except (TypeError, ValueError):
                due = date.max
            raw_time = str(task.get("call_time") or task.get("scheduled_time") or task.get("horario") or "").strip()
            try:
                scheduled_time = datetime.strptime(raw_time[:5], "%H:%M").time()
            except ValueError:
                scheduled_time = datetime.max.time()
            overdue_rank = 0 if due < date.today() else 1
            priority = str(task.get("priority", "")).lower()
            priority_rank = 0 if priority in ("alta", "high", "urgente") else 1
            return (overdue_rank, due, scheduled_time, priority_rank)

        call_tasks.sort(key=call_sort_key)
        first = call_tasks[0]
        raw_time = str(first.get("call_time") or first.get("scheduled_time") or first.get("horario") or "").strip()
        when = raw_time[:5] if raw_time else "horário não informado"
        due = first.get("due") or "prazo não informado"
        contract = first.get("contract") or "não informado"
        owner = first.get("owner") or "responsável não informado"
        title = first.get("title") or "Ligação de acompanhamento"
        result = [
            "• contrato {} | {} | horário {} | prazo {} | responsável {} | prioridade {}".format(
                task.get("contract") or "não informado",
                task.get("title") or "Ligação",
                str(task.get("call_time") or task.get("scheduled_time") or task.get("horario") or "")[:5] or "não informado",
                task.get("due") or "não informado",
                task.get("owner") or "não informado",
                task.get("priority") or "não informada"
            )
            for task in call_tasks[:5]
        ]
        explanation = (
            "Organizei as ligações pelo prazo e horário registrados no CRM, colocando tarefas vencidas primeiro. "
            if any(is_overdue(task) for task in call_tasks)
            else "Organizei as ligações pelo próximo prazo e horário registrados no CRM. "
        )
        if raw_time:
            human_time = raw_time[:5].replace(":", "h")
            return "Eu começaria pelo contrato {} — a ligação está marcada para às {}.".format(contract, human_time)
        return "Eu começaria pelo contrato {}. O horário da ligação não está informado no CRM; considerei o prazo {} e a prioridade {}.".format(
            contract, due, first.get("priority") or "não informada"
        )

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

\n\n@app.get("/api/sheets/status")\ndef api_sheets_status():\n    if not os.environ.get("GOOGLE_SHEET_ID") or not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):\n        return jsonify({"enabled": False, "message": "Integração Google Sheets ainda não configurada no Render."})\n    try:\n        from google_sheets import check_for_changes\n        result = check_for_changes()\n        result["enabled"] = True\n        return jsonify(result)\n    except Exception as exc:\n        return jsonify({"enabled": True, "error": "Não foi possível consultar a planilha.", "detail": str(exc)}), 502\n\n@app.get("/api/sheets/data")\ndef api_sheets_data():\n    if not os.environ.get("GOOGLE_SHEET_ID") or not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):\n        return jsonify({"enabled": False, "message": "Integração Google Sheets ainda não configurada no Render."})\n    try:\n        from google_sheets import read_sheet\n        return jsonify({"enabled": True, **read_sheet()})\n    except Exception as exc:\n        return jsonify({"enabled": True, "error": "Não foi possível ler a planilha.", "detail": str(exc)}), 502\n\n@app.post("/api/chat")
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
