from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Locator, Page

from ..browserless_client import BrowserlessPlaywrightClient


@dataclass
class _Element:
    """A thin wrapper around Playwright Locator to provide DP-like methods."""

    locator: Locator

    def click(self) -> None:
        self.locator.click()

    def input(self, text: str, clear: bool = True) -> None:
        if clear:
            self.locator.fill(text)
        else:
            self.locator.type(text)

    def text(self) -> str:
        return self.locator.inner_text()

    def html(self) -> str:
        return self.locator.inner_html()


class DPPage:
    """Minimal DrissionPage-style adapter using Playwright over Browserless.

    This is not a drop-in replacement, but it covers common actions:
    - goto/navigation
    - element selection (css/xpath/text), click, input
    - wait for selectors
    - screenshot/pdf
    """

    def __init__(self, ws_endpoint: Optional[str] = None) -> None:
        self._client = BrowserlessPlaywrightClient(ws_endpoint)
        self._page: Optional[Page] = None

    def __enter__(self) -> "DPPage":
        self._client.start()
        self._page = self._client.new_page()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # Lifecycle
    def close(self) -> None:
        self._client.close()
        self._page = None

    # Navigation
    def get(self, url: str, wait_until: str = "networkidle") -> None:
        page = self._require_page()
        page.goto(url, wait_until=wait_until)

    # Element selection
    def ele(self, selector: str) -> _Element:
        page = self._require_page()
        locator = self._to_locator(page, selector)
        return _Element(locator)

    def wait_ele(self, selector: str, timeout_ms: int = 30000) -> _Element:
        page = self._require_page()
        locator = self._to_locator(page, selector)
        locator.wait_for(state="attached", timeout=timeout_ms)
        return _Element(locator)

    # Page actions
    def click(self, selector: str) -> None:
        self.ele(selector).click()

    def input(self, selector: str, text: str, clear: bool = True) -> None:
        self.ele(selector).input(text, clear=clear)

    # Content
    def text(self, selector: str) -> str:
        return self.ele(selector).text()

    def html(self, selector: str) -> str:
        return self.ele(selector).html()

    # Media
    def screenshot(self, path: str, full_page: bool = True) -> None:
        page = self._require_page()
        page.screenshot(path=path, full_page=full_page)

    def pdf(self, path: str, format: str = "A4") -> None:
        page = self._require_page()
        page.pdf(path=path, format=format)

    # Helpers
    def _require_page(self) -> Page:
        if self._page is None:
            # Late init for non-with usage
            self._client.start()
            self._page = self._client.new_page()
        return self._page

    @staticmethod
    def _to_locator(page: Page, selector: str) -> Locator:
        # Heuristics similar to DP: prefix-based routing
        if selector.startswith("css:"):
            return page.locator(selector[len("css:"):].strip())
        if selector.startswith("xpath:"):
            return page.locator(f"xpath={selector[len("xpath:"):].strip()}")
        if selector.startswith("text:"):
            return page.get_by_text(selector[len("text:"):].strip())
        # Default to CSS
        return page.locator(selector)


__all__ = [
    "DPPage",
]

