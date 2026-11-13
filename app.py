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


def get_sheet_data():
    """Lê a planilha somente quando a integração está configurada."""
    if not os.environ.get("GOOGLE_SHEET_ID") or not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
        return None
    try:
        from google_sheets import read_sheet
        return read_sheet()
    except Exception:
        return None


def format_sheet_rows(values, limit=20):
    if not values:
        return "A planilha está vazia ou não retornou dados."

    headers = values[0] if values else []
    rows = values[1:] if len(values) > 1 else []
    lines = []

    for row_number, row in enumerate(rows[:limit], start=2):
        parts = []
        width = max(len(headers), len(row))
        for index in range(width):
            value = row[index] if index < len(row) else ""
            if value != "":
                label = headers[index] if index < len(headers) and headers[index] else f"Coluna {index + 1}"
                parts.append(f"{label}: {value}")
        if parts:
            lines.append(f"Linha {row_number} — " + " | ".join(parts))

    if not lines:
        return "A planilha possui cabeçalho, mas não há registros preenchidos."

    return "\n".join(lines)


def answer(message, supplied_tasks=None, supplied_notes=None, sheet_context=None):
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
        return (
            f"{prefix} — {task.get('title', 'Tarefa')} — "
            f"{task.get('owner', 'sem responsável')} — "
            f"{task.get('due', 'sem prazo')} — "
            f"{task.get('status', 'sem status')}"
        )

    sheet_question = any(term in text for term in (
        "planilha", "google sheets", "sheets", "linha da planilha",
        "dados da planilha", "o que mudou na planilha", "mudou na planilha",
        "alteração na planilha", "alteracoes na planilha", "alterações na planilha",
    ))

    if sheet_question:
        if not sheet_context:
            return (
                "A integração com o Google Sheets ainda não está configurada ou "
                "não consegui acessar a planilha agora."
            )

        values = sheet_context.get("values", [])
        if any(term in text for term in (
            "mudou", "mudança", "mudanca", "alterou", "alteração",
            "alteracao", "última alteração", "ultima alteracao"
        )):
            return (
                "A planilha está sendo monitorada. A última verificação foi em "
                f"{sheet_context.get('checked_at', 'horário não informado')}. "
                "Para identificar exatamente o que mudou, use o alerta de alteração "
                "no painel ou faça uma nova consulta."
            )

        return "Encontrei estes dados na planilha:\n" + format_sheet_rows(values)

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
            return (
                "Não encontrei ligações pendentes no CRM. Verifique se as tarefas "
                "estão marcadas com 'Retornar contato' ou possuem uma observação de ligação."
            )

        def call_sort_key(task):
            try:
                due = datetime.strptime(str(task.get("due", ""))[:10], "%Y-%m-%d").date()
            except (TypeError, ValueError):
                due = date.max

            raw_time = str(
                task.get("call_time") or task.get("scheduled_time") or task.get("horario") or ""
            ).strip()
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
        raw_time = str(
            first.get("call_time") or first.get("scheduled_time") or first.get("horario") or ""
        ).strip()
        due = first.get("due") or "prazo não informado"
        contract = first.get("contract") or "não informado"

        if raw_time:
            human_time = raw_time[:5].replace(":", "h")
            return f"Eu começaria pelo contrato {contract} — a ligação está marcada para às {human_time}."

        return (
            f"Eu começaria pelo contrato {contract}. O horário da ligação não está informado "
            f"no CRM; considerei o prazo {due} e a prioridade {first.get('priority') or 'não informada'}."
        )

    if any(x in text for x in ("atrasad", "vencid")):
        result = [task for task in tasks if is_overdue(task)]
        if not result:
            return "Não encontrei tarefas em atraso no momento."

        lines = [
            "• {} | contrato {} | prazo {} | responsável {}".format(
                task.get("title", "Tarefa"),
                task.get("contract", "—"),
                task.get("due", "—"),
                task.get("owner", "—"),
            )
            for task in result[:10]
        ]
        return f"Encontrei {len(result)} tarefa(s) em atraso:\n" + "\n".join(lines)

    if any(x in text for x in ("anotação", "anotacoes", "nota", "notas")):
        if not notes:
            return "Não encontrei anotações no CRM no momento."

        lines = [
            "• {}: {} | contrato {}".format(
                note.get("contact", "Contato"),
                note.get("text", ""),
                note.get("contract") or "não informado",
            )
            for note in notes[:8]
        ]
        return "Estas são as anotações encontradas:\n" + "\n".join(lines)

    if any(x in text for x in ("tarefa", "tarefas", "pendência", "pendencias")):
        if not tasks:
            return "Não encontrei tarefas no CRM no momento."

        return "Encontrei estas tarefas no CRM:\n" + "\n".join(
            "• " + task_label(task) for task in tasks[:8]
        )

    if any(x in text for x in ("oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "tudo bem")):
        return (
            "Olá! Estou conectado ao CRM e ao Google Sheets. Posso consultar tarefas, "
            "anotações, responsáveis, prazos, status e dados da planilha."
        )

    return (
        "Posso consultar o CRM e o Google Sheets. Experimente perguntar: "
        "“quais tarefas estão atrasadas?”, “quem devo ligar primeiro?” ou "
        "“mostre os dados da planilha”."
    )


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
        return jsonify({
            "error": "Não foi possível consultar as tarefas do CRM.",
            "detail": str(exc),
        }), 502


@app.get("/api/notes")
def api_notes():
    try:
        return jsonify(get_notes())
    except Exception as exc:
        return jsonify({
            "error": "Não foi possível consultar as anotações do CRM.",
            "detail": str(exc),
        }), 502


@app.get("/api/sheets/status")
def api_sheets_status():
    if not os.environ.get("GOOGLE_SHEET_ID") or not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
        return jsonify({
            "enabled": False,
            "message": "Integração Google Sheets ainda não configurada no Render.",
        })

    try:
        from google_sheets import check_for_changes
        result = check_for_changes()
        result["enabled"] = True
        return jsonify(result)
    except Exception as exc:
        return jsonify({
            "enabled": True,
            "error": "Não foi possível consultar a planilha.",
            "detail": str(exc),
        }), 502


@app.get("/api/sheets/data")
def api_sheets_data():
    if not os.environ.get("GOOGLE_SHEET_ID") or not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
        return jsonify({
            "enabled": False,
            "message": "Integração Google Sheets ainda não configurada no Render.",
        })

    try:
        from google_sheets import read_sheet
        return jsonify({"enabled": True, **read_sheet()})
    except Exception as exc:
        return jsonify({
            "enabled": True,
            "error": "Não foi possível ler a planilha.",
            "detail": str(exc),
        }), 502


@app.post("/api/chat")
def api_chat():
    body = request.get_json(silent=True) or {}
    message = body.get("message", "")
    supplied_tasks = body.get("tasks")
    supplied_notes = body.get("notes")

    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Envie uma mensagem em 'message'."}), 400

    sheet_context = None
    if any(term in message.lower() for term in (
        "planilha", "google sheets", "sheets", "dados da planilha"
    )):
        sheet_context = get_sheet_data()

    try:
        reply = answer(
            message,
            supplied_tasks,
            supplied_notes,
            sheet_context,
        )
        return jsonify({"reply": reply})
    except Exception as exc:
        return jsonify({
            "reply": "Não consegui consultar o CRM agora.",
            "error": str(exc),
        }), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
