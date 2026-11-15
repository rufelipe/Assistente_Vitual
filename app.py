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


from urllib.parse import quote
import re
import unicodedata

def _normalize_text(value):
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(ch for ch in value if not unicodedata.combining(ch))

def _column_letter(number):
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result

def answer_from_sheets(message, sheets, spreadsheet_url=""):
    """Responde com base nos valores enviados pelo Google Apps Script."""
    question = _normalize_text(message).strip()
    if not isinstance(sheets, list) or not sheets:
        return None

    stop_words = {
        "qual", "quais", "quanto", "quantos", "quantas", "como", "esta",
        "estao", "tem", "tenho", "para", "por", "com", "da", "das", "de",
        "do", "dos", "e", "o", "a", "os", "as", "na", "no", "nas", "nos",
        "equipe", "meu", "minha", "sobre", "mostre", "consulte", "ver"
    }
    terms = [word for word in re.findall(r"[a-z0-9]+", question)
             if len(word) > 2 and word not in stop_words]

    is_nps = any(term in question for term in
                 ("nps", "satisfacao", "detrator", "promotor"))

    rows_found = []
    nps_found = []

    for sheet in sheets:
        if not isinstance(sheet, dict):
            continue
        sheet_name = str(sheet.get("name") or sheet.get("sheetName") or "Planilha")
        values = sheet.get("values") or []
        sheet_id = sheet.get("sheetId", sheet.get("gid"))

        if not isinstance(values, list):
            continue

        for row_index, row in enumerate(values):
            if not isinstance(row, list):
                continue
            cells = [str(cell or "").strip() for cell in row]
            nonempty = [(i, value) for i, value in enumerate(cells) if value]
            if not nonempty:
                continue

            row_text = _normalize_text(" ".join(cells))
            matched = [term for term in terms if term in row_text]
            if is_nps and "nps" in row_text:
                for col_index, value in nonempty:
                    if "nps" in _normalize_text(value):
                        result_cell = None
                        for value_index in range(col_index + 1, len(cells)):
                            if cells[value_index]:
                                result_cell = value_index
                                break
                        if result_cell is not None:
                            nps_found.append({
                                "sheet": sheet_name,
                                "cell": f"{_column_letter(result_cell + 1)}{row_index + 1}",
                                "value": cells[result_cell],
                                "sheet_id": sheet_id
                            })
                        break

            if matched:
                score = len(matched)
                rows_found.append({
                    "score": score,
                    "sheet": sheet_name,
                    "row": row_index + 1,
                    "cells": nonempty[:12],
                    "sheet_id": sheet_id,
                    "matched": matched
                })

    if is_nps and nps_found:
        # Prioriza o indicador localizado no Dashboard.
        nps_found.sort(key=lambda item: 0 if item["sheet"].strip().lower() == "dashboard" else 1)
        found = nps_found[0]
        base_url = spreadsheet_url.split("#")[0] if spreadsheet_url else ""
        source_url = (f"{base_url}#gid={found['sheet_id']}&range={quote(found['cell'], safe='!:')}"
                      if base_url and found["sheet_id"] is not None else "")
        sources = [{
            "sheetName": found["sheet"],
            "range": found["cell"],
            "label": f"{found['sheet']}!{found['cell']}",
            "url": source_url
        }] if source_url else []
        return {
            "reply": f"O NPS encontrado na planilha é {found['value']}. Fonte: {found['sheet']}!{found['cell']}.",
            "sources": sources
        }

    if rows_found:
        rows_found.sort(key=lambda item: item["score"], reverse=True)
        best = rows_found[:5]
        output = []
        sources = []
        for item in best:
            details = " | ".join(f"{_column_letter(col + 1)}: {value}"
                                 for col, value in item["cells"])
            output.append(f"{item['sheet']} (linha {item['row']}): {details}")
            base_url = spreadsheet_url.split("#")[0] if spreadsheet_url else ""
            if base_url and item["sheet_id"] is not None:
                cell = f"A{item['row']}"
                sources.append({
                    "sheetName": item["sheet"],
                    "range": cell,
                    "label": f"{item['sheet']}!{cell}",
                    "url": f"{base_url}#gid={item['sheet_id']}&range={quote(cell, safe='!:')}"
                })
        return {
            "reply": "Encontrei estas informações nas abas da planilha:\n" + "\n".join(output),
            "sources": sources
        }

    return None


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

@app.post("/api/chat")
def api_chat():
    body = request.get_json(silent=True) or {}
    message = body.get("message", "")
    supplied_tasks = body.get("tasks")
    supplied_notes = body.get("notes")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Envie uma mensagem em 'message'."}), 400
    try:
        sheet_result = answer_from_sheets(
            message,
            body.get("sheets", []),
            body.get("spreadsheetUrl", "")
        )
        if sheet_result is not None:
            return jsonify(sheet_result)
        return jsonify({
            "reply": answer(message, supplied_tasks, supplied_notes),
            "sources": []
        })
    except Exception as exc:
        return jsonify({
            "reply": "Não consegui consultar os dados agora.",
            "error": str(exc),
            "sources": []
        }), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
