"""Visual QA runner for the Streamlit evidence platform.

Starts the local Streamlit app, captures desktop/tablet/mobile screenshots with
Microsoft Edge headless, and writes a manifest under data/runs/.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EDGE_CANDIDATES = [
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]
VIEWPORTS = {
    "desktop": (1440, 1080),
    "tablet": (834, 1194),
    "mobile": (390, 844),
}
REQUIRED_TEXT_ANCHORS = [
    "黑土区水蚀智能预测与证据化评估平台",
    "EVIDENCE PLATFORM",
    "证据化评估工作台",
]
REQUIRED_VISIBLE_SELECTORS = [
    ".command-hero",
    ".gate-board",
    ".result-workbench",
]
FIRST_PAINT_SELECTOR = ".command-hero"


def layout_health_script() -> str:
    return """
    selectors => {
      const viewport = { width: window.innerWidth, height: window.innerHeight };
      const visibleArea = rect => {
        const left = Math.max(0, rect.left);
        const top = Math.max(0, rect.top);
        const right = Math.min(viewport.width, rect.right);
        const bottom = Math.min(viewport.height, rect.bottom);
        return Math.max(0, right - left) * Math.max(0, bottom - top);
      };
      const selectorHealth = {};
      for (const selector of selectors) {
        const node = document.querySelector(selector);
        if (!node) {
          selectorHealth[selector] = { present: false, visible_ratio: 0 };
          continue;
        }
        const rect = node.getBoundingClientRect();
        const area = Math.max(1, rect.width * rect.height);
        selectorHealth[selector] = {
          present: true,
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          visible_ratio: Number((visibleArea(rect) / area).toFixed(4))
        };
      }
      const sidebar = document.querySelector('[data-testid="stSidebar"]');
      let sidebarHealth = { present: false, visible_ratio: 0, viewport_overlap_ratio: 0 };
      if (sidebar) {
        const rect = sidebar.getBoundingClientRect();
        const sidebarArea = Math.max(1, rect.width * rect.height);
        sidebarHealth = {
          present: true,
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          visible_ratio: Number((visibleArea(rect) / sidebarArea).toFixed(4)),
          viewport_overlap_ratio: Number((visibleArea(rect) / Math.max(1, viewport.width * viewport.height)).toFixed(4))
        };
      }
      return {
        viewport,
        selectors: selectorHealth,
        sidebar: sidebarHealth,
        required_selectors_present: selectors.every(selector => selectorHealth[selector]?.present),
        first_paint_visible: !!selectorHealth[".command-hero"] && selectorHealth[".command-hero"].visible_ratio > 0.35,
        sidebar_dominates_viewport: sidebarHealth.viewport_overlap_ratio > 0.45
      };
    }
    """


def force_first_paint_script() -> str:
    return """
    selector => {
      window.scrollTo(0, 0);
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
      for (const node of document.querySelectorAll('*')) {
        if (node.scrollHeight > node.clientHeight || node.scrollWidth > node.clientWidth) {
          node.scrollTop = 0;
          node.scrollLeft = 0;
        }
      }
      const target = document.querySelector(selector);
      if (target) {
        target.scrollIntoView({ block: 'start', inline: 'nearest' });
      }
      window.scrollBy(0, -24);
      return !!target;
    }
    """


def find_browser(explicit: str | None = None) -> Path:
    candidates = [Path(explicit)] if explicit else DEFAULT_EDGE_CANDIDATES
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    raise FileNotFoundError("No Edge/Chrome executable found for headless screenshots.")


def wait_http(url: str, timeout_s: int) -> None:
    deadline = time.time() + timeout_s
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - keep last startup error for manifest/debugging.
            last_error = exc
        time.sleep(1)
    raise TimeoutError(f"Timed out waiting for {url}; last_error={last_error}")


def image_quality(path: Path) -> dict:
    """Return a lightweight blank-screen check for a captured screenshot."""
    try:
        from PIL import Image

        image = Image.open(path).convert("RGB")
        colors = image.getcolors(maxcolors=10_000_000) or []
        total = image.size[0] * image.size[1]
        non_white = 0
        for count, color in colors:
            if color != (255, 255, 255):
                non_white += count
        return {
            "width": image.size[0],
            "height": image.size[1],
            "color_count": len(colors),
            "non_white_ratio": round(non_white / max(total, 1), 6),
            "blank_like": len(colors) <= 3 or non_white / max(total, 1) < 0.01,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}", "blank_like": True}


def capture_with_playwright(url: str, browser_path: Path, out_dir: Path, timeout_s: int) -> tuple[list, list]:
    """Capture screenshots through Playwright so Streamlit JS has time to render."""
    from playwright.sync_api import sync_playwright

    screenshots = []
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=str(browser_path),
            headless=True,
            args=["--disable-gpu", "--no-first-run"],
        )
        try:
            for name, (width, height) in VIEWPORTS.items():
                page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                shot_path = out_dir / f"{name}_{width}x{height}.png"
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)
                    page.wait_for_function(
                        """anchors => anchors.every(anchor => document.body && document.body.innerText.includes(anchor))""",
                        arg=REQUIRED_TEXT_ANCHORS,
                        timeout=timeout_s * 1000,
                    )
                    page.wait_for_timeout(2500)
                    # Streamlit can keep scroll offsets on internal containers,
                    # especially at mobile widths, and may auto-scroll after
                    # initial render. Wait first, then force the hero into the
                    # first paint immediately before measuring and capturing.
                    page.evaluate(force_first_paint_script(), FIRST_PAINT_SELECTOR)
                    page.locator(FIRST_PAINT_SELECTOR).scroll_into_view_if_needed(timeout=timeout_s * 1000)
                    page.wait_for_timeout(300)
                    page.screenshot(path=str(shot_path), full_page=False)
                    quality = image_quality(shot_path)
                    visible_text = page.locator("body").inner_text(timeout=5000)
                    layout_health = page.evaluate(layout_health_script(), REQUIRED_VISIBLE_SELECTORS)
                    anchors_found = {
                        anchor: anchor in visible_text
                        for anchor in REQUIRED_TEXT_ANCHORS
                    }
                    layout_failed = (
                        not layout_health.get("required_selectors_present")
                        or not layout_health.get("first_paint_visible")
                        or layout_health.get("sidebar_dominates_viewport")
                    )
                    if quality.get("blank_like") or layout_failed:
                        errors.append({
                            "viewport": name,
                            "error": "LayoutHealthFailed" if not quality.get("blank_like") else "BlankLikeScreenshot",
                            "quality": quality,
                            "anchors_found": anchors_found,
                            "layout_health": layout_health,
                            "path": str(shot_path),
                        })
                    else:
                        screenshots.append({
                            "viewport": name,
                            "width": width,
                            "height": height,
                            "path": str(shot_path),
                            "bytes": shot_path.stat().st_size,
                            "quality": quality,
                            "anchors_found": anchors_found,
                            "layout_health": layout_health,
                        })
                except Exception as exc:  # noqa: BLE001
                    errors.append({"viewport": name, "error": f"{type(exc).__name__}: {exc}", "path": str(shot_path)})
                finally:
                    page.close()
        finally:
            browser.close()
    return screenshots, errors


def capture_with_edge_cli(url: str, browser_path: Path, out_dir: Path, timeout_s: int) -> tuple[list, list]:
    """Fallback screenshot capture using the browser command line."""
    screenshots = []
    errors = []
    for name, (width, height) in VIEWPORTS.items():
        shot_path = out_dir / f"{name}_{width}x{height}.png"
        user_data = out_dir / f"edge_profile_{name}"
        browser_cmd = [
            str(browser_path),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=12000",
            f"--user-data-dir={user_data}",
            f"--window-size={width},{height}",
            f"--screenshot={shot_path}",
            url,
        ]
        result = subprocess.run(
            browser_cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
        quality = image_quality(shot_path) if shot_path.exists() else {"blank_like": True}
        if result.returncode != 0 or not shot_path.exists() or shot_path.stat().st_size == 0 or quality.get("blank_like"):
            errors.append({
                "viewport": name,
                "returncode": result.returncode,
                "stdout": result.stdout[-1000:],
                "stderr": result.stderr[-1000:],
                "quality": quality,
            })
        else:
            screenshots.append({
                "viewport": name,
                "width": width,
                "height": height,
                "path": str(shot_path),
                "bytes": shot_path.stat().st_size,
                "quality": quality,
            })
    return screenshots, errors


def run_visual_qa(port: int, browser_path: Path, timeout_s: int) -> dict:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "data" / "runs" / f"ui_visual_qa_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = out_dir / "streamlit.stdout.log"
    stderr_path = out_dir / "streamlit.stderr.log"
    url = f"http://127.0.0.1:{port}"

    streamlit_cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.headless=true",
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
    ]

    screenshots = []
    errors = []
    capture_engine = "playwright"
    proc = None
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        try:
            proc = subprocess.Popen(
                streamlit_cmd,
                cwd=str(ROOT),
                stdout=stdout,
                stderr=stderr,
                text=True,
            )
            wait_http(url, timeout_s=timeout_s)
            try:
                screenshots, errors = capture_with_playwright(url, browser_path, out_dir, timeout_s)
            except Exception as exc:  # noqa: BLE001
                capture_engine = "edge_cli"
                errors.append({"engine": "playwright", "error": f"{type(exc).__name__}: {exc}"})
                fallback_screenshots, fallback_errors = capture_with_edge_cli(url, browser_path, out_dir, timeout_s)
                screenshots.extend(fallback_screenshots)
                errors.extend(fallback_errors)
        finally:
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)

    manifest = {
        "status": "ok" if len(screenshots) == len(VIEWPORTS) and not errors else "partial",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "url": url,
        "browser": str(browser_path),
        "capture_engine": capture_engine,
        "streamlit_cmd": streamlit_cmd,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "screenshots": screenshots,
        "errors": errors,
        "claim_boundary": "Screenshots prove page renders at the captured breakpoints; they do not prove native Figma source creation or scientific validity.",
    }
    manifest_path = out_dir / "visual_qa_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture Streamlit UI visual QA screenshots.")
    parser.add_argument("--port", type=int, default=8513)
    parser.add_argument("--browser", default=None, help="Optional Edge/Chrome executable path.")
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args()

    try:
        browser = find_browser(args.browser)
        manifest = run_visual_qa(port=args.port, browser_path=browser, timeout_s=args.timeout)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0 if manifest["status"] == "ok" else 2
    except Exception as exc:  # noqa: BLE001 - CLI should return readable failure.
        print(json.dumps({"status": "error", "error_type": type(exc).__name__, "message": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
