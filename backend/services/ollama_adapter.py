import time
import json
import logging
import requests
from typing import Dict, Any, List, Optional, Generator
from backend.config import OLLAMA_HOST, OLLAMA_TIMEOUT_SECONDS
from backend.telemetry.audit import NetworkEgressGuard

logger = logging.getLogger("mrpl.ollama")


class OllamaAdapter:
    """
    Centralized HTTP Client for Local Ollama Server.
    Ensures strict local air-gapped inference and uniform response normalization.
    """

    def __init__(self, host: str = OLLAMA_HOST, timeout: int = OLLAMA_TIMEOUT_SECONDS):
        self.host = host.rstrip("/")
        self.timeout = timeout
        # Air-gap guard check
        NetworkEgressGuard.enforce_local_url(self.host)

    def check_health(self) -> Dict[str, Any]:
        """
        Pings Ollama server and returns reachability status and latency.
        """
        NetworkEgressGuard.enforce_local_url(self.host)
        t0 = time.time()
        try:
            res = requests.get(f"{self.host}/api/tags", timeout=5)
            latency_ms = round((time.time() - t0) * 1000, 2)
            if res.status_code == 200:
                data = res.json()
                models_count = len(data.get("models", []))
                return {
                    "reachable": True,
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "host": self.host,
                    "models_count": models_count,
                }
            else:
                return {
                    "reachable": False,
                    "status": "degraded",
                    "latency_ms": latency_ms,
                    "host": self.host,
                    "error": f"HTTP {res.status_code}: {res.text}",
                }
        except requests.exceptions.ConnectionError:
            return {
                "reachable": False,
                "status": "unavailable",
                "latency_ms": None,
                "host": self.host,
                "error": "Ollama server is not running or unreachable at local port 11434.",
            }
        except Exception as e:
            return {
                "reachable": False,
                "status": "error",
                "latency_ms": None,
                "host": self.host,
                "error": str(e),
            }

    def list_tags(self) -> List[Dict[str, Any]]:
        """
        Fetches list of installed models from local Ollama.
        """
        NetworkEgressGuard.enforce_local_url(self.host)
        try:
            res = requests.get(f"{self.host}/api/tags", timeout=self.timeout)
            res.raise_for_status()
            data = res.json()
            return data.get("models", [])
        except Exception as e:
            logger.error(f"Failed to fetch Ollama tags: {e}")
            return []

    def show_model(self, model_name: str) -> Dict[str, Any]:
        """
        Fetches detailed model metadata from Ollama `/api/show`.
        """
        NetworkEgressGuard.enforce_local_url(self.host)
        try:
            res = requests.post(
                f"{self.host}/api/show",
                json={"name": model_name},
                timeout=self.timeout,
            )
            if res.status_code == 200:
                return res.json()
            else:
                logger.warning(f"Ollama show returned {res.status_code} for {model_name}")
                return {}
        except Exception as e:
            logger.error(f"Failed to show Ollama model {model_name}: {e}")
            return {}

    @staticmethod
    def _prepare_images(images: List[str], max_dim: int = 1200) -> List[str]:
        clean_images = []
        for img in images:
            if not isinstance(img, str) or not img.strip():
                continue
            b64_str = img.split(",", 1)[1] if "," in img else img
            try:
                import io
                import base64
                from PIL import Image
                raw_bytes = base64.b64decode(b64_str)
                with Image.open(io.BytesIO(raw_bytes)) as pil_img:
                    if max(pil_img.size) > max_dim:
                        scale = max_dim / max(pil_img.size)
                        new_size = (int(pil_img.size[0] * scale), int(pil_img.size[1] * scale))
                        res_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
                        buf = io.BytesIO()
                        if res_img.mode in ("RGBA", "P"):
                            res_img.save(buf, format="PNG")
                        else:
                            res_img.save(buf, format="JPEG", quality=90)
                        b64_str = base64.b64encode(buf.getvalue()).decode("ascii")
            except Exception as e:
                logger.debug(f"Image optimization note: {e}")
            clean_images.append(b64_str)
        return clean_images

    def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        images: Optional[List[str]] = None,
        stream: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Invokes model via `/api/generate` on local Ollama.
        Supports multimodal base64 images and latency measurement.
        """
        NetworkEgressGuard.enforce_local_url(self.host)

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if images and ("vl" in model.lower() or "vision" in model.lower()):
            clean_imgs = self._prepare_images(images, max_dim=1200)
            if clean_imgs:
                payload["images"] = clean_imgs

        gen_options = dict(options or {})
        if "num_predict" not in gen_options:
            # For reasoning models (qwen3:4b), allocate 2048 tokens to accommodate internal chain-of-thought + complete answer
            if "qwen3" in model.lower():
                gen_options["num_predict"] = 2048
            else:
                gen_options["num_predict"] = 768
        if "temperature" not in gen_options:
            gen_options["temperature"] = 0.2
        if "num_ctx" not in gen_options:
            gen_options["num_ctx"] = 4096
        if gen_options:
            payload["options"] = gen_options

        t0 = time.time()
        try:
            res = requests.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            res.raise_for_status()
            elapsed_ms = round((time.time() - t0) * 1000, 2)
            data = res.json()

            resp_text = data.get("response", "")
            if resp_text and "<think>" in resp_text:
                resp_text = re.sub(r"<think>[\s\S]*?</think>", "", resp_text).strip()

            return {
                "success": True,
                "model": model,
                "response": resp_text,
                "latency_ms": elapsed_ms,
                "eval_count": data.get("eval_count", 0),
                "eval_duration_ns": data.get("eval_duration", 0),
                "prompt_eval_count": data.get("prompt_eval_count", 0),
                "total_duration_ns": data.get("total_duration", 0),
                "done": data.get("done", True),
                "done_reason": data.get("done_reason"),
                "error": None,
            }
        except Exception as e:
            elapsed_ms = round((time.time() - t0) * 1000, 2)
            logger.error(f"Inference error on {model}: {e}")
            return {
                "success": False,
                "model": model,
                "response": "",
                "latency_ms": elapsed_ms,
                "error": str(e),
            }

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        stream: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Invokes model via `/api/chat` on local Ollama.
        """
        NetworkEgressGuard.enforce_local_url(self.host)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        if options:
            payload["options"] = options

        t0 = time.time()
        try:
            res = requests.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            res.raise_for_status()
            elapsed_ms = round((time.time() - t0) * 1000, 2)
            data = res.json()

            message = data.get("message", {})
            content = message.get("content", "")

            return {
                "success": True,
                "model": model,
                "response": content,
                "message": message,
                "latency_ms": elapsed_ms,
                "eval_count": data.get("eval_count", 0),
                "prompt_eval_count": data.get("prompt_eval_count", 0),
                "done": data.get("done", True),
                "error": None,
            }
        except Exception as e:
            elapsed_ms = round((time.time() - t0) * 1000, 2)
            logger.error(f"Chat error on {model}: {e}")
            return {
                "success": False,
                "model": model,
                "response": "",
                "latency_ms": elapsed_ms,
                "error": str(e),
            }
