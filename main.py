import json
import os
from datetime import date, datetime, timedelta

from crm_api import CRMRestClient


DEFAULT_CRM_URL = "https://salesforceteste.vercel.app"


def parse_datetime(value, field_name):
    """Converte datas ISO ou no formato DD/MM/AAAA vindas da API."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if not isinstance(value, str) or not value.strip():
        raise ValueError("O campo '{}' está vazio ou não contém uma data válida.".format(field_name))

    value = value.strip()
    formats = (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    )
    for date_format in formats:
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            pass
    raise ValueError("Data inválida no campo '{}': {!r}.".format(field_name, value))


def to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "sim", "yes", " realizado", "realizado")
    return False


def carregar_tarefas():
    base_url = os.environ.get("CRM_API_URL", DEFAULT_CRM_URL)
    endpoint = os.environ.get("CRM_API_ENDPOINT", "/api/tasks")
    field_map_json = os.environ.get("CRM_FIELD_MAP")
    access_token = os.environ.get("CRM_ACCESS_TOKEN", "")
    items_key = os.environ.get("CRM_ITEMS_KEY")

    if field_map_json:
        try:
            field_map = json.loads(field_map_json)
        except ValueError:
            raise ValueError("CRM_FIELD_MAP precisa ser um JSON válido.")
    else:
        # Padrão para APIs que já usam os nomes esperados pelo assistente.
        field_map = {
            "cliente": "cliente",
            "titulo": "titulo",
            "vencimento": "vencimento",
            "prioridade": "prioridade",
            "status": "status",
            "contato_agendado": "contato_agendado",
            "contato_realizado": "contato_realizado",
            "tipo_contato": "tipo_contato",
            "observacao": "observacao",
            "criar_proxima_tarefa": "criar_proxima_tarefa",
        }

        if not isinstance(field_map, dict):
        raise ValueError("CRM_FIELD_MAP precisa ser um objeto JSON de mapeamento.")

    obrigatorios = ("cliente", "titulo", "vencimento", "prioridade", "status")
    ausentes = [nome for nome in obrigatorios if nome not in field_map]
    if ausentes:
        raise ValueError("CRM_FIELD_MAP não mapeia os campos obrigatórios: {}.".format(", ".join(ausentes)))

    client = CRMRestClient(base_url, access_token)
    records = client.get_records(endpoint, items_key or None)
    tarefas = []
    for record in records:
        tarefa = client.normalize_task(record, field_map)
        try:
            tarefa["vencimento"] = parse_datetime(tarefa.get("vencimento"), "vencimento").date()
        except ValueError as error:
            campos = ", ".join(sorted(record.keys())) if isinstance(record, dict) else "indisponíveis"
            raise ValueError("{}. Campos recebidos da API: {}. Ajuste o mapeamento do vencimento.".format(error, campos))

        contato_agendado = tarefa.get("contato_agendado")
        if contato_agendado:
            tarefa["contato_agendado"] = parse_datetime(contato_agendado, "contato_agendado")
        tarefa["contato_realizado"] = to_bool(tarefa.get("contato_realizado"))
        tarefa.setdefault("contato_agendado", None)
        tarefa.setdefault("tipo_contato", "contato")
        tarefa.setdefault("observacao", "")
        tarefa["criar_proxima_tarefa"] = to_bool(tarefa.get("criar_proxima_tarefa"))
        tarefas.append(tarefa)
    return tarefas


def formatar_data(data):
    return data.strftime("%d/%m/%Y")


def tarefas_abertas(tarefas):
    concluidos = ("concluída", "concluida", "completed", "complete", "done")
    return [
        tarefa for tarefa in tarefas
        if str(tarefa.get("status", "")).strip().lower() not in concluidos
    ]


def exibir_lista(titulo, tarefas, detalhe):
    print("\n" + titulo)
    if not tarefas:
        print("  Nenhuma tarefa.")
        return
    for tarefa in tarefas:
        print("  - {} | {} | vence {} | prioridade: {}".format(
            tarefa.get("cliente", "—"), tarefa.get("titulo", "—"),
            formatar_data(tarefa["vencimento"]), tarefa.get("prioridade", "—")
        ))
        if detalhe:
            texto = detalhe(tarefa)
            if texto:
                print("    {}".format(texto))


def mostrar_resumo_diario(tarefas):
    hoje = date.today()
    abertas = tarefas_abertas(tarefas)
    atrasadas = [t for t in abertas if t["vencimento"] < hoje]
    vencem_hoje = [t for t in abertas if t["vencimento"] == hoje]
    proximas = [t for t in abertas if hoje < t["vencimento"] <= hoje + timedelta(days=3)]
    prioritarias = [t for t in abertas if str(t.get("prioridade", "")).lower() == "alta"]
    contatos_pendentes = [
        t for t in abertas
        if t.get("contato_agendado") is not None and not t["contato_realizado"]
    ]

    print("ASSISTENTE DE CRM — RESUMO DO DIA")
    print("Data: {}".format(formatar_data(hoje)))
    print("Tarefas abertas: {} | atrasadas: {} | vencem hoje: {}".format(
        len(abertas), len(atrasadas), len(vencem_hoje)
    ))

    exibir_lista("PRIORIDADES DO DIA", prioritarias, lambda t: t.get("observacao"))
    exibir_lista("TAREFAS ATRASADAS", atrasadas, lambda t: "Atenção: tarefa vencida.")
    exibir_lista("VENCEM HOJE", vencem_hoje, lambda t: "Concluir ou reagendar no CRM.")
    exibir_lista("PRÓXIMOS VENCIMENTOS (3 DIAS)", proximas, lambda t: "Planeje o acompanhamento.")
    exibir_lista(
        "LIGAÇÕES/MENSAGENS AGENDADAS E AINDA NÃO REALIZADAS",
        contatos_pendentes,
        lambda t: "{} agendada para {}.".format(
            str(t.get("tipo_contato", "contato")).capitalize(),
            t["contato_agendado"].strftime("%d/%m/%Y às %H:%M")
        )
    )
    exibir_lista(
        "CONTATOS QUE PRECISAM DE REGISTRO",
        [t for t in abertas if not t["contato_realizado"] and t["vencimento"] <= hoje],
        lambda t: "Contato ainda não marcado como realizado ({}).".format(
            t.get("tipo_contato", "contato")
        )
    )
    exibir_lista(
        "CRIAR PRÓXIMAS TAREFAS",
        [t for t in abertas if t["criar_proxima_tarefa"]],
        lambda t: "Criar uma nova tarefa de acompanhamento no CRM."
    )
    exibir_lista(
        "ANOTAÇÕES IMPORTANTES DOS CLIENTES",
        [t for t in abertas if t.get("observacao")],
        lambda t: t.get("observacao")
    )

    print("\nDados carregados da API configurada. O relatório não altera o CRM.")


if __name__ == "__main__":
    try:
        mostrar_resumo_diario(carregar_tarefas())
    except Exception as error:
        print("Não foi possível carregar as tarefas do CRM: {}".format(error))
