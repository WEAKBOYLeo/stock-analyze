"""
HTTP fetching with rate limiting, retries, and polite User-Agent headers.

Usage:
    from lib.fetcher import Fetcher
    f = Fetcher(user_agent="MyResearch/1.0 (contact@example.com)")
    data = f.get_json("https://api.example.com/data")
    html = f.get_text("https://example.com/page")
"""

import time
import json
import requests
from typing import Optional

DEFAULT_UA = "StockResearch/1.0 (research-bot@example.com)"
MIN_DELAY = 0.5  # seconds between requests to same host


class Fetcher:
    def __init__(self, user_agent: str = DEFAULT_UA, log=None):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self._last_request: dict[str, float] = {}  # host -> last request time
        self.log = log

    def _rate_limit(self, host: str):
        """Enforce minimum delay between requests to the same host."""
        now = time.time()
        if host in self._last_request:
            elapsed = now - self._last_request[host]
            if elapsed < MIN_DELAY:
                time.sleep(MIN_DELAY - elapsed)
        self._last_request[host] = time.time()

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make an HTTP request with retry logic."""
        from urllib.parse import urlparse
        host = urlparse(url).hostname or url
        self._rate_limit(host)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = self.session.request(method, url, timeout=30, **kwargs)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 5 * (attempt + 1)))
                    if self.log:
                        self.log.warn(f"429 rate limit on {host}, waiting {wait}s")
                    time.sleep(wait)
                    continue
                if resp.status_code >= 500 and attempt < max_retries - 1:
                    if self.log:
                        self.log.warn(f"5xx from {host}, retry {attempt + 1}/{max_retries}")
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    if self.log:
                        self.log.warn(f"Request failed: {e}, retry {attempt + 1}/{max_retries}")
                    time.sleep(2 ** attempt)
                else:
                    raise

    def get_json(self, url: str, **params) -> dict:
        """GET JSON from an API endpoint."""
        resp = self._request("GET", url, params=params)
        return resp.json()

    def post_json(self, url: str, data: dict = None, **kwargs) -> dict:
        """POST and get JSON response."""
        resp = self._request("POST", url, json=data, **kwargs)
        return resp.json()

    def get_text(self, url: str, **params) -> str:
        """GET plain text / HTML from a URL."""
        resp = self._request("GET", url, params=params)
        return resp.text

    def download(self, url: str, dest_path: str) -> str:
        """Download a file to dest_path. Returns dest_path."""
        resp = self._request("GET", url, stream=True)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        if self.log:
            self.log.info(f"Downloaded → {dest_path}")
        return dest_path

    def close(self):
        self.session.close()


import os
