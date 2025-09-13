import os
from contextlib import AbstractContextManager
from typing import Optional

from dotenv import load_dotenv
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright


def _build_ws_endpoint_from_env() -> str:
    """
    Construct the Browserless WebSocket endpoint from environment variables.

    Variables:
    - BROWSERLESS_WS_URL: Full ws(s) endpoint. Ex: ws://localhost:3000?token=ABC
    - BROWSERLESS_URL: Base http(s)/ws(s) URL. Ex: http://localhost:3000 or ws://localhost:3000
    - BROWSERLESS_TOKEN: If provided and not already included, append as token querystring
    """
    load_dotenv()

    explicit_ws = os.getenv("BROWSERLESS_WS_URL")
    if explicit_ws:
        return explicit_ws

    base_url = os.getenv("BROWSERLESS_URL", "ws://localhost:3000")

    # Normalize to ws(s) scheme
    if base_url.startswith("http://"):
        base_url = base_url.replace("http://", "ws://", 1)
    elif base_url.startswith("https://"):
        base_url = base_url.replace("https://", "wss://", 1)

    token = os.getenv("BROWSERLESS_TOKEN")
    if token and "token=" not in base_url:
        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}token={token}"
    return base_url


class BrowserlessPlaywrightClient(AbstractContextManager["BrowserlessPlaywrightClient"]):
    """Synchronous Playwright client that connects to Browserless over CDP.

    Usage:
        with BrowserlessPlaywrightClient() as client:
            page = client.new_page()
            page.goto("https://example.com")
    """

    def __init__(self, ws_endpoint: Optional[str] = None) -> None:
        self.ws_endpoint: str = ws_endpoint or _build_ws_endpoint_from_env()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    def __enter__(self) -> "BrowserlessPlaywrightClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        if self._playwright is not None:
            return
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.connect_over_cdp(self.ws_endpoint)
        # Create a fresh context to mimic isolated sessions
        self._context = self._browser.new_context()

    @property
    def browser(self) -> Browser:
        if self._browser is None:
            raise RuntimeError("BrowserlessPlaywrightClient not started. Call start() or use as context manager.")
        return self._browser

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("Browser context not initialized. Ensure start() has been called.")
        return self._context

    def new_page(self) -> Page:
        return self.context.new_page()

    def close(self) -> None:
        # Close in reverse order
        try:
            if self._context is not None:
                self._context.close()
        finally:
            self._context = None
        try:
            if self._browser is not None:
                self._browser.close()
        finally:
            self._browser = None
        try:
            if self._playwright is not None:
                self._playwright.stop()
        finally:
            self._playwright = None


__all__ = [
    "BrowserlessPlaywrightClient",
    "_build_ws_endpoint_from_env",
]

