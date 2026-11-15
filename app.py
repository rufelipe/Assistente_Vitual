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

def _sheet_header(values, required):
    """Localiza a linha de cabeçalho mesmo quando a aba tem linhas de título."""
    required = {_normalize_text(x) for x in required}
    for row_index, row in enumerate(values[:15]):
        if not isinstance(row, list):
            continue
        headers = [_normalize_text(x) for x in row]
        if len(required.intersection(headers)) >= min(2, len(required)):
            return row_index, headers
    return None, []


def _cell_value(row, headers, *names):
    for name in names:
        key = _normalize_text(name)
        if key in headers:
            index = headers.index(key)
            return row[index] if index < len(row) else ""
    return ""


def _parse_sheet_date(value):
    from datetime import datetime, date
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            pass
    return None


def _nps_analysis(message, sheets, spreadsheet_url=""):
    from collections import defaultdict
    from datetime import date
    question = _normalize_text(message)
    nps_sheet = next((s for s in sheets if isinstance(s, dict) and
                      "nps" in _normalize_text(s.get("name") or s.get("sheetName"))), None)
    if not nps_sheet:
        return None

    values = nps_sheet.get("values") or []
    header_row, headers = _sheet_header(
        values, ["Data resposta", "Nota", "Categoria da nota", "E-mail analista"]
    )
    if header_row is None:
        return {"reply": "Encontrei a aba NPS Diário, mas não consegui identificar todos os cabeçalhos necessários para calcular o NPS.", "sources": []}

    roster = {}
    roster_sheet = next((s for s in sheets if isinstance(s, dict) and
                         "equipe" in _normalize_text(s.get("name") or s.get("sheetName"))), None)
    if roster_sheet:
        rv = roster_sheet.get("values") or []
        rh_index, rh = _sheet_header(rv, ["Nome", "E-mail"])
        if rh_index is not None:
            for row in rv[rh_index + 1:]:
                if not isinstance(row, list):
                    continue
                email = str(_cell_value(row, rh, "E-mail", "Email") or "").strip().lower()
                name = str(_cell_value(row, rh, "Nome") or "").strip()
                if email and name:
                    roster[email] = name

    today = date.today()
    month_requested = any(x in question for x in ("este mes", "nesse mes", "mes atual", "em novembro", "novembro"))
    october_requested = "outubro" in question
    selected = []
    unmatched = set()
    for row in values[header_row + 1:]:
        if not isinstance(row, list):
            continue
        email = str(_cell_value(row, headers, "E-mail analista", "Email analista") or "").strip().lower()
        category = _normalize_text(_cell_value(row, headers, "Categoria da nota", "Tipo NPS"))
        raw_date = _cell_value(row, headers, "Data resposta", "Data")
        response_date = _parse_sheet_date(raw_date)
        if not email or not category:
            continue
        if month_requested and response_date and response_date.month != today.month:
            continue
        if october_requested and response_date and response_date.month != 10:
            continue
        if not any(term in category for term in ("promoter", "promotor", "passive", "neutro", "detractor", "detrator")):
            continue
        if email not in roster:
            unmatched.add(email)
        selected.append((email, category, response_date))

    if not selected:
        return {"reply": "Não encontrei avaliações de NPS para o período solicitado na aba NPS Diário.", "sources": []}

    stats = defaultdict(lambda: {"promotores": 0, "neutros": 0, "detratores": 0, "total": 0})
    for email, category, _ in selected:
        item = stats[email]
        item["total"] += 1
        if "promot" in category:
            item["promotores"] += 1
        elif "passiv" in category or "neutr" in category:
            item["neutros"] += 1
        elif "detract" in category or "detrat" in category:
            item["detratores"] += 1

    for item in stats.values():
        item["nps"] = round((item["promotores"] - item["detratores"]) * 100 / item["total"], 2)

    is_promoters = "promotor" in question
    is_detractors = "detrator" in question
    is_best = any(x in question for x in ("melhor", "maior", "top", "ranking", "lider"))
    is_worst = any(x in question for x in ("pior", "menor", "baixo", "atencao", "precisa"))
    is_comparison = any(x in question for x in ("compare", "comparacao", "todos", "analistas", "ranking"))
    ordered = sorted(stats.items(), key=lambda pair: pair[1]["nps"], reverse=True)

    def label(email):
        return roster.get(email, f"E-mail sem correspondência no cadastro ({email})")

    if is_promoters:
        ranked = sorted(stats.items(), key=lambda pair: pair[1]["promotores"], reverse=True)
        title = "Quantidade de avaliações promotoras"
        value_key = "promotores"
    elif is_detractors:
        ranked = sorted(stats.items(), key=lambda pair: pair[1]["detratores"], reverse=True)
        title = "Quantidade de avaliações detratoras"
        value_key = "detratores"
    else:
        ranked = ordered
        title = "Ranking de NPS por analista"
        value_key = "nps"

    if is_best and not is_comparison and not is_promoters and not is_detractors:
        ranked = ranked[:1]
        title = "Maior NPS encontrado"
    elif is_worst and not is_comparison and not is_promoters and not is_detractors:
        ranked = sorted(stats.items(), key=lambda pair: pair[1]["nps"])
        ranked = ranked[:1]
        title = "Menor NPS encontrado"

    period = "mês atual" if month_requested else ("outubro" if october_requested else "todo o período disponível")
    lines = []
    for rank, (email, item) in enumerate(ranked, 1):
        value = f"{item[value_key]}%" if value_key == "nps" else str(item[value_key])
        lines.append(
            f"{rank}. {label(email)} — NPS {item['nps']:.2f} | "
            f"{item['promotores']} promotores, {item['neutros']} neutros, "
            f"{item['detratores']} detratores ({item['total']} avaliações)"
        )

    total = len(selected)
    promoters = sum(x["promotores"] for x in stats.values())
    detractors = sum(x["detratores"] for x in stats.values())
    overall = round((promoters - detractors) * 100 / total, 2)
    reply = (
        f"{title} — {period}.\n"
        f"NPS geral das avaliações consideradas: {overall:.2f} ({total} respostas).\n"
        + "\n".join(lines)
    )
    if unmatched:
        reply += (
            "\n\nAtenção: há e-mails nas avaliações que não correspondem exatamente "
            "ao cadastro da aba Equipe e Config. Mantive esses registros separados "
            "para não atribuir resultados à pessoa errada."
        )

    base_url = spreadsheet_url.split("#")[0] if spreadsheet_url else ""
    sheet_id = nps_sheet.get("sheetId", nps_sheet.get("gid"))
    source_url = f"{base_url}#gid={sheet_id}&range=A{header_row + 1}:O{len(values)}" if base_url and sheet_id is not None else ""
    sources = [{
        "sheetName": nps_sheet.get("name") or nps_sheet.get("sheetName") or "NPS Diário",
        "range": f"A{header_row + 1}:O{len(values)}",
        "label": "NPS Diário — avaliações utilizadas",
        "url": source_url
    }] if source_url else []
    return {"reply": reply, "sources": sources}



def _is_yes(value):
    value = _normalize_text(value).strip()
    return value in ("sim", "s", "yes", "y", "true", "1", "faltou", "ausente", "falta")


def _abs_analysis(message, sheets, spreadsheet_url=""):
    from collections import defaultdict
    question = _normalize_text(message)
    abs_sheet = next((s for s in sheets if isinstance(s, dict) and
                      "abs" in _normalize_text(s.get("name") or s.get("sheetName"))), None)
    if not abs_sheet:
        return {"reply": "Não recebi a aba ABS Diário no contexto enviado pela planilha. Verifique se o Apps Script está enviando todas as abas.", "sources": []}

    values = abs_sheet.get("values") or []
    header_row, headers = _sheet_header(
        values, ["Data", "E-mail do analista", "Faltou"]
    )
    if header_row is None:
        return {"reply": "Encontrei a aba ABS Diário, mas não identifiquei os cabeçalhos Data, E-mail do analista e Faltou.", "sources": []}

    roster = {}
    roster_sheet = next((s for s in sheets if isinstance(s, dict) and
                         "equipe" in _normalize_text(s.get("name") or s.get("sheetName"))), None)
    if roster_sheet:
        rv = roster_sheet.get("values") or []
        ri, rh = _sheet_header(rv, ["Nome", "E-mail"])
        if ri is not None:
            for row in rv[ri + 1:]:
                if isinstance(row, list):
                    email = str(_cell_value(row, rh, "E-mail", "Email") or "").strip().lower()
                    name = str(_cell_value(row, rh, "Nome") or "").strip()
                    if email and name:
                        roster[email] = name

    grouped = defaultdict(lambda: {"faltas": 0, "registros": 0, "datas": [], "motivos": []})
    total_absences = 0
    for row in values[header_row + 1:]:
        if not isinstance(row, list):
            continue
        email = str(_cell_value(row, headers, "E-mail do analista", "Email do analista") or "").strip().lower()
        if not email:
            continue
        missed = _is_yes(_cell_value(row, headers, "Faltou"))
        absence = _is_yes(_cell_value(row, headers, "Ausência", "Ausencia"))
        # Uma linha conta no máximo uma falta, mesmo que os dois campos estejam marcados.
        is_absent = missed or absence
        item = grouped[email]
        item["registros"] += 1
        if is_absent:
            item["faltas"] += 1
            total_absences += 1
            day = _cell_value(row, headers, "Data", "Dia previsto?")
            if day:
                item["datas"].append(str(day))
            reason = _cell_value(row, headers, "Observações / motivo", "Observacoes / motivo", "Observações", "Motivo")
            if reason:
                item["motivos"].append(str(reason))

    if not grouped:
        return {"reply": "Não encontrei registros com e-mail de analista na aba ABS Diário.", "sources": []}

    def display_name(email):
        return roster.get(email, f"E-mail sem correspondência no cadastro ({email})")

    ranked = sorted(grouped.items(), key=lambda pair: (pair[1]["faltas"], pair[1]["registros"]), reverse=True)
    asks_person = any(token in question for token in ("analista", "quem", "responsavel", "responsável"))
    asks_total = any(token in question for token in ("total", "geral", "equipe", "todos", "quantas", "quantos"))
    asks_detail = any(token in question for token in ("motivo", "observacao", "observacoes", "detalhe", "data"))
    lines = []
    for email, item in ranked:
        lines.append(f"• {display_name(email)} — {item['faltas']} falta(s) em {item['registros']} registro(s)")
        if asks_detail and item["motivos"]:
            lines.append("  Motivos registrados: " + "; ".join(item["motivos"][:3]))

    if asks_person and not asks_total and ranked:
        target_terms = [t for t in re.findall(r"[a-z0-9]+", question)
                        if len(t) > 2 and t not in {"abs", "quem", "analista", "analistas", "faltou", "faltas", "teve", "tem"}]
        matching = [(email, item) for email, item in ranked
                    if any(t in _normalize_text(display_name(email)) for t in target_terms)]
        if matching:
            email, item = matching[0]
            reply = f"{display_name(email)} tem {item['faltas']} falta(s) em {item['registros']} registro(s) na aba ABS Diário."
            if item["motivos"]:
                reply += " Motivos: " + "; ".join(item["motivos"][:5])
        else:
            reply = "Resumo de ABS por analista:\n" + "\n".join(lines)
    else:
        reply = f"Resumo de ABS Diário: {total_absences} falta(s) em {sum(x['registros'] for x in grouped.values())} registro(s).\n" + "\n".join(lines)

    sheet_id = abs_sheet.get("sheetId", abs_sheet.get("gid"))
    base_url = spreadsheet_url.split("#")[0] if spreadsheet_url else ""
    source_url = f"{base_url}#gid={sheet_id}&range=A{header_row + 1}:F{len(values)}" if base_url and sheet_id is not None else ""
    sources = [{
        "sheetName": abs_sheet.get("name") or abs_sheet.get("sheetName") or "ABS Diário",
        "range": f"A{header_row + 1}:F{len(values)}",
        "label": "ABS Diário — registros utilizados",
        "url": source_url
    }] if source_url else []
    return {"reply": reply, "sources": sources}

def answer_from_sheets(message, sheets, spreadsheet_url=""):
    """Responde com cálculos estruturados e consultas gerais às abas enviadas pelo Apps Script."""
    question = _normalize_text(message).strip()
    if not isinstance(sheets, list) or not sheets:
        return None

    is_sheet_question = any(term in question for term in (
        "planilha", "aba", "nps", "analista", "equipe", "promotor", "detrator",
        "satisfacao", "monitoria", "coach", "abs", "fora do prazo", "fora prazo"
    ))
    is_abs_question = any(term in question for term in (
        "abs", "absenteismo", "absenteismo", "faltas", "faltou", "ausencia", "ausente"
    ))
    if is_abs_question:
        result = _abs_analysis(message, sheets, spreadsheet_url)
        if result is not None:
            return result

    is_nps_question = any(term in question for term in (
        "nps", "promotor", "detrator", "satisfacao"
    ))
    if is_nps_question:
        result = _nps_analysis(message, sheets, spreadsheet_url)
        if result is not None:
            return result

    stop_words = {
        "qual", "quais", "quanto", "quantos", "quantas", "como", "esta",
        "estao", "tem", "tenho", "para", "por", "com", "da", "das", "de",
        "do", "dos", "e", "o", "a", "os", "as", "na", "no", "nas", "nos",
        "equipe", "meu", "minha", "sobre", "mostre", "consulte", "ver"
    }
    terms = [word for word in re.findall(r"[a-z0-9]+", question)
             if len(word) > 2 and word not in stop_words]
    rows_found = []
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
            if matched:
                rows_found.append({
                    "score": len(matched), "sheet": sheet_name,
                    "row": row_index + 1, "cells": nonempty[:12],
                    "sheet_id": sheet_id
                })

    if rows_found:
        rows_found.sort(key=lambda item: item["score"], reverse=True)
        output, sources = [], []
        base_url = spreadsheet_url.split("#")[0] if spreadsheet_url else ""
        for item in rows_found[:5]:
            details = " | ".join(f"{_column_letter(col + 1)}: {value}"
                                 for col, value in item["cells"])
            output.append(f"{item['sheet']} (linha {item['row']}): {details}")
            if base_url and item["sheet_id"] is not None:
                cell = f"A{item['row']}"
                sources.append({
                    "sheetName": item["sheet"], "range": cell,
                    "label": f"{item['sheet']}!{cell}",
                    "url": f"{base_url}#gid={item['sheet_id']}&range={quote(cell, safe='!:')}"
                })
        return {"reply": "Encontrei estas informações nas abas da planilha:\n" + "\n".join(output), "sources": sources}

    if is_sheet_question:
        return {"reply": "Entendi que sua pergunta é sobre a planilha, mas não encontrei dados suficientes para respondê-la. Tente indicar o indicador, analista ou período que deseja consultar.", "sources": []}
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
