"""Tiny JSON-over-HTTP client for the local Ollama and Qdrant services."""

import json
import urllib.error
import urllib.request

# Both services run on localhost; never route these calls through a system proxy.
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class ServiceError(RuntimeError):
    """A service was unreachable or answered with an error."""


def request_json(
    method: str,
    url: str,
    body: dict | None = None,
    headers: dict | None = None,
    timeout: float = 60.0,
) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with _opener.open(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        error.close()
        raise ServiceError(f"{method} {url} -> HTTP {error.code}: {detail}") from error
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        raise ServiceError(f"Cannot reach {url} ({error}). Is the stack running? Try: make up") from error
    return json.loads(raw) if raw else {}
