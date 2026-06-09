import json
import os
import subprocess
import sys
import unittest
from unittest import mock
from pathlib import Path

from PIL import Image
from streamlit.testing.v1 import AppTest

os.environ.setdefault("WATER_EROSION_DISABLE_DOTENV", "1")

ROOT = Path(__file__).resolve().parent
HANDOFF = ROOT / "docs" / "figma_handoff"
FIGMA_PLUGIN = HANDOFF / "figma_plugin"


class UIDesignAssetsTest(unittest.TestCase):
    def _runtime_text(self, app) -> str:
        fragments = []
        for attr in ["button", "markdown", "metric", "caption", "warning", "info", "success", "text_input", "text_area", "file_uploader", "expander", "radio"]:
            for item in getattr(app, attr, []) or []:
                for field in ["label", "value", "body", "placeholder"]:
                    value = getattr(item, field, None)
                    if value is not None:
                        fragments.append(str(value))
                options = getattr(item, "options", None)
                if options is not None:
                    fragments.extend(str(option) for option in options)
        return "\n".join(fragments)

    def _assert_runtime_text_clean(self, app):
        forbidden = [
            "\u9879\u76ee\u9a7e\u9a76\u8231",
            "\u4e00\u952e\u79d1\u7814\u5de5\u4f5c\u6d41",
            "\u8bc1\u636e\u94fe",
            "\u9501\u5b9a\u6a21\u578b",
            "\u5019\u9009\u6a21\u578b",
            "\u6a21\u578b\u6392\u540d",
            "\u53c2\u6570\u4f18\u5316",
            "\u95e8\u7981",
            "workflow",
            "ranking",
            "API Key",
            "\u8ba4\u8bc1\u5931\u8d25",
        ]
        rendered_text = self._runtime_text(app)
        for term in forbidden:
            self.assertNotIn(term, rendered_text)

    def _assert_source_contains_text(self, source: str, text: str):
        escaped = text.encode("unicode_escape").decode("ascii")
        self.assertTrue(text in source or escaped in source, f"Missing source text: {text}")

    def test_required_handoff_assets_still_exist(self):
        required = [
            ROOT / "docs" / "UI_DESIGN_SYSTEM.md",
            ROOT / "scripts" / "ui_visual_qa.py",
            ROOT / "scripts" / "figma_handoff_audit.py",
            ROOT / "scripts" / "build_figma_handoff_bundle.py",

            ROOT / "scripts" / "start_shared.ps1",
            HANDOFF / "README.md",
            HANDOFF / "design-tokens.json",
            HANDOFF / "component-library.json",
            HANDOFF / "prototype-map.json",
            FIGMA_PLUGIN / "README.md",
            FIGMA_PLUGIN / "manifest.json",
            FIGMA_PLUGIN / "code.js",
        ]
        for path in required:
            self.assertTrue(path.exists(), f"Missing retained asset: {path}")
            self.assertGreater(path.stat().st_size, 100, f"Suspiciously small asset: {path}")



    def test_shared_start_launcher_keeps_network_boundary_explicit(self):

        launcher = (ROOT / "scripts" / "start_shared.ps1").read_text(encoding="utf-8")

        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for expected in [

            "--server.address",

            "0.0.0.0",

            "--browser.serverAddress",

            "DryRun",

            "trusted LAN",

        ]:

            self.assertIn(expected, launcher)

        self.assertNotIn("enableCORS", launcher)

        self.assertNotIn("enableXsrfProtection", launcher)

        self.assertIn(".\\scripts\\start_shared.ps1 -Port 8501", readme)

        self.assertIn("Do not expose the raw Streamlit port", readme)

    def test_source_contract_is_sidebar_navigation_modules(self):
        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        for expected in [
            "def render_home",
            "def render_data_workshop",
            "def render_modeling_lab",
            "def render_explain_studio",
            "def render_predict_export",
            "def render_sidebar",
            "def render_assistant_panel",
            "assistant_chat",
            "retrain_optimized",
            "set_current_model",
            "assistant_panel_container",
            "assistant_bubble_container",
            "assistant-icon-button",
            "smart-assistant-avatar",
            "assistant_user_text",
            "initial_sidebar_state=\"expanded\"",
            "dragReady",
            'key=f"sidebar_nav_{layer_id}"',
            "data_workshop_uploader",
            "reset_session_in_data_workshop",
        ]:
            self.assertIn(expected, app_text)
        self._assert_source_contains_text(app_text, "\u8d1d\u53f6\u65af\u4f18\u5316")
        self._assert_source_contains_text(app_text, "\u4f18\u5316\u540e\u91cd\u8bad")
        self._assert_source_contains_text(app_text, "\u667a\u80fd\u5c0f\u52a9\u624b")
        self.assertIn("_render_model_hyperparameter_controls", app_text)
        self.assertIn("model_param_overrides", app_text)
        self._assert_source_contains_text(app_text, "\u624b\u52a8\u8d85\u53c2\u6570")

        home_block = app_text.split("def render_home():", 1)[1].split("def render_data_workshop():", 1)[0]
        self.assertNotIn("render_results_workbench()", home_block)
        self.assertNotIn("_render_layer_entry_card", home_block)
        self.assertIn("st.chat_input", app_text)
        self.assertNotIn("render_command_center", app_text)
        self.assertNotIn("render_gate_workbench", app_text)
        self.assertNotIn("render_design_system_panel", app_text)
        self.assertNotIn("sidebar_uploader", app_text)
        self.assertNotIn("请先在左侧上传", app_text)

    def test_smart_assistant_is_icon_first_and_chat_only(self):
        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        panel_block = app_text.split("def render_assistant_panel():", 1)[1].split("def _mark_for_rerun():", 1)[0]
        bubble_block = panel_block.split("if not st.session_state.get(\"assistant_open\"):", 1)[1].split("return", 1)[0]
        self.assertIn("assistant-icon-button", panel_block)
        self.assertIn("assistant-drag-handle", panel_block)
        self.assertIn("assistant-bubble-avatar", app_text)
        self.assertIn("_assistant_bubble_avatar_html", bubble_block)
        self.assertNotIn("st.image", bubble_block)
        self.assertIn("assistant_bubble_button", panel_block)
        self.assertIn("assistant_user_text", panel_block)
        self.assertIn("st.chat_input", panel_block)
        self.assertIn("assistant_pending_text", app_text)
        self.assertNotIn('disabled=not bool(str(prompt or "").strip())', panel_block)
        self.assertNotIn("form_submit_button", panel_block)
        self.assertIn("assistant_close_icon_button", panel_block)
        self.assertNotIn("_assistant_status_message()", panel_block)
        self.assertNotIn("_assistant_actions()", panel_block)
        self.assertNotIn("assistant_action_", panel_block)
        for clutter in ["阻断原因", "当前无阻断项", "建议下一步", "拖动智能小助手", "可调整大小"]:
            escaped = clutter.encode("unicode_escape").decode("ascii")
            self.assertNotIn(clutter, panel_block)
            self.assertNotIn(escaped, panel_block)
        self.assertNotIn("resize: both", app_text)

    def test_llm_contract_allows_openai_backend_without_frontend_secrets(self):
        agent_text = (ROOT / "agent.py").read_text(encoding="utf-8")
        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        llm_toml = (ROOT / "config" / "llm.toml").read_text(encoding="utf-8")
        req_text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        combined = "\n".join([agent_text, app_text, llm_toml, req_text, readme])
        for expected in [
            "LLM_BACKEND",
            "LLM_LOCAL_MODEL_PATH",
            "LLM_DEVICE",
            "LLM_DTYPE",
            "LLM_MAX_NEW_TOKENS",
            "LLM_TEMPERATURE",
            "transformers",
            "LOCAL_MODEL_NOT_CONFIGURED",
            "LOCAL_MODEL_LOAD_FAILED",
            "LOCAL_INFERENCE_UNAVAILABLE",
            "OpenAIResponsesBackend",
            "OPENAI_API_KEY",
            "OPENAI_MODEL",
            "gpt-5.5",
            "client.responses.create",
        ]:
            self.assertIn(expected, combined)
        for forbidden in [
            "LLM_BASE_URL",
            "siliconflow",
            "chat.completions",
            "requests.post",
            "anthropic",
            "google.generativeai",
        ]:
            self.assertNotIn(forbidden, combined)
        self.assertNotRegex(combined, r"sk-[A-Za-z0-9]{10,}")
        self.assertNotIn("OPENAI_API_KEY", app_text)
        self.assertNotIn("api_key", app_text.lower())

    def test_ui_tests_do_not_read_dotenv(self):
        test_text = (ROOT / "test_ui_design_assets.py").read_text(encoding="utf-8")
        forbidden = "(ROOT / " + '".env").read_text'
        self.assertNotIn(forbidden, test_text)
        self.assertEqual(os.environ.get("WATER_EROSION_DISABLE_DOTENV"), "1")
        check = (
            "import os, sys, types\n"
            "os.environ['WATER_EROSION_DISABLE_DOTENV'] = '1'\n"
            "calls = []\n"
            "dotenv = types.ModuleType('dotenv')\n"
            "def load_dotenv(path):\n"
            "    calls.append(path)\n"
            "    raise RuntimeError('dotenv should be disabled during tests')\n"
            "dotenv.load_dotenv = load_dotenv\n"
            "sys.modules['dotenv'] = dotenv\n"
            "import agent\n"
            "assert calls == [], calls\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", check],
            cwd=ROOT,
            env={**os.environ, "WATER_EROSION_DISABLE_DOTENV": "1"},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_local_llm_settings_are_safe_for_invalid_config(self):
        import agent

        keys = ["LLM_MAX_NEW_TOKENS", "LLM_TEMPERATURE"]
        old_values = {key: os.environ.get(key) for key in keys}
        try:
            os.environ["LLM_MAX_NEW_TOKENS"] = "not-an-int"
            os.environ["LLM_TEMPERATURE"] = "not-a-float"
            settings = agent._load_llm_settings()
            self.assertEqual(settings.max_new_tokens, 512)
            self.assertEqual(settings.temperature, 0.3)
            self.assertIs(settings.trust_remote_code, False)
        finally:
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_openai_timeout_default_is_shorter_than_assistant_ui_timeout(self):
        import agent

        old_timeout = os.environ.pop("OPENAI_TIMEOUT_SECONDS", None)
        try:
            settings = agent._load_llm_settings()
            self.assertLess(settings.openai_timeout_seconds, 8.0)
            self.assertLess(agent.LocalLLMSettings().openai_timeout_seconds, 8.0)
        finally:
            if old_timeout is not None:
                os.environ["OPENAI_TIMEOUT_SECONDS"] = old_timeout

    def test_smart_assistant_has_non_empty_local_fallback(self):
        import agent

        avatar_path = ROOT / "assets" / "smart_assistant_avatar.png"
        self.assertTrue(avatar_path.exists())
        self.assertGreater(avatar_path.stat().st_size, 10000)

        assistant = agent.Agent()
        assistant.settings = agent.LocalLLMSettings()
        assistant.backend = agent.LocalTransformersBackend(assistant.settings)
        response = assistant.respond(
            "下一步应该做什么？",
            {
                "uploads": {},
                "feature_table": None,
                "models": {},
                "best_model": None,
                "predictions": None,
                "workflow_stage": "idle",
            },
        )
        self.assertIn("智能小助手", response["text"])
        self.assertIn("下一步", response["text"])
        self.assertIsNone(response["error"])

    def test_assistant_timeout_attempts_to_cancel_background_future(self):
        import app as streamlit_app

        class FakeFuture:
            def __init__(self):
                self.cancel_called = False

            def result(self, timeout=None):
                raise streamlit_app.FuturesTimeoutError()

            def cancel(self):
                self.cancel_called = True
                return True

        class FakeExecutor:
            def __init__(self):
                self.future = FakeFuture()

            def submit(self, *args, **kwargs):
                return self.future

        fake_executor = FakeExecutor()
        old_executor = streamlit_app._ASSISTANT_RESPOND_EXECUTOR
        old_session_agent = streamlit_app._session_agent
        old_snapshot = streamlit_app._current_state_snapshot
        try:
            streamlit_app._ASSISTANT_RESPOND_EXECUTOR = fake_executor
            streamlit_app._session_agent = lambda: type(
                "Assistant",
                (),
                {"respond": lambda self, user_text, state: {"text": "late"}},
            )()
            streamlit_app._current_state_snapshot = lambda: {"workflow_stage": "data"}

            response = streamlit_app._assistant_respond_with_timeout("测试超时", timeout_seconds=0.01)

            self.assertTrue(fake_executor.future.cancel_called)
            self.assertIn("助手响应超时", response["text"])
        finally:
            streamlit_app._ASSISTANT_RESPOND_EXECUTOR = old_executor
            streamlit_app._session_agent = old_session_agent
            streamlit_app._current_state_snapshot = old_snapshot

    def test_smart_assistant_avatar_uses_transparent_background(self):
        avatar_path = ROOT / "assets" / "smart_assistant_avatar.png"
        with Image.open(avatar_path) as img:
            self.assertEqual(img.mode, "RGBA")
            corners = [
                img.getpixel((0, 0)),
                img.getpixel((img.width - 1, 0)),
                img.getpixel((0, img.height - 1)),
                img.getpixel((img.width - 1, img.height - 1)),
            ]
            self.assertTrue(all(pixel[3] == 0 for pixel in corners))

    def test_smart_assistant_input_is_horizontal_and_sends_message(self):
        cwd = os.getcwd()
        try:
            os.chdir(ROOT)
            app = AppTest.from_file("app.py")
            app.run(timeout=120)
            {b.label: b for b in app.button}["打开智能小助手"].click()
            app.run(timeout=120)
            self.assertEqual(len(app.text_area), 0)
            chat_input = next(item for item in app.chat_input if item.key == "assistant_user_text")
            chat_input.set_value("下一步怎么做？")
            app.run(timeout=120)
            messages = app.session_state["messages"]
            self.assertTrue(any(msg.get("role") == "user" and "下一步怎么做" in msg.get("content", "") for msg in messages))
            self.assertTrue(any(msg.get("role") == "assistant" and "智能小助手" in msg.get("content", "") for msg in messages))
        finally:
            os.chdir(cwd)

    def test_assistant_bubble_click_target_is_not_blocked_by_drag_script(self):
        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("opacity: 0 !important", app_text)
        self.assertNotIn("makeDraggable(bubble, bubble", app_text)
        self.assertIn(".st-key-assistant_bubble_container [data-testid=\"stButton\"]", app_text)
        bubble_block = app_text.split(".st-key-assistant_panel_container", 1)[0].split(".st-key-assistant_bubble_container", 1)[1]
        self.assertIn("position: absolute;", bubble_block)
        self.assertIn("inset: 0;", bubble_block)
        self.assertIn("height: 74px !important;", bubble_block)

    def test_openai_backend_without_key_falls_back_without_leaking_secret(self):
        import agent

        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            assistant = agent.Agent()
            assistant.settings = agent.LocalLLMSettings(backend="openai", openai_model="gpt-5.5")
            assistant.backend = agent.OpenAIResponsesBackend(assistant.settings)
            response = assistant.respond(
                "请解释当前状态",
                {
                    "uploads": {},
                    "feature_table": None,
                    "models": {},
                    "best_model": None,
                    "predictions": None,
                    "workflow_stage": "idle",
                },
            )
        finally:
            if old_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old_key

        self.assertIn("智能小助手", response["text"])
        self.assertIn("下一步", response["text"])
        self.assertIsNone(response["error"])
        self.assertNotRegex(response["text"], r"sk-[A-Za-z0-9]{10,}")

    def test_external_llm_prompt_is_redacted_by_default_when_key_is_available(self):
        import agent

        calls = []

        class FakeResponse:
            output_text = "ChatGPT 模拟回复：已收到脱敏摘要。"

        class FakeResponses:
            def create(self, **kwargs):
                calls.append(kwargs)
                return FakeResponse()

        class FakeClient:
            def __init__(self, **kwargs):
                self.responses = FakeResponses()

        fake_openai_module = type("FakeOpenAI", (), {"OpenAI": FakeClient})
        old_values = {key: os.environ.get(key) for key in ["OPENAI_API_KEY", "ALLOW_EXTERNAL_LLM"]}
        try:
            os.environ["OPENAI_API_KEY"] = "unit-test-key"
            os.environ.pop("ALLOW_EXTERNAL_LLM", None)
            assistant = agent.Agent()
            assistant.settings = agent.LocalLLMSettings(backend="openai")
            assistant.backend = agent.OpenAIResponsesBackend(assistant.settings)
            with mock.patch.object(agent.importlib, "import_module", return_value=fake_openai_module):
                response = assistant.respond(
                    "请解释 D:\\secret\\R_2024.tif，密钥 sk-abcdefghijklmnopqrstuvwxyz",
                    {
                        "uploads": {"R": {"filepath": "D:\\secret\\R_2024.tif"}},
                        "feature_table": {"path": "D:\\secret\\feature_table.parquet"},
                        "models": {},
                        "best_model": None,
                        "predictions": None,
                        "workflow_stage": "data",
                    },
                )
        finally:
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(calls, [])
        self.assertIn("智能小助手", response["text"])
        self.assertIsNone(response["error"])
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz", response["text"])
        self.assertNotIn("D:\\secret", response["text"])
        self.assertIn("[REDACTED_SECRET]", response["text"])
        self.assertIn("[REDACTED_PATH]", response["text"])

    def test_external_llm_prompt_is_redacted_when_explicitly_allowed(self):
        import agent

        calls = []

        class FakeResponse:
            output_text = "ChatGPT 模拟回复：已收到脱敏摘要。"

        class FakeResponses:
            def create(self, **kwargs):
                calls.append(kwargs)
                return FakeResponse()

        class FakeClient:
            def __init__(self, **kwargs):
                self.responses = FakeResponses()

        fake_openai_module = type("FakeOpenAI", (), {"OpenAI": FakeClient})
        old_values = {key: os.environ.get(key) for key in ["OPENAI_API_KEY", "ALLOW_EXTERNAL_LLM"]}
        try:
            os.environ["OPENAI_API_KEY"] = "unit-test-key"
            os.environ["ALLOW_EXTERNAL_LLM"] = "true"
            assistant = agent.Agent()
            assistant.settings = agent.LocalLLMSettings(
                backend="openai",
                openai_model="gpt-5.5",
                openai_max_output_tokens=256,
                allow_external_llm=True,
            )
            assistant.backend = agent.OpenAIResponsesBackend(assistant.settings)
            with mock.patch.object(agent.importlib, "import_module", return_value=fake_openai_module):
                response = assistant.respond(
                    "请解释 D:\\secret\\R_2024.tif，密钥 sk-abcdefghijklmnopqrstuvwxyz",
                    {"workflow_stage": "data"},
                )
        finally:
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(response["text"], "ChatGPT 模拟回复：已收到脱敏摘要。")
        prompt = calls[0]["input"]
        self.assertNotIn("D:\\secret", prompt)
        self.assertNotIn("R_2024.tif", prompt)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz", prompt)
        self.assertIn("[REDACTED_PATH]", prompt)
        self.assertIn("[REDACTED_SECRET]", prompt)

    def test_external_llm_prompt_includes_metadata_only_platform_state(self):
        import agent

        calls = []

        class FakeResponse:
            output_text = "ChatGPT 模拟回复：已结合平台状态。"

        class FakeResponses:
            def create(self, **kwargs):
                calls.append(kwargs)
                return FakeResponse()

        class FakeClient:
            def __init__(self, **kwargs):
                self.responses = FakeResponses()

        fake_openai_module = type("FakeOpenAI", (), {"OpenAI": FakeClient})
        old_values = {key: os.environ.get(key) for key in ["OPENAI_API_KEY", "ALLOW_EXTERNAL_LLM"]}
        try:
            os.environ["OPENAI_API_KEY"] = "unit-test-key"
            os.environ["ALLOW_EXTERNAL_LLM"] = "true"
            assistant = agent.Agent()
            assistant.settings = agent.LocalLLMSettings(
                backend="openai",
                openai_model="gpt-5.5",
                allow_external_llm=True,
            )
            assistant.backend = agent.OpenAIResponsesBackend(assistant.settings)
            with mock.patch.object(agent.importlib, "import_module", return_value=fake_openai_module):
                response = assistant.respond(
                    "当前可以做什么？",
                    {
                        "uploads": {
                            "R_2024.tif": {"filepath": "D:\\secret\\R_2024.tif", "size": 123},
                            "K_2024.tif": {"filepath": "D:\\secret\\K_2024.tif", "size": 456},
                        },
                        "feature_table": {"path": "D:\\secret\\feature_table.parquet", "n_samples": 88},
                        "models": {
                            "random_forest": {"metrics": {"r2": 0.8}},
                            "xgboost": {"metrics": {"r2": 0.7}},
                        },
                        "best_model": "random_forest",
                        "predictions": {"scenario": "ssp245", "path": "D:\\secret\\pred.npy"},
                        "_quality_report": {"gate_verdict": "PASS_WITH_RISKS"},
                        "run_context": {
                            "run_id": "run_20260609_secret",
                            "evidence_paths": [
                                "D:\\secret\\best_model.joblib",
                                "D:\\secret\\report.md",
                            ],
                        },
                        "_explanation_meta": {"explanation_mode": "proxy", "shap_ready": False},
                        "workflow_stage": "models_optimized",
                    },
                )
        finally:
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(response["text"], "ChatGPT 模拟回复：已结合平台状态。")
        prompt = calls[0]["input"]
        for expected in [
            "Platform state summary",
            "workflow_stage=models_optimized",
            "uploads_count=2",
            "feature_table_ready=True",
            "models_count=2",
            "best_model=random_forest",
            "predictions_ready=True",
            "quality_gate=PASS_WITH_RISKS",
            "evidence_count=2",
            "explanation_mode=proxy",
            "shap_ready=False",
        ]:
            self.assertIn(expected, prompt)
        for forbidden in [
            "D:\\secret",
            "R_2024.tif",
            "K_2024.tif",
            "feature_table.parquet",
            "best_model.joblib",
            "report.md",
            "run_20260609_secret",
        ]:
            self.assertNotIn(forbidden, prompt)

    def test_openai_backend_uses_responses_api_when_key_is_available(self):
        import agent

        calls = []

        class FakeResponse:
            output_text = "ChatGPT 模拟回复：可以继续数据处理。"

        class FakeResponses:
            def create(self, **kwargs):
                calls.append(kwargs)
                return FakeResponse()

        class FakeClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.responses = FakeResponses()

        fake_openai_module = type("FakeOpenAI", (), {"OpenAI": FakeClient})
        old_key = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ["OPENAI_API_KEY"] = "unit-test-key"
            assistant = agent.Agent()
            assistant.settings = agent.LocalLLMSettings(
                backend="openai",
                openai_model="gpt-5.5",
                openai_max_output_tokens=256,
                allow_external_llm=True,
            )
            assistant.backend = agent.OpenAIResponsesBackend(assistant.settings)
            with mock.patch.object(agent.importlib, "import_module", return_value=fake_openai_module):
                response = assistant.respond(
                    "请解释当前状态",
                    {
                        "uploads": {"R": "R_2024.tif"},
                        "feature_table": None,
                        "models": {},
                        "best_model": None,
                        "predictions": None,
                        "workflow_stage": "data",
                    },
                )
        finally:
            if old_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old_key

        self.assertEqual(response["text"], "ChatGPT 模拟回复：可以继续数据处理。")
        self.assertIsNone(response["error"])
        self.assertEqual(calls[0]["model"], "gpt-5.5")
        self.assertEqual(calls[0]["max_output_tokens"], 256)
        self.assertIn("请解释当前状态", calls[0]["input"])
        self.assertEqual(assistant.conversation_history[-1]["content"], response["text"])

    def test_security_controls_do_not_add_frontend_mode_badges(self):
        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        for forbidden in ["科研敏感模式", "DATA_SECURITY_MODE", "ALLOW_EXTERNAL_LLM", "ASSISTANT_CONTEXT_POLICY"]:
            self.assertNotIn(forbidden, app_text)

    def test_component_library_and_tokens_are_retained(self):
        tokens = json.loads((HANDOFF / "design-tokens.json").read_text(encoding="utf-8-sig"))
        components = json.loads((HANDOFF / "component-library.json").read_text(encoding="utf-8-sig"))
        self.assertIn("color", tokens)
        self.assertIn("motion", tokens)
        names = {item["name"] for item in components["components"]}
        self.assertIn("ResultWorkbench", names)
        self.assertIn("OptionAction", names)

    def test_empty_home_runtime_contract(self):
        cwd = os.getcwd()
        try:
            os.chdir(ROOT)
            os.environ.pop("WATER_EROSION_UI_QA_SEED", None)
            app = AppTest.from_file("app.py")
            app.run(timeout=120)
            button_map = {b.label: b for b in app.button}
            for label in ["\u9996\u9875", "\u6570\u636e\u5904\u7406", "\u6a21\u578b\u6784\u5efa", "\u7ed3\u679c\u89e3\u91ca", "\u9884\u6d4b\u5bfc\u51fa", "\u6253\u5f00\u667a\u80fd\u5c0f\u52a9\u624b"]:
                self.assertIn(label, button_map)
            self.assertNotIn("\u6536\u8d77", button_map)
            self.assertNotIn("\u53d1\u9001", button_map)
            self.assertFalse(button_map["\u6a21\u578b\u6784\u5efa"].disabled)
            self.assertFalse(button_map["\u7ed3\u679c\u89e3\u91ca"].disabled)
            self.assertFalse(button_map["\u9884\u6d4b\u5bfc\u51fa"].disabled)
            rendered = self._runtime_text(app)
            self.assertIn("\u9ed1\u571f\u533a\u6c34\u8680\u667a\u80fd\u9884\u6d4b\u4e0e\u8bc1\u636e\u5316\u8bc4\u4f30\u5e73\u53f0", rendered)
            self.assertIn("\u9996\u9875\u8bbe\u8ba1\u57fa\u7ebf", rendered)
            self.assertIn("\u7814\u7a76\u805a\u7126", rendered)
            self.assertIn("\u4e94\u56e0\u5b50\u4f53\u7cfb", rendered)
            self.assertIn("\u9996\u9875\u7684\u4fe1\u606f\u5bc6\u5ea6\u6765\u81ea\u7814\u7a76\u8ba4\u77e5\u7ed3\u6784", rendered)
            self.assertIn("\u9ed1\u571f\u533a\u6c34\u8680\u5177\u6709\u660e\u663e\u7684\u5730\u5f62\u5dee\u5f02", rendered)
            self.assertIn("\u542f\u822a\u9875", rendered)
            self.assertNotIn("\u4e1a\u52a1\u5c42", rendered)
            self.assertEqual(len(app.chat_input), 0)
            self._assert_runtime_text_clean(app)
        finally:
            os.chdir(cwd)

    def test_sidebar_navigation_enters_independent_modules(self):
        cwd = os.getcwd()
        try:
            os.chdir(ROOT)
            app = AppTest.from_file("app.py")
            app.run(timeout=120)
            button_map = {b.label: b for b in app.button}
            button_map["\u6a21\u578b\u6784\u5efa"].click()
            app.run(timeout=120)
            self.assertEqual(app.session_state["current_layer"], "modelingLab")
            rendered = self._runtime_text(app)
            self.assertIn("\u6a21\u578b\u6784\u5efa", rendered)
            self.assertNotIn("\u8bf7\u5148\u5b8c\u6210\u6570\u636e\u8d28\u91cf\u68c0\u67e5", rendered)
            button_map = {b.label: b for b in app.button}
            self.assertIn("\u9996\u9875", button_map)
            self.assertIn("\u6784\u5efa\u5efa\u6a21\u6570\u636e", button_map)
            self.assertFalse(button_map["\u6784\u5efa\u5efa\u6a21\u6570\u636e"].disabled)
            self.assertIn("\u67e5\u770b\u6a21\u578b\u7ed3\u679c", button_map)
            button_map["\u6570\u636e\u5904\u7406"].click()
            app.run(timeout=120)
            self.assertEqual(app.session_state["current_layer"], "dataWorkshop")
            rendered = self._runtime_text(app)
            self.assertIn("\u4e0a\u4f20\u6570\u636e", rendered)
            self.assertIn("\u5f53\u524d\u6587\u4ef6\u72b6\u6001", rendered)
            self.assertIn("\u4f1a\u8bdd\u7ba1\u7406", rendered)
            self._assert_runtime_text_clean(app)
        finally:
            os.chdir(cwd)

    def test_data_workshop_contains_real_upload_workspace(self):
        cwd = os.getcwd()
        try:
            os.chdir(ROOT)
            app = AppTest.from_file("app.py")
            app.run(timeout=120)
            button_map = {b.label: b for b in app.button}
            button_map["\u6570\u636e\u5904\u7406"].click()
            app.run(timeout=120)
            rendered = self._runtime_text(app)
            self.assertIn("\u4e0a\u4f20\u6570\u636e", rendered)
            self.assertIn("GeoTIFF", rendered)
            self.assertIn("\u5237\u65b0\u8bc6\u522b\u7ed3\u679c", rendered)
            self.assertIn("\u91cd\u7f6e\u4f1a\u8bdd", rendered)
            self.assertIn("\u6587\u4ef6\u547d\u540d\u8bf4\u660e", rendered)
            self.assertNotIn("\u8bf7\u5148\u5728\u5de6\u4fa7\u4fa7\u8fb9\u680f", rendered)
            self._assert_runtime_text_clean(app)
        finally:
            os.chdir(cwd)

    def test_seeded_data_inventory_uses_real_raster_metadata(self):
        cwd = os.getcwd()
        old_seed = os.environ.get("WATER_EROSION_UI_QA_SEED")
        try:
            os.chdir(ROOT)
            os.environ["WATER_EROSION_UI_QA_SEED"] = "1"
            app = AppTest.from_file("app.py")
            app.run(timeout=120)
            button_map = {b.label: b for b in app.button}
            button_map["\u6570\u636e\u5904\u7406"].click()
            app.run(timeout=120)
            radio = next(r for r in app.radio if r.label == "\u5206\u533a")
            self.assertIn("\u6570\u636e\u6e05\u5355", list(radio.options))
            radio.set_value("\u6570\u636e\u6e05\u5355")
            app.run(timeout=120)
            inventory = app.session_state["_upload_inventory"]
            self.assertEqual(inventory["status"], "ok")
            self.assertGreaterEqual(inventory["total_files"], 1)
            row = inventory["rows"][0]
            for field in [
                "file", "variable", "year", "path", "size_bytes", "uploaded_at",
                "crs", "width", "height", "resolution_x", "resolution_y", "nodata",
                "valid_pixel_pct", "min", "max", "mean", "read_status",
            ]:
                self.assertIn(field, row)
            self.assertEqual(row["file"], "R_2024.tif")
            self.assertEqual(row["variable"], "R")
            self.assertEqual(row["year"], "2024")
            self.assertEqual(row["read_status"], "ok")
            self.assertEqual(row["width"], 2)
            self.assertEqual(row["height"], 2)
            app_text = (ROOT / "app.py").read_text(encoding="utf-8")
            self.assertIn("st.download_button", app_text)
            self.assertIn("data_inventory.csv", app_text)
            self.assertIn("download_data_inventory", app_text)
            self._assert_runtime_text_clean(app)
        finally:
            if old_seed is None:
                os.environ.pop("WATER_EROSION_UI_QA_SEED", None)
            else:
                os.environ["WATER_EROSION_UI_QA_SEED"] = old_seed
            os.chdir(cwd)

    def test_assistant_is_upper_local_dialogue_layer(self):
        cwd = os.getcwd()
        try:
            os.chdir(ROOT)
            app = AppTest.from_file("app.py")
            app.run(timeout=120)
            button_map = {b.label: b for b in app.button}
            self.assertIn("\u6253\u5f00\u667a\u80fd\u5c0f\u52a9\u624b", button_map)
            self.assertNotIn("\u6536\u8d77", button_map)
            rendered = self._runtime_text(app)
            self.assertNotIn("\u4e0a\u5c42\u60ac\u6d6e", rendered)
            button_map["\u6253\u5f00\u667a\u80fd\u5c0f\u52a9\u624b"].click().run(timeout=120)
            opened_buttons = {b.label: b for b in app.button}
            opened_text = self._runtime_text(app)
            self.assertIn("\u6536\u8d77", opened_buttons)
            chat_inputs = [item for item in app.chat_input if item.key == "assistant_user_text"]
            self.assertTrue(chat_inputs)
            self.assertIn("\u667a\u80fd\u5c0f\u52a9\u624b", opened_text)
            self.assertEqual(chat_inputs[0].placeholder, "\u8f93\u5165\u95ee\u9898\u3001\u4ee3\u7801\u4efb\u52a1\u6216\u5e73\u53f0\u64cd\u4f5c\u9700\u6c42")
            app_text = (ROOT / "app.py").read_text(encoding="utf-8")
            self.assertIn("position: fixed", app_text)
            self.assertIn("assistant-icon-button", app_text)
            self.assertIn("localStorage.setItem", app_text)
            self._assert_runtime_text_clean(app)
        finally:
            os.chdir(cwd)

    def test_seeded_state_unlocks_all_modules_and_actions(self):
        cwd = os.getcwd()
        old_seed = os.environ.get("WATER_EROSION_UI_QA_SEED")
        try:
            os.chdir(ROOT)
            os.environ["WATER_EROSION_UI_QA_SEED"] = "1"
            app = AppTest.from_file("app.py")
            app.run(timeout=120)
            button_map = {b.label: b for b in app.button}
            for label in ["\u6570\u636e\u5904\u7406", "\u6a21\u578b\u6784\u5efa", "\u7ed3\u679c\u89e3\u91ca", "\u9884\u6d4b\u5bfc\u51fa"]:
                self.assertIn(label, button_map)
                self.assertFalse(button_map[label].disabled)
            button_map["\u6a21\u578b\u6784\u5efa"].click()
            app.run(timeout=120)
            button_map = {b.label: b for b in app.button}
            self.assertIn("\u6784\u5efa\u5efa\u6a21\u6570\u636e", button_map)
            self.assertIn("\u9ed8\u8ba4\u8bad\u7ec3", button_map)
            self.assertIn("\u8d1d\u53f6\u65af\u4f18\u5316", button_map)
            self.assertIn("\u4f18\u5316\u540e\u91cd\u8bad", button_map)
            self.assertIn("\u67e5\u770b\u6a21\u578b\u7ed3\u679c", button_map)
            rendered = self._runtime_text(app)
            self.assertIn("\u5efa\u6a21\u6570\u636e\u51c6\u5907", rendered)
            self.assertIn("\u8bad\u7ec3\u65b9\u6848", rendered)
            self.assertIn("\u6a21\u578b\u7ed3\u679c", rendered)
            self.assertIn("\u9ed8\u8ba4\u8bad\u7ec3", rendered)
            self.assertIn("\u8d1d\u53f6\u65af\u4f18\u5316", rendered)
            self.assertIn("\u4f18\u5316\u540e\u91cd\u8bad", rendered)
            self.assertIn("\u5f53\u524d\u4f7f\u7528", rendered)
            self._assert_runtime_text_clean(app)
        finally:
            if old_seed is None:
                os.environ.pop("WATER_EROSION_UI_QA_SEED", None)
            else:
                os.environ["WATER_EROSION_UI_QA_SEED"] = old_seed
            os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()

