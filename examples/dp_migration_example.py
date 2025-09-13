import os
from pathlib import Path

from adapter import DPPage


def main() -> None:
    # Ensure endpoint/token via env (see README). For local docker-compose, default works.
    ws = os.getenv("BROWSERLESS_WS_URL")

    with DPPage(ws_endpoint=ws) as page:
        page.get("https://example.com")
        title = page.text("css:h1")
        print("Title:", title)
        out = Path(__file__).parent / "shot.png"
        page.screenshot(str(out), full_page=True)
        print("Saved screenshot to:", out)


if __name__ == "__main__":
    main()

