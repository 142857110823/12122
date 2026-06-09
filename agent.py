"""Local LLM adapter for optional Q&A and result explanation.

The scientific workflow must remain runnable even when the local model is not
configured or cannot be loaded. This module degrades gracefully and never
blocks tools.py execution.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import toml
from dotenv import load_dotenv

from tools import load_tool_schemas


LOCAL_MODEL_NOT_CONFIGURED = "\u672c\u5730\u5f00\u6e90\u6a21\u578b\u672a\u914d\u7f6e"
LOCAL_MODEL_LOAD_FAILED = "\u672c\u5730\u6a21\u578b\u52a0\u8f7d\u5931\u8d25"
LOCAL_INFERENCE_UNAVAILABLE = "\u672c\u5730\u63a8\u7406\u4e0d\u53ef\u7528"
OPENAI_API_KEY_NOT_CONFIGURED = "OpenAI API key 未配置"
OPENAI_SDK_NOT_INSTALLED = "OpenAI SDK 未安装"
OPENAI_INFERENCE_UNAVAILABLE = "OpenAI API 推理不可用"
EXTERNAL_LLM_DISABLED = "External LLM disabled by data protection policy"
SCIENTIFIC_CHAIN_STILL_AVAILABLE = "\u5f53\u524d\u79d1\u7814\u5de5\u5177\u94fe\u4ecd\u53ef\u6b63\u5e38\u4f7f\u7528"
CONFIGURE_LOCAL_MODEL_HINT = "\u5982\u9700\u672c\u5730\u95ee\u7b54\u6216\u7ed3\u679c\u89e3\u91ca\uff0c\u8bf7\u914d\u7f6e `LLM_LOCAL_MODEL_PATH` \u540e\u91cd\u8bd5\u3002"
ASSISTANT_DISPLAY_NAME = "智能小助手"


if os.environ.get("WATER_EROSION_DISABLE_DOTENV") != "1":
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def load_system_prompt() -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "system.txt")
    if not os.path.exists(prompt_path):
        return "You are a concise scientific assistant for this platform."
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()


@dataclass
class LocalLLMSettings:
    backend: str = "openai"
    local_model_path: str = ""
    openai_model: str = "gpt-5.5"
    openai_timeout_seconds: float = 6.0
    openai_max_output_tokens: int = 700
    data_security_mode: str = "research_sensitive"
    allow_external_llm: bool = False
    assistant_context_policy: str = "metadata_only"
    data_retention_days: int = 30
    device: str = "auto"
    dtype: str = "auto"
    max_new_tokens: int = 512
    temperature: float = 0.3
    trust_remote_code: bool = False


def _load_llm_settings() -> LocalLLMSettings:
    config_path = os.path.join(os.path.dirname(__file__), "config", "llm.toml")
    file_cfg: Dict[str, Any] = {}
    if os.path.exists(config_path):
        try:
            file_cfg = toml.load(config_path).get("llm", {}) or {}
        except Exception:
            file_cfg = {}

    def pick(env_key: str, file_key: str, default: Any) -> Any:
        value = os.getenv(env_key)
        if value not in (None, ""):
            return value
        return file_cfg.get(file_key, default)

    def pick_int(env_key: str, file_key: str, default: int) -> int:
        try:
            return int(pick(env_key, file_key, default))
        except (TypeError, ValueError):
            return default

    def pick_float(env_key: str, file_key: str, default: float) -> float:
        try:
            return float(pick(env_key, file_key, default))
        except (TypeError, ValueError):
            return default

    def pick_bool(env_key: str, file_key: str, default: bool) -> bool:
        value = pick(env_key, file_key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y", "on"}:
                return True
            if normalized in {"false", "0", "no", "n", "off"}:
                return False
        return default

    return LocalLLMSettings(
        backend=str(pick("LLM_BACKEND", "backend", "openai")).strip().lower(),
        local_model_path=str(pick("LLM_LOCAL_MODEL_PATH", "local_model_path", "")).strip(),
        openai_model=str(pick("OPENAI_MODEL", "openai_model", "gpt-5.5")).strip() or "gpt-5.5",
        openai_timeout_seconds=pick_float("OPENAI_TIMEOUT_SECONDS", "openai_timeout_seconds", 6.0),
        openai_max_output_tokens=pick_int("OPENAI_MAX_OUTPUT_TOKENS", "openai_max_output_tokens", 700),
        data_security_mode=str(pick("DATA_SECURITY_MODE", "data_security_mode", "research_sensitive")).strip().lower() or "research_sensitive",
        allow_external_llm=pick_bool("ALLOW_EXTERNAL_LLM", "allow_external_llm", False),
        assistant_context_policy=str(pick("ASSISTANT_CONTEXT_POLICY", "assistant_context_policy", "metadata_only")).strip().lower() or "metadata_only",
        data_retention_days=pick_int("DATA_RETENTION_DAYS", "data_retention_days", 30),
        device=str(pick("LLM_DEVICE", "device", "auto")).strip().lower(),
        dtype=str(pick("LLM_DTYPE", "dtype", "auto")).strip().lower(),
        max_new_tokens=pick_int("LLM_MAX_NEW_TOKENS", "max_new_tokens", 512),
        temperature=pick_float("LLM_TEMPERATURE", "temperature", 0.3),
        trust_remote_code=pick_bool("LLM_TRUST_REMOTE_CODE", "trust_remote_code", False),
    )


def _sanitize_sensitive_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    text = re.sub(r"sk-[A-Za-z0-9_-]{10,}", "[REDACTED_SECRET]", text)
    text = re.sub(r"(?i)\b(OPENAI_API_KEY|LLM_API_KEY)\s*=\s*[^\s,;，；]+", r"\1=[REDACTED_SECRET]", text)
    text = re.sub(r"[A-Za-z]:\\[^\s,，。；;]+", "[REDACTED_PATH]", text)
    text = re.sub(r"(?<!\w)/(Users|home|mnt|var|tmp)/[^\s,，。；;]+", "[REDACTED_PATH]", text)
    return text


def _metadata_only_state_summary(state: Optional[dict]) -> str:
    state = state or {}
    uploads = state.get("uploads") or {}
    feature_table = state.get("feature_table") or {}
    models = state.get("models") or {}
    predictions = state.get("predictions") or {}
    quality = state.get("_quality_report") or {}
    run_context = state.get("run_context") or {}
    explanation = state.get("_explanation_meta") or {}
    lines = [
        "Platform state summary",
        f"workflow_stage={state.get('workflow_stage') or 'idle'}",
        f"uploads_count={len(uploads)}",
        f"feature_table_ready={bool(feature_table)}",
        f"models_count={len(models)}",
        f"best_model={state.get('best_model') or ''}",
        f"predictions_ready={bool(predictions)}",
        f"quality_gate={quality.get('gate_verdict') or ''}",
        f"evidence_count={len(run_context.get('evidence_paths') or [])}",
        f"explanation_mode={explanation.get('explanation_mode') or ''}",
        f"shap_ready={bool(explanation.get('shap_ready'))}",
    ]
    return "\n".join(_sanitize_sensitive_text(line) for line in lines)


class LocalTransformersBackend:
    """Lazy local text-generation backend with safe fallback behavior."""

    def __init__(self, settings: LocalLLMSettings):
        self.settings = settings
        self._pipeline = None
        self._load_error: Optional[str] = None

    def _torch_module(self):
        try:
            return importlib.import_module("torch")
        except Exception:
            return None

    def _device_arg(self):
        device = self.settings.device
        if device == "cpu":
            return -1
        if device == "cuda":
            return 0
        torch = self._torch_module()
        if torch is not None and getattr(torch.cuda, "is_available", lambda: False)():
            return 0
        return -1

    def _torch_dtype(self):
        if self.settings.dtype in ("", "auto"):
            return None
        torch = self._torch_module()
        if torch is None:
            return None
        return getattr(torch, self.settings.dtype, None)

    def available(self) -> Tuple[bool, str]:
        if self.settings.backend != "transformers":
            return False, f"Unsupported local backend: {self.settings.backend}"
        if not self.settings.local_model_path:
            return False, LOCAL_MODEL_NOT_CONFIGURED
        if not os.path.exists(self.settings.local_model_path):
            return False, f"{LOCAL_MODEL_LOAD_FAILED}\uff1a\u6a21\u578b\u8def\u5f84\u4e0d\u5b58\u5728"
        return True, ""

    def _ensure_pipeline(self) -> Tuple[bool, str]:
        ok, reason = self.available()
        if not ok:
            return False, reason
        if self._pipeline is not None:
            return True, ""
        if self._load_error:
            return False, self._load_error

        try:
            transformers = importlib.import_module("transformers")
            kwargs: Dict[str, Any] = {
                "task": "text-generation",
                "model": self.settings.local_model_path,
                "tokenizer": self.settings.local_model_path,
                "trust_remote_code": self.settings.trust_remote_code,
                "device": self._device_arg(),
            }
            torch_dtype = self._torch_dtype()
            if torch_dtype is not None:
                kwargs["torch_dtype"] = torch_dtype
            self._pipeline = transformers.pipeline(**kwargs)
            return True, ""
        except Exception as exc:
            self._load_error = f"{LOCAL_MODEL_LOAD_FAILED}\uff1a{exc}"
            self._pipeline = None
            return False, self._load_error

    def generate(self, prompt: str) -> Tuple[bool, str]:
        ok, reason = self._ensure_pipeline()
        if not ok:
            return False, reason
        try:
            outputs = self._pipeline(
                prompt,
                max_new_tokens=self.settings.max_new_tokens,
                temperature=self.settings.temperature,
                do_sample=self.settings.temperature > 0,
                return_full_text=False,
            )
            if not outputs:
                return False, f"{LOCAL_INFERENCE_UNAVAILABLE}\uff1a\u6a21\u578b\u672a\u8fd4\u56de\u7ed3\u679c"
            text = str(outputs[0].get("generated_text", "")).strip()
            if not text:
                return False, f"{LOCAL_INFERENCE_UNAVAILABLE}\uff1a\u6a21\u578b\u8fd4\u56de\u4e3a\u7a7a"
            return True, text
        except Exception as exc:
            return False, f"{LOCAL_INFERENCE_UNAVAILABLE}\uff1a{exc}"


class OpenAIResponsesBackend:
    """Backend for server-side OpenAI Responses API calls.

    The API key is read only from the process environment. It is never passed
    through Streamlit UI state and is never included in returned error text.
    """

    def __init__(self, settings: LocalLLMSettings):
        self.settings = settings
        self._client = None
        self._load_error: Optional[str] = None

    def _api_key(self) -> str:
        return str(os.getenv("OPENAI_API_KEY") or "").strip()

    def _openai_module(self):
        try:
            return importlib.import_module("openai")
        except Exception:
            return None

    def available(self) -> Tuple[bool, str]:
        if self.settings.backend != "openai":
            return False, f"Unsupported OpenAI backend: {self.settings.backend}"
        if not self.settings.allow_external_llm:
            return False, EXTERNAL_LLM_DISABLED
        if not self._api_key():
            return False, OPENAI_API_KEY_NOT_CONFIGURED
        if self._openai_module() is None:
            return False, OPENAI_SDK_NOT_INSTALLED
        return True, ""

    def _ensure_client(self) -> Tuple[bool, str]:
        ok, reason = self.available()
        if not ok:
            return False, reason
        if self._client is not None:
            return True, ""
        if self._load_error:
            return False, self._load_error
        try:
            openai_module = self._openai_module()
            self._client = openai_module.OpenAI(
                api_key=self._api_key(),
                timeout=self.settings.openai_timeout_seconds,
            )
            return True, ""
        except Exception:
            self._client = None
            self._load_error = f"{OPENAI_INFERENCE_UNAVAILABLE}\uff1a客户端初始化失败"
            return False, self._load_error

    @staticmethod
    def _extract_text(response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if output_text:
            return str(output_text).strip()
        output = getattr(response, "output", None)
        if isinstance(output, list):
            chunks: List[str] = []
            for item in output:
                content = getattr(item, "content", None)
                if isinstance(content, list):
                    for part in content:
                        text = getattr(part, "text", None)
                        if text:
                            chunks.append(str(text))
            return "\n".join(chunks).strip()
        return ""

    def generate(self, prompt: str) -> Tuple[bool, str]:
        ok, reason = self._ensure_client()
        if not ok:
            return False, reason
        try:
            client = self._client
            response = client.responses.create(
                model=self.settings.openai_model,
                input=prompt,
                max_output_tokens=self.settings.openai_max_output_tokens,
            )
            text = self._extract_text(response)
            if not text:
                return False, f"{OPENAI_INFERENCE_UNAVAILABLE}\uff1a模型未返回文本"
            return True, text
        except Exception as exc:
            message = str(exc).splitlines()[0][:160]
            return False, f"{OPENAI_INFERENCE_UNAVAILABLE}\uff1a{message}"


class Agent:
    """Optional assistant layer for local Q&A and result explanation."""

    def __init__(self):
        self.settings = _load_llm_settings()
        if self.settings.backend == "openai":
            self.backend = OpenAIResponsesBackend(self.settings)
        else:
            self.backend = LocalTransformersBackend(self.settings)
        self.system_prompt = load_system_prompt()
        self.tool_schemas = load_tool_schemas()
        self.max_history_rounds = 12
        self.conversation_history: List[Dict[str, str]] = []

    def _trim_history(self):
        max_items = self.max_history_rounds * 2
        if len(self.conversation_history) > max_items:
            self.conversation_history = self.conversation_history[-max_items:]

    def _tool_summary(self, result: dict) -> str:
        if result.get("status") == "error":
            return json.dumps({"status": "error", "message": result.get("message", "unknown error")}, ensure_ascii=False)
        keys = [
            "message",
            "best_algorithm",
            "best_rmse",
            "best_r2",
            "scenario",
            "sample_count",
            "n_samples",
            "n_features",
            "run_id",
            "gate_verdict",
        ]
        summary = {key: result.get(key) for key in keys if key in result}
        if "metrics" in result and isinstance(result["metrics"], list):
            summary["metrics_preview"] = result["metrics"][:3]
        return json.dumps(summary, ensure_ascii=False, indent=2)

    def _deterministic_analysis(self, stage: str, tool_name: str, tool_result: dict) -> str:
        if tool_result.get("status") == "error":
            return f"{stage} / {tool_name} failed: {tool_result.get('message', 'unknown error')}"
        parts = [tool_result.get("message", "Operation completed.")]
        if tool_result.get("best_algorithm"):
            parts.append(f"Best model: {tool_result['best_algorithm']}")
        if tool_result.get("gate_verdict"):
            parts.append(f"Gate verdict: {tool_result['gate_verdict']}")
        return " ".join(parts)

    def _deterministic_response(self, user_message: str, state: dict, backend_reason: str = "") -> str:
        state = state or {}
        uploads = state.get("uploads") or {}
        feature_table = state.get("feature_table") or {}
        models = state.get("models") or {}
        predictions = state.get("predictions") or {}
        quality = state.get("_quality_report") or {}
        stage = state.get("workflow_stage") or "idle"

        if not uploads:
            next_step = "下一步：先进入数据处理页上传或加载 R、K、LS、C、P 和 label 栅格数据。"
        elif not quality:
            next_step = "下一步：运行数据质量检查，确认变量识别、可读性、覆盖率和取值范围。"
        elif not feature_table:
            next_step = "下一步：构建建模特征表，生成可训练的样本矩阵。"
        elif not models:
            next_step = "下一步：进入模型构建页训练候选模型；如已设置手动超参数，会进入训练链路。"
        elif not predictions:
            best_model = state.get("best_model") or "当前最优模型"
            next_step = f"下一步：使用 {best_model} 生成预测，随后查看解释结果和导出证据包。"
        else:
            next_step = "下一步：检查预测、解释、报告和证据包路径是否齐全，再导出结果。"

        status_bits = [
            f"当前阶段：{stage}",
            f"上传文件：{len(uploads)} 个",
            f"特征表：{'已生成' if feature_table else '未生成'}",
            f"模型：{len(models)} 个",
            f"预测：{'已生成' if predictions else '未生成'}",
        ]
        if quality.get("gate_verdict"):
            status_bits.append(f"质量门控：{quality.get('gate_verdict')}")
        if backend_reason:
            status_bits.append(f"本地模型：{backend_reason}")
        question = _sanitize_sensitive_text(user_message).strip()
        question_line = f"我已收到你的问题：{question}" if question else "我已收到你的问题。"
        backend_reason = _sanitize_sensitive_text(backend_reason)
        return (
            f"{ASSISTANT_DISPLAY_NAME}：{question_line}\n"
            + "；".join(status_bits)
            + f"\n{next_step}"
        )

    def _build_chat_prompt(self, user_message: str, mode: str, external: bool = False, state: Optional[dict] = None) -> str:
        def clean(value: str) -> str:
            return _sanitize_sensitive_text(value) if external else value

        history = [f"{item['role']}: {clean(item['content'])}" for item in self.conversation_history[-self.max_history_rounds * 2:]]
        history.append(f"user: {clean(user_message)}")
        state_summary = ""
        if external and self.settings.assistant_context_policy == "metadata_only":
            state_summary = _metadata_only_state_summary(state)
        return (
            f"{self.system_prompt}\n\n"
            f"You are running in {mode}. Give concise, useful, evidence-aware Chinese answers. "
            "Only use the current platform state and provided evidence. "
            "Do not invent platform capabilities, metrics, paths, or scientific conclusions.\n\n"
            + (state_summary + "\n\n" if state_summary else "")
            + "\n".join(history)
            + "\nassistant:"
        )

    def _store_dialogue(self, user_message: str, assistant_text: str):
        self.conversation_history.append({"role": "user", "content": _sanitize_sensitive_text(user_message)})
        self.conversation_history.append({"role": "assistant", "content": _sanitize_sensitive_text(assistant_text)})
        self._trim_history()

    def respond(self, user_message: str, state: dict, progress_callback=None) -> dict:
        result = {"text": "", "tool_calls": [], "images": [], "maps": [], "error": None}
        try:
            ok, reason = self.backend.available()
            if not ok:
                text = self._deterministic_response(user_message, state, reason)
                self._store_dialogue(user_message, text)
                result["text"] = text
                return result

            if progress_callback:
                mode_label = "OpenAI API" if self.settings.backend == "openai" else "Local model"
                progress_callback(f"{mode_label} is thinking...", 0.4)

            mode = "OpenAI Responses API mode" if self.settings.backend == "openai" else "local inference mode"
            prompt = self._build_chat_prompt(user_message, mode, external=self.settings.backend == "openai", state=state)
            ok, text = self.backend.generate(prompt)
            if not ok:
                fallback = self._deterministic_response(user_message, state, text)
                self._store_dialogue(user_message, fallback)
                result["text"] = fallback
                return result

            self._store_dialogue(user_message, text)
            result["text"] = _sanitize_sensitive_text(text)
            if progress_callback:
                progress_callback("Done", 1.0)
            return result
        except Exception as exc:
            traceback.print_exc()
            result["error"] = f"{LOCAL_INFERENCE_UNAVAILABLE}\uff1a{exc}"
            result["text"] = result["error"]
            return result

    def analyze(self, stage: str, tool_name: str, tool_result: dict, state: dict = None) -> str:
        ok, _ = self.backend.available()
        if not ok:
            return self._deterministic_analysis(stage, tool_name, tool_result)
        prompt = (
            f"{self.system_prompt}\n\n"
            "Summarize the scientific tool result in under 120 Chinese characters. "
            "State only the conclusion and the next recommended action.\n\n"
            f"Stage: {stage}\n"
            f"Tool: {tool_name}\n"
            f"Result summary:\n{self._tool_summary(tool_result)}\n"
            "Answer:"
        )
        ok, text = self.backend.generate(prompt)
        if not ok:
            return self._deterministic_analysis(stage, tool_name, tool_result)
        return text.strip()

    def reset(self):
        self.conversation_history = []


_agent_instance: Optional[Agent] = None


def get_agent() -> Agent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = Agent()
    return _agent_instance
