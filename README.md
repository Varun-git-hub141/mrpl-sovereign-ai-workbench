# MRPL Sovereign AI Workbench

### On-Premise Model Registry, Intelligent Model Router, Execution Planner & Verification Foundation

Designed for industrial public-sector refinery operations, the MRPL Sovereign AI Workbench is designed for air-gapped deployment with zero external LLM inference and local-only model execution.

---

##  Core Architectural Pipeline

```
USER QUERY + FILES
        ↓
REQUEST CONTEXT BUILDER
        ↓
TASK ANALYZER (Intent + Modality + Risk + Capability Demands)
        ↓
MODEL REGISTRY (Dynamic Ollama Discovery + Provenance Vectors)
        ↓
POLICY + HARDWARE ELIGIBILITY (GPU VRAM + Context Fit + Air-Gap Guard)
        ↓
INTELLIGENT MODEL ROUTER (W1-W9 Multi-Factor Suitability Scoring)
        ↓
FIRST-CLASS EXECUTION PLAN (Primary + Verifier + Tools + Risk Policy)
        ↓
EXECUTION ORCHESTRATOR (Local Ollama + Python Calculators + Vision)
        ↓
VERIFICATION ENGINE (Deterministic Checks + Cross-Model Contradiction)
        ↓
RISK / CONFIDENCE ENGINE (Suitability vs Grounded Confidence)
        ↓
HUMAN APPROVAL GATE (For High-Risk Operations)
        ↓
VERIFIED DELIVERABLE & SANITIZED AUDIT TRAIL
```

---
---

## Problem

Industrial engineering workflows often require engineers to work with sensitive documents, equipment records, inspection reports, P&IDs, maintenance history, and engineering calculations.

Cloud-based AI systems can introduce data-sovereignty, confidentiality, and connectivity concerns for such environments.

The MRPL Sovereign AI Workbench addresses this by providing a local-first AI execution architecture where:

- Models execute locally through Ollama.
- Engineering knowledge can remain on-premise.
- Model selection is performed dynamically based on task requirements and hardware constraints.
- AI-generated results are subjected to deterministic and cross-model verification.
- High-risk decisions can require explicit human engineering approval.
- Audit telemetry is sanitized to avoid persisting proprietary prompts and documents.

---

## Key Engineering Features

- **Dynamic Model Registry** — Discovers locally available Ollama models instead of relying on a fixed model list.
- **Capability-Based Model Routing** — Selects models according to reasoning, coding, mathematics, vision, OCR, hardware, latency, and risk requirements.
- **Hybrid RAG** — Combines semantic retrieval with engineering-domain knowledge and evidence sufficiency checks.
- **Evidence-First Execution** — Tracks evidence, provenance, confidence, and contradictions before producing engineering outputs.
- **Deterministic Verification** — Uses Python-based engineering calculators alongside LLM reasoning.
- **Multi-Model Verification** — High-risk workflows can independently cross-check model-generated conclusions.
- **Human-in-the-Loop Approval** — Risk-sensitive operations can be blocked until an authorized engineer approves them.
- **P&ID Knowledge Graph** — Represents equipment and instrument relationships for structured topology-aware queries.
- **Verified Work Products** — Generates structured engineering deliverables with validation before delivery.
- **Sovereignty Monitoring** — Provides runtime checks for external inference and network-egress conditions.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| Backend | Python, FastAPI |
| AI Runtime | Ollama, Open-Weight LLMs |
| Retrieval | Hybrid RAG, Vector Search |
| Engineering Intelligence | Deterministic Python Calculators |
| Data Models | Pydantic |
| Frontend | HTML, CSS, JavaScript |
| Testing | Pytest |
| Documents | DOCX / PDF / XLSX generation |
| Deployment Model | Local / On-Premise / Air-Gapped Compatible |

---

## Security & Data Handling

This repository intentionally excludes sensitive or environment-specific runtime data.

The following are **not committed**:

- Industrial knowledge-base documents
- Runtime execution history
- Audit data
- Vector indexes
- Benchmark artifacts
- Generated deliverables
- Temporary files
- Credentials and environment secrets





---
##  Non-Negotiable Air-Gap & Sovereignty Guarantees

- **Zero Cloud Inference**: External LLM calls = 0. All inferences execute against `http://127.0.0.1:11434`.
- **Zero Model Downloads**: Never pulls or replaces models. Discovers only existing local weights.
- **Model-Agnostic Dynamic Discovery**: The router contains zero hardcoded model tags. Introducing any new open-weight model automatically discovers, profiles, and evaluates it.
- **Sanitized Audit Telemetry**: Audit logs record only execution timings, mathematical scores, and model tags. Proprietary engineering documents and prompt text are never persisted.

---

##  Quick Start

### 1. Requirements
- Python 3.10+
- Local Ollama daemon running on `127.0.0.1:11434`
- NVIDIA GPU with CUDA (optional, CPU fallback supported)

### 2. Launch the Workbench
```bash
py -3 run.py
```
Open your browser at: **`http://127.0.0.1:8000`**

### 3. Run Automated Tests
```bash
py -3 -m pytest tests/ -v
```

---

##  Industrial PSU Scenarios Built-In

1. **P&ID Diagram Inspection**: Multimodal visual equipment trace for Crude Distillation Feed Pump P-101A and connected instrument loops (`FV-101`, `PT-102`, `FIC-101`).
2. **Corrosion Rate & Remaining Life Calculation**: API 570 rate calculation and wall thickness evaluation using ultrasonic survey CSVs.
3. **High-Risk Pump P-101 Operation Approval**: Multi-model independent verification cross-examining vibration data against ISO 10816 Zone D trip limits with mandatory human sign-off.
4. **Refinery Turnaround Memo Brief**: Fast, structured summarization of unit turnaround safety and isolation procedures.

---

##  REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/route` | Analyzes task, tests hardware eligibility, scores models, and constructs `ExecutionPlan` |
| `POST` | `/api/execute` | Orchestrates inference, runs local tools, conducts verification, and gates human sign-off |
| `GET` | `/api/registry/models` | Returns registered models with capability provenance and health status |
| `POST` | `/api/registry/refresh` | Forces dynamic rediscovery of Ollama models |
| `POST` | `/api/registry/override` | Persists capability score overrides to `config/model_overrides.yaml` |
| `POST` | `/api/registry/probe/{id}` | Runs synthetic capability probes on a specific model |
| `GET` | `/api/health/system` | Returns GPU VRAM, CPU load, and Ollama status |
| `GET` | `/api/sovereignty/status` | Returns air-gap compliance and zero-egress verification |
| `POST` | `/api/benchmarks/run` | Executes empirical local latency and accuracy benchmarks |
| `GET` | `/api/trace/history` | Returns sanitized audit traces |
| `POST` | `/api/human-approval/decision` | Submits human engineering approval / rejection decision |
