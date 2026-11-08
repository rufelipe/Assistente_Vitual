import json
import urllib.request

class CRMRestClient:
    def __init__(self, base_url, access_token="", timeout=15):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.timeout = timeout

    def get_records(self, endpoint):
        url = self.base_url + "/" + endpoint.lstrip("/")
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        if self.access_token:
            request.add_header("Authorization", "Bearer " + self.access_token)

        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("tasks", "notes", "records", "data", "items", "value"):
                if isinstance(payload.get(key), list):
                    return payload[key]
        raise ValueError("A resposta da API do CRM não contém uma lista de registros.")
