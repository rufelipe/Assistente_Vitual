"""Cliente REST básico para buscar dados de um CRM configurável.

Mantenha tokens fora do código e configure o endpoint e os campos conforme
a resposta real da API.
"""
from __future__ import print_function

import json
import urllib.request


class CRMRestClient(object):
    def __init__(self, base_url, access_token, timeout=15):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.timeout = timeout

    def get_records(self, endpoint, items_key=None):
        """Faz GET e retorna uma lista de registros JSON."""
        url = self.base_url + "/" + endpoint.lstrip("/")
        request = urllib.request.Request(url)

        if self.access_token:
            request.add_header("Authorization", "Bearer " + self.access_token)
        request.add_header("Accept", "application/json")

        response = urllib.request.urlopen(request, timeout=self.timeout)
        try:
            payload = json.loads(response.read().decode("utf-8"))
        finally:
            response.close()

        records = payload
        if items_key:
            for key in items_key.split("."):
                records = records[key]
        elif isinstance(records, dict):
            for key in ("tasks", "records", "data", "items", "value"):
                if isinstance(records.get(key), list):
                    records = records[key]
                    break

        if not isinstance(records, list):
            raise ValueError(
                "A resposta da API não contém uma lista. Configure CRM_ITEMS_KEY "
                "com a propriedade que contém os registros."
            )
        return records

    @staticmethod
    def normalize_task(record, field_map):
        """Mapeia campos da API para o formato usado pelo assistente."""
        aliases = {
            "cliente": ("cliente", "client", "customer", "clientName", "customerName"),
            "titulo": ("titulo", "title", "subject", "name"),
            "vencimento": (
                "vencimento", "dueDate", "due_date", "data_vencimento",
                "dataVencimento", "ActivityDate"
            ),
            "prioridade": ("prioridade", "priority"),
            "status": ("status", "state"),
        }

        def get_value(path):
            value = record
            for part in path.split("."):
                if not isinstance(value, dict) or part not in value:
                    return None
                value = value[part]
            return value

        result = {}
        for name, source in field_map.items():
            value = get_value(source)
            if value is None and source == name:
                for alias in aliases.get(name, ()):
                    value = get_value(alias)
                    if value is not None:
                        break
            result[name] = value
        return result
