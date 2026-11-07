"""Cliente HTTP para a API pública do protótipo Salesforce."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CRM_API_URL = os.environ.get("CRM_API_URL", "https://salesforceteste.vercel.app")


class CRMRestClient:
    def __init__(self, base_url=CRM_API_URL, access_token="", timeout=20):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.timeout = timeout

    def get_json(self, endpoint):
        url = self.base_url + "/" + endpoint.lstrip("/")
        headers = {"Accept": "application/json", "User-Agent": "Assistente-Virtual/1.0"}
        if self.access_token:
            headers["Authorization"] = "Bearer " + self.access_token
        req = Request(url, headers=headers, method="GET")
        try:
            with urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError("Salesforce respondeu HTTP {} em {}.".format(exc.code, endpoint))
        except URLError as exc:
            raise RuntimeError("Não foi possível acessar o Salesforce: {}.".format(exc.reason))
        except (ValueError, UnicodeDecodeError):
            raise RuntimeError("O endpoint {} não retornou JSON válido.".format(endpoint))

    def get_records(self, endpoint, items_key=None):
        payload = self.get_json(endpoint)
        records = payload
        if items_key:
            for key in items_key.split("."):
                records = records[key]
        elif isinstance(records, dict):
            for key in ("tasks", "notes", "records", "data", "items", "value"):
                if isinstance(records.get(key), list):
                    records = records[key]
                    break
        if not isinstance(records, list):
            raise ValueError("A resposta de {} não contém uma lista JSON.".format(endpoint))
        return records

    @staticmethod
    def normalize_task(record, field_map):
        """Mapeia os campos solicitados sem criar informações ausentes."""
        result = {}
        for target, source in field_map.items():
            value = record
            for part in source.split("."):
                if not isinstance(value, dict) or part not in value:
                    value = None
                    break
                value = value[part]
            result[target] = value
        return result
