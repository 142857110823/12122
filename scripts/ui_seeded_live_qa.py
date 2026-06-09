"""Run browser-level UI QA with an explicit seeded test state.

This script starts Streamlit with WATER_EROSION_UI_QA_SEED=1. The seed is
marked in the UI and must not be treated as a scientific result.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "data" / "runs"

FORBIDDEN = [
    "\u9879\u76ee\u9a7e\u9a76\u8231",
    "\u8bc1\u636e\u94fe",
    "\u9501\u5b9a\u6a21\u578b",
    "\u5019\u9009\u6a21\u578b",
    "\u95e8\u7981",
    "\u5de5\u4f5c\u6d41",
    "\u6a21\u578b\u6392\u540d",
    "API Key",
    "\u8ba4\u8bc1\u5931\u8d25",
    "Calling st.rerun",
]


def wait_for_http(url: str, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(2)
    raise RuntimeError(f"Streamlit did not respond: {url}")


def assert_clean(page, name: str) -> str:
    body = page.locator("body").inner_text(timeout=60000)
    leaked = [term for term in FORBIDDEN if term in body]
    if leaked:
        raise AssertionError(f"{name} leaked forbidden terms: {leaked}")
    return body


def wait_button(page, label: str) -> None:
    page.get_by_role("button", name=label, exact=True).first.wait_for(timeout=120000)


def click_action_and_wait(page, label: str) -> None:
    page.get_by_role("button", name=label, exact=True).first.click(timeout=30000)
    page.wait_for_selector(f"text=\u754c\u9762\u6d4b\u8bd5\u52a8\u4f5c\u5df2\u54cd\u5e94\uff1a{label}", timeout=60000)


def click_radio_text(page, label: str) -> None:
    page.get_by_text(label, exact=True).first.click(timeout=30000)
    page.wait_for_timeout(1000)


def verify_data_inventory_download(page, out_dir: Path, checks: list[dict]) -> None:
    page.get_by_role("button", name="\u6570\u636e\u5904\u7406").click(timeout=30000)
    page.wait_for_timeout(1200)
    click_radio_text(page, "\u6570\u636e\u6e05\u5355")
    wait_button(page, "\u5bfc\u51fa\u6570\u636e\u6e05\u5355 CSV")
    with page.expect_download(timeout=60000) as download_info:
        page.get_by_role("button", name="\u5bfc\u51fa\u6570\u636e\u6e05\u5355 CSV").first.click(timeout=30000)
    download = download_info.value
    save_path = out_dir / "data_inventory.csv"
    download.save_as(str(save_path))
    text = save_path.read_text(encoding="utf-8-sig")
    required_columns = [
        "file", "variable", "year", "scenario", "path", "size_bytes", "uploaded_at",
        "crs", "width", "height", "resolution_x", "resolution_y", "nodata",
        "valid_pixel_pct", "min", "max", "mean",
    ]
    missing = [col for col in required_columns if col not in text.splitlines()[0]]
    if missing:
        raise AssertionError(f"data_inventory.csv missing columns: {missing}\n{text[:500]}")
    for expected in ["R_2024.tif", "R", "2024", "EPSG:4326", "100.0", "13.5"]:
        if expected not in text:
            raise AssertionError(f"data_inventory.csv missing real metadata value {expected!r}:\n{text[:800]}")
    assert_global_shell(page, "data_inventory")
    assert_clean(page, "data_inventory")
    page.screenshot(path=str(out_dir / "data_inventory.png"), full_page=True)
    checks.append({"layer": "data_inventory", "download": str(save_path), "bytes": save_path.stat().st_size})


def verify_direct_model_build_backend(page, out_dir: Path, checks: list[dict]) -> None:
    page.get_by_role("button", name="\u6a21\u578b\u6784\u5efa").click(timeout=30000)
    page.wait_for_timeout(1200)
    build_button = page.get_by_role("button", name="\u6784\u5efa\u5efa\u6a21\u6570\u636e").first
    build_button.wait_for(timeout=60000)
    if not build_button.is_enabled(timeout=30000):
        raise AssertionError("构建建模数据 button is disabled; it must be open without data-quality gating.")
    build_button.click(timeout=30000)
    page.wait_for_timeout(3000)
    body = page.locator("body").inner_text(timeout=60000)
    if "\u754c\u9762\u6d4b\u8bd5\u52a8\u4f5c\u5df2\u54cd\u5e94\uff1a\u6784\u5efa\u5efa\u6a21\u6570\u636e" in body:
        raise AssertionError("构建建模数据 was intercepted by the fake QA action response.")
    if "No label_YYYY raster found." not in body:
        page.wait_for_timeout(1200)
        body = page.locator("body").inner_text(timeout=60000)
    if "No label_YYYY raster found." not in body:
        raise AssertionError("Direct model build did not expose the expected backend NoLabel error. Body tail:\n" + body[-1500:])
    assert_global_shell(page, "direct_model_build")
    assert_clean(page, "direct_model_build")
    page.screenshot(path=str(out_dir / "direct_model_build_backend_error.png"), full_page=True)
    checks.append({"layer": "direct_model_build", "backend_error": "No label_YYYY raster found."})


def assert_global_shell(page, name: str) -> None:
    body = page.locator("body").inner_text(timeout=60000)
    for text in [
        "\u9996\u9875",
        "\u6570\u636e\u5904\u7406",
        "\u6a21\u578b\u6784\u5efa",
        "\u7ed3\u679c\u89e3\u91ca",
        "\u9884\u6d4b\u5bfc\u51fa",
        "\u6570\u636e\u8f7d\u5165",
        "\u5f53\u524d\u6587\u4ef6\u72b6\u6001",
    ]:
        if text not in body:
            raise AssertionError(f"{name} missing global shell text: {text}")
    sidebar = page.locator('[data-testid="stSidebar"]').first
    sidebar.wait_for(timeout=60000)
    box = sidebar.bounding_box()
    if not box or box.get("width", 0) < 250:
        raise AssertionError(f"{name} sidebar is not expanded/persistent: {box}")


def assert_assistant_is_draggable(page) -> dict:
    panel = page.locator(".st-key-assistant_panel_container").first
    handle = page.locator(".assistant-drag-handle").first
    panel.wait_for(timeout=60000)
    handle.wait_for(timeout=60000)
    panel_text = panel.inner_text(timeout=60000)
    for text in ["\u667a\u80fd\u5c0f\u52a9\u624b", "\u8f93\u5165\u95ee\u9898\u3001\u4ee3\u7801\u4efb\u52a1\u6216\u5e73\u53f0\u64cd\u4f5c\u9700\u6c42", "\u53d1\u9001"]:
        if text not in panel_text:
            raise AssertionError(f"Assistant panel missing text: {text}\n{panel_text}")
    before = panel.bounding_box()
    if not before:
        raise AssertionError("Assistant panel has no bounding box before drag")
    handle_box = handle.bounding_box()
    if not handle_box:
        raise AssertionError("Assistant drag handle has no bounding box")
    start_x = handle_box["x"] + min(24, handle_box["width"] / 2)
    start_y = handle_box["y"] + handle_box["height"] / 2
    page.mouse.move(start_x, start_y)
    page.mouse.down()
    page.mouse.move(start_x - 160, start_y - 90, steps=8)
    page.mouse.up()
    page.wait_for_timeout(500)
    after = panel.bounding_box()
    if not after:
        raise AssertionError("Assistant panel has no bounding box after drag")
    moved = abs(after["x"] - before["x"]) + abs(after["y"] - before["y"])
    if moved < 40:
        raise AssertionError(f"Assistant did not move enough after drag: before={before}, after={after}")
    collapse = panel.get_by_role("button", name="\u6536\u8d77").first
    collapse.click(timeout=30000)
    page.wait_for_timeout(1200)
    page.locator(".st-key-assistant_bubble_container").first.wait_for(timeout=60000)
    return {"before": before, "after": after, "moved_px": moved}


def enter_layer(page, out_dir: Path, checks: list[dict], entry: str, name: str,
                required: list[str] | None = None, radio: str | None = None,
                action_label: str | None = None) -> None:
    page.get_by_role("button", name=entry, exact=True).first.click(timeout=30000)
    page.wait_for_timeout(1200)
    if radio:
        page.get_by_text(radio, exact=True).first.click(timeout=30000)
        page.wait_for_timeout(1000)
    for label in required or []:
        wait_button(page, label)
    if action_label:
        click_action_and_wait(page, action_label)
    assert_global_shell(page, name)
    assert_clean(page, name)
    shot = out_dir / f"{name}.png"
    page.screenshot(path=str(shot), full_page=True)
    buttons = page.locator("button").all_inner_texts()
    checks.append({"layer": name, "screenshot": str(shot), "button_count": len(buttons)})


def run_browser_qa(url: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector("text=\u9ed1\u571f\u6c34\u8680\u9884\u6d4b\u5206\u6790\u5e73\u53f0", timeout=90000)
        for label in ["\u9996\u9875", "\u6570\u636e\u5904\u7406", "\u6a21\u578b\u6784\u5efa", "\u7ed3\u679c\u89e3\u91ca", "\u9884\u6d4b\u5bfc\u51fa", "\u6536\u8d77"]:
            wait_button(page, label)
        home = assert_clean(page, "home")
        if "\u754c\u9762\u6d4b\u8bd5\u72b6\u6001" not in home:
            raise AssertionError("QA seed notice is missing")
        assert_global_shell(page, "home")

        buttons = page.locator("button").all_inner_texts()
        expected_order = [
            "\u9996\u9875",
            "\u6570\u636e\u5904\u7406",
            "\u6a21\u578b\u6784\u5efa",
            "\u7ed3\u679c\u89e3\u91ca",
            "\u9884\u6d4b\u5bfc\u51fa",
        ]
        indexes = [buttons.index(label) for label in expected_order]
        if indexes != sorted(indexes):
            raise AssertionError(f"Top navigation order is not process order: {buttons}")
        assistant_drag = assert_assistant_is_draggable(page)
        page.screenshot(path=str(out_dir / "home.png"), full_page=True)

        verify_data_inventory_download(page, out_dir, checks)

        enter_layer(page, out_dir, checks, "\u6570\u636e\u5904\u7406", "data_quality",
                    ["\u8fd0\u884c\u6570\u636e\u68c0\u67e5"], radio="\u6570\u636e\u68c0\u67e5",
                    action_label="\u8fd0\u884c\u6570\u636e\u68c0\u67e5")
        enter_layer(page, out_dir, checks, "\u6a21\u578b\u6784\u5efa", "model_training",
                    ["\u6784\u5efa\u5efa\u6a21\u6570\u636e", "\u9ed8\u8ba4\u8bad\u7ec3", "\u8d1d\u53f6\u65af\u4f18\u5316", "\u4f18\u5316\u540e\u91cd\u8bad", "\u67e5\u770b\u6a21\u578b\u7ed3\u679c"],
                    action_label="\u9ed8\u8ba4\u8bad\u7ec3")
        enter_layer(page, out_dir, checks, "\u7ed3\u679c\u89e3\u91ca", "explain",
                    ["\u5237\u65b0\u89e3\u91ca\u7ed3\u679c", "\u89e3\u91ca\u5f53\u524d\u7ed3\u679c"],
                    action_label="\u5237\u65b0\u89e3\u91ca\u7ed3\u679c")
        enter_layer(page, out_dir, checks, "\u9884\u6d4b\u5bfc\u51fa", "predict",
                    ["\u751f\u6210\u9884\u6d4b\u5730\u56fe", "\u67e5\u770b\u5730\u56fe", "\u67e5\u770b\u4e0d\u786e\u5b9a\u6027"],
                    radio="\u9884\u6d4b\u5730\u56fe", action_label="\u751f\u6210\u9884\u6d4b\u5730\u56fe")

        page.get_by_role("button", name="\u9884\u6d4b\u5bfc\u51fa").click(timeout=30000)
        page.get_by_text("\u5bfc\u51fa\u7ed3\u679c", exact=True).first.click(timeout=30000)
        page.wait_for_timeout(1000)
        wait_button(page, "\u5bfc\u51fa\u7ed3\u679c")
        wait_button(page, "\u751f\u6210\u62a5\u544a")
        click_action_and_wait(page, "\u5bfc\u51fa\u7ed3\u679c")
        assert_global_shell(page, "export")
        assert_clean(page, "export")
        page.screenshot(path=str(out_dir / "export.png"), full_page=True)

        verify_direct_model_build_backend(page, out_dir, checks)
        browser.close()
    return {"url": url, "out_dir": str(out_dir), "checks": checks, "assistant_drag": assistant_drag, "status": "ok"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8542)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = args.out_dir or RUNS / f"streamlit_seeded_qa_{stamp}"
    out_log = RUNS / f"streamlit_seeded_qa_{stamp}.out.log"
    err_log = RUNS / f"streamlit_seeded_qa_{stamp}.err.log"
    RUNS.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["WATER_EROSION_UI_QA_SEED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.port",
        str(args.port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    with out_log.open("w", encoding="utf-8") as out, err_log.open("w", encoding="utf-8") as err:
        proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=out, stderr=err)
        try:
            url = f"http://127.0.0.1:{args.port}/"
            wait_for_http(url)
            result = run_browser_qa(url, out_dir)
            result["stdout_log"] = str(out_log)
            result["stderr_log"] = str(err_log)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())

