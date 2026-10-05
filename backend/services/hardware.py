import subprocess
import logging
import psutil
from typing import Dict, Any, Optional

logger = logging.getLogger("mrpl.hardware")


class HardwareDetector:
    """
    Detects real-time system hardware: NVIDIA GPU VRAM, CPU cores/load, system RAM.
    """

    @classmethod
    def get_hardware_telemetry(cls) -> Dict[str, Any]:
        gpu_info = cls._get_gpu_info()
        cpu_info = cls._get_cpu_info()
        ram_info = cls._get_ram_info()

        return {
            "gpu": gpu_info,
            "cpu": cpu_info,
            "ram": ram_info,
            "can_fit_model": cls.can_fit_model,
        }

    @classmethod
    def _get_gpu_info(cls) -> Dict[str, Any]:
        """
        Attempts to read GPU metrics via nvidia-smi.
        """
        default_gpu = {
            "available": False,
            "name": "CPU-Only / Integrated Graphics",
            "total_vram_gb": 0.0,
            "used_vram_gb": 0.0,
            "free_vram_gb": 0.0,
            "utilization_pct": 0,
            "temperature_c": None,
        }

        try:
            # Query nvidia-smi for memory and utilization
            cmd = [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )

            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split("\n")
                first_line = lines[0].split(",")
                if len(first_line) >= 6:
                    name = first_line[0].strip()
                    total_mb = float(first_line[1].strip())
                    used_mb = float(first_line[2].strip())
                    free_mb = float(first_line[3].strip())
                    util_pct = int(first_line[4].strip())
                    temp_c = int(first_line[5].strip())

                    return {
                        "available": True,
                        "name": name,
                        "total_vram_gb": round(total_mb / 1024.0, 2),
                        "used_vram_gb": round(used_mb / 1024.0, 2),
                        "free_vram_gb": round(free_mb / 1024.0, 2),
                        "utilization_pct": util_pct,
                        "temperature_c": temp_c,
                    }
        except Exception as e:
            logger.debug(f"nvidia-smi query skipped or failed: {e}")

        return default_gpu

    @classmethod
    def _get_cpu_info(cls) -> Dict[str, Any]:
        try:
            logical_cores = psutil.cpu_count(logical=True) or 4
            physical_cores = psutil.cpu_count(logical=False) or 2
            cpu_percent = psutil.cpu_percent(interval=None)

            return {
                "logical_cores": logical_cores,
                "physical_cores": physical_cores,
                "utilization_pct": cpu_percent,
            }
        except Exception as e:
            logger.warning(f"Error reading CPU telemetry: {e}")
            return {
                "logical_cores": 4,
                "physical_cores": 2,
                "utilization_pct": 10.0,
            }

    @classmethod
    def _get_ram_info(cls) -> Dict[str, Any]:
        try:
            mem = psutil.virtual_memory()
            return {
                "total_gb": round(mem.total / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "utilization_pct": mem.percent,
            }
        except Exception as e:
            logger.warning(f"Error reading RAM telemetry: {e}")
            return {
                "total_gb": 16.0,
                "used_gb": 8.0,
                "available_gb": 8.0,
                "utilization_pct": 50.0,
            }

    @classmethod
    def can_fit_model(cls, estimated_vram_gb: float) -> Dict[str, Any]:
        """
        Calculates if a model can reasonably run on GPU or CPU.
        """
        gpu = cls._get_gpu_info()
        ram = cls._get_ram_info()

        # If GPU is present and free VRAM is enough with margin
        margin_gb = 0.3
        if gpu["available"]:
            if gpu["free_vram_gb"] >= (estimated_vram_gb - margin_gb):
                return {
                    "can_run": True,
                    "target": "GPU",
                    "reason": f"Sufficient GPU VRAM ({gpu['free_vram_gb']} GB free >= {estimated_vram_gb} GB needed)",
                }
            elif (gpu["total_vram_gb"]) >= estimated_vram_gb:
                # GPU could hold it if current VRAM is cleared/swapped by Ollama
                return {
                    "can_run": True,
                    "target": "GPU (VRAM Swapped / Hybrid)",
                    "reason": f"Fits total VRAM ({gpu['total_vram_gb']} GB total >= {estimated_vram_gb} GB needed)",
                }

        # Fallback to system RAM
        if ram["available_gb"] >= (estimated_vram_gb + 1.0):
            return {
                "can_run": True,
                "target": "CPU (RAM Offload)",
                "reason": f"Offloading to System RAM ({ram['available_gb']} GB available)",
            }

        return {
            "can_run": False,
            "target": "None",
            "reason": f"Insufficient memory: Needs ~{estimated_vram_gb} GB, Free VRAM: {gpu['free_vram_gb']} GB, Free RAM: {ram['available_gb']} GB",
        }
