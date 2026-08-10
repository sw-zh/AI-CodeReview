"""Bounded, read-only GitHub source client for project facts, not Agent tool evidence."""

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.core.config import Settings
from app.domain.errors import DomainError


_GITHUB_API_BASE_URL = "https://api.github.com"
_MAX_PAGES = 50


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):  # noqa: N802
        return None


@dataclass(frozen=True)
class GitHubSyncPayload:
    issues: list[dict]
    milestones: list[dict]
    truncated: bool


def _safe_api_base_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != "api.github.com" or parsed.path not in {"", "/"}:
        raise DomainError("SOURCE_CONNECTION_INVALID", "GitHub 来源仅允许使用 https://api.github.com")
    return _GITHUB_API_BASE_URL


class GitHubSourceClient:
    def __init__(self, *, repository_slug: str, api_base_url: str, secret_ref: str | None, settings: Settings) -> None:
        self._repository_slug = repository_slug
        self._api_base_url = _safe_api_base_url(api_base_url)
        self._secret_ref = secret_ref
        self._settings = settings

    def fetch(self) -> GitHubSyncPayload:
        issues, issues_truncated = self._list_paginated(f"/repos/{self._repository_slug}/issues", {"state": "all"})
        milestones, milestones_truncated = self._list_paginated(f"/repos/{self._repository_slug}/milestones", {"state": "all"})
        return GitHubSyncPayload(issues=issues, milestones=milestones, truncated=issues_truncated or milestones_truncated)

    def _list_paginated(self, path: str, query: dict[str, str]) -> tuple[list[dict], bool]:
        items: list[dict] = []
        for page in range(1, _MAX_PAGES + 1):
            response = self._get(path, {**query, "per_page": "100", "page": str(page)})
            if not isinstance(response, list):
                raise DomainError("SOURCE_RESPONSE_INVALID", "GitHub 来源返回格式无效")
            if not all(isinstance(item, dict) for item in response):
                raise DomainError("SOURCE_RESPONSE_INVALID", "GitHub 来源包含无效资源")
            items.extend(response)
            if len(response) < 100:
                return items, False
        return items, True

    def _get(self, path: str, query: dict[str, str]) -> object:
        target_url = f"{self._api_base_url}{path}?{urlencode(query)}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "AI-CodeReview-SourceSync/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._secret_ref:
            secret = os.environ.get(self._secret_ref)
            if not secret:
                raise DomainError("SOURCE_SECRET_UNAVAILABLE", "服务端未配置 GitHub 来源所需密钥")
            headers["Authorization"] = f"Bearer {secret}"
        request = Request(target_url, headers=headers, method="GET")
        try:
            with build_opener(_NoRedirect()).open(request, timeout=self._settings.github_sync_timeout_seconds) as response:
                if response.getcode() < 200 or response.getcode() >= 300:
                    raise DomainError("SOURCE_UNAVAILABLE", f"GitHub 来源返回 HTTP {response.getcode()}")
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > self._settings.github_sync_response_limit_bytes:
                    raise DomainError("SOURCE_RESPONSE_TOO_LARGE", "GitHub 来源响应超过允许大小")
                raw = response.read(self._settings.github_sync_response_limit_bytes + 1)
            if len(raw) > self._settings.github_sync_response_limit_bytes:
                raise DomainError("SOURCE_RESPONSE_TOO_LARGE", "GitHub 来源响应超过允许大小")
            return json.loads(raw.decode("utf-8"))
        except DomainError:
            raise
        except UnicodeDecodeError as exc:
            raise DomainError("SOURCE_RESPONSE_INVALID", "GitHub 来源不是 UTF-8 JSON") from exc
        except json.JSONDecodeError as exc:
            raise DomainError("SOURCE_RESPONSE_INVALID", "GitHub 来源不是有效 JSON") from exc
        except HTTPError as exc:
            code = "SOURCE_RATE_LIMITED" if exc.code in {403, 429} else "SOURCE_UNAVAILABLE"
            raise DomainError(code, f"GitHub 来源返回 HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise DomainError("SOURCE_UNAVAILABLE", "GitHub 来源当前不可用") from exc
