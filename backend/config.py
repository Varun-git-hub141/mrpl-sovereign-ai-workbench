import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
CONFIG_DIR = BACKEND_DIR / "config"
DATA_DIR = BACKEND_DIR / "data"
SAMPLES_DIR = BASE_DIR / "samples"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

# Ollama Connection & Execution Timeouts
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
MODEL_TIMEOUT_SECONDS = OLLAMA_TIMEOUT_SECONDS

# Server Config
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# File paths
MODEL_OVERRIDES_FILE = CONFIG_DIR / "model_overrides.yaml"
ROUTING_WEIGHTS_FILE = CONFIG_DIR / "routing_weights.yaml"
REGISTRY_CACHE_FILE = DATA_DIR / "registry_cache.json"
METRICS_DB_FILE = DATA_DIR / "execution_metrics.json"
BENCHMARK_RESULTS_FILE = DATA_DIR / "benchmark_results.json"
