from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import HTTP_TIMEOUT, USER_AGENT
from utils.logging import get_logger

logger = get_logger(__name__)


class ExternalServiceError(RuntimeError):
    """Falha controlada de uma fonte externa."""


@dataclass
class HttpResult:
    content: bytes
    content_type: str
    elapsed_ms: int
    url: str

    def json(self):
        try:
            return json.loads(self.content.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExternalServiceError(f"Resposta JSON inválida de {self.url}") from exc

    def xml(self):
        try:
            return ElementTree.fromstring(self.content)
        except ElementTree.ParseError as exc:
            raise ExternalServiceError(f"Resposta XML inválida de {self.url}") from exc


class GovernmentHttpClient:
    def __init__(self, timeout: float = HTTP_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.7,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, application/xml, text/xml, */*"})

    def get(
        self,
        url: str,
        *,
        params: dict | None = None,
        timeout: float | None = None,
        headers: dict | None = None,
    ) -> HttpResult:
        started = time.perf_counter()
        try:
            response = self.session.get(url, params=params, timeout=timeout or self.timeout, headers=headers)
            elapsed = int((time.perf_counter() - started) * 1000)
            logger.info("source_request status=%s duration_ms=%s url=%s", response.status_code, elapsed, response.url)
            if response.status_code == 404:
                raise ExternalServiceError(f"Recurso não encontrado na fonte oficial: {response.url}")
            response.raise_for_status()
            return HttpResult(response.content, response.headers.get("Content-Type", ""), elapsed, response.url)
        except requests.RequestException as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            logger.warning("source_request_failed duration_ms=%s url=%s error=%s", elapsed, url, type(exc).__name__)
            raise ExternalServiceError(f"Fonte oficial temporariamente indisponível ({url}).") from exc

    def stream_to_file(self, url: str, destination, chunk_size: int = 1024 * 1024) -> None:
        destination = Path(destination)
        partial = destination.with_name(destination.name + ".part")
        try:
            partial.unlink(missing_ok=True)
            with self.session.get(url, stream=True, timeout=(self.timeout, 180)) as response:
                response.raise_for_status()
                with open(partial, "wb") as output:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            output.write(chunk)
            os.replace(partial, destination)
        except (requests.RequestException, OSError) as exc:
            partial.unlink(missing_ok=True)
            raise ExternalServiceError(f"Falha no download oficial ({url}).") from exc


http = GovernmentHttpClient()

