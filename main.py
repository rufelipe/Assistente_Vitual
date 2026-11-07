"""Relatório local da Assistente Virtual integrado ao Salesforce."""
from datetime import date, datetime
from app import load_tasks


def parse_due(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def mostrar_resumo_diario():
    tarefas = load_tasks()
    hoje = date.today()
    abertas = [t for t in tarefas if str(t.get("status", "")).lower() not in
               ("concluída", "concluida", "completed", "complete", "done")]
    atrasadas = [t for t in abertas if parse_due(t.get("vencimento")) and parse_due(t["vencimento"]) < hoje]
    vencem_hoje = [t for t in abertas if parse_due(t.get("vencimento")) == hoje]
    prioritarias = [t for t in abertas if str(t.get("prioridade", "")).lower() in ("alta", "high", "urgent", "urgente")]
    print("ASSISTENTE VIRTUAL — RESUMO DO DIA")
    print("Data: {}".format(hoje.strftime("%d/%m/%Y")))
    print("Abertas: {} | atrasadas: {} | vencem hoje: {} | prioridade alta: {}".format(
        len(abertas), len(atrasadas), len(vencem_hoje), len(prioritarias)))
    for titulo, lista in (("ATRASADAS", atrasadas), ("VENCEM HOJE", vencem_hoje), ("PRIORIDADE ALTA", prioritarias)):
        print("\n" + titulo)
        for tarefa in lista:
            print("- {} | {} | responsável: {} | prazo: {}".format(
                tarefa.get("cliente"), tarefa.get("titulo"), tarefa.get("responsavel"),
                tarefa.get("vencimento") or "data inválida/ausente"))


if __name__ == "__main__":
    mostrar_resumo_diario()
