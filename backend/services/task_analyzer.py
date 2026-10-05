import re
import os
import logging
from typing import List, Dict, Any, Optional
from backend.models.task_profile import (
    TaskProfile,
    TaskType,
    RiskLevel,
    InputModality,
)
from backend.models.model_profile import CapabilityVector
from backend.models.entity_models import (
    EntityResolutionStatus,
    EntityType,
    DomainCategory,
    KnowledgeSourceType,
)
from backend.services.entity_resolver import MRPLEntityResolver

logger = logging.getLogger("mrpl.task_analyzer")


class TaskAnalyzer:
    """
    Analyzes queries and attached files using deterministic pattern matching,
    modality heuristics, MRPL Entity Resolution, and industrial PSU refinery domain rules
    to construct a structured TaskProfile.
    """

    def __init__(self, entity_resolver: Optional[MRPLEntityResolver] = None):
        self.entity_resolver = entity_resolver or MRPLEntityResolver()

    # Keyword patterns for PSU refinery workflows
    PATTERNS = {
        "equipment_approval": re.compile(
            r"\b(approve|approved|approval|continued operation|fitness for service|ffs|rla|remaining life assessment|mocl|critical equipment)\b",
            re.IGNORECASE,
        ),
        "engineering_calc": re.compile(
            r"\b(calculate|corrosion rate|wall thickness|design pressure|asme|api 570|api 510|api 653|flow rate|reynolds|head loss|heat duty|orifice|thickness survey|mpy|mm/year)\b",
            re.IGNORECASE,
        ),
        "pid_inspection": re.compile(
            r"\b(p&id|pid|piping and instrumentation|process flow|pfd|isometric|schematic|equipment connected|instrument tag|line number|valve|pump nozzle)\b",
            re.IGNORECASE,
        ),
        "coding": re.compile(
            r"\b(python|code|script|function|algorithm|class|regex|pandas|numpy|sql|bash|powershell|debug|refactor|unit test)\b",
            re.IGNORECASE,
        ),
        "policy_safety": re.compile(
            r"\b(oisd|peso|safety interlock|hazop|sil|safety integrity|esd|emergency shutdown|work permit|ptw|statutory compliance)\b",
            re.IGNORECASE,
        ),
        "memo_summary": re.compile(
            r"\b(summarize|summary|memo|minutes of meeting|mom|brief|executive summary|abstract|key points|recap)\b",
            re.IGNORECASE,
        ),
    }

    FILE_MODALITY_MAP = {
        # Vision / Scans
        ".png": InputModality.VISION,
        ".jpg": InputModality.VISION,
        ".jpeg": InputModality.VISION,
        ".webp": InputModality.VISION,
        ".bmp": InputModality.VISION,
        ".tiff": InputModality.VISION,
        # Documents
        ".pdf": InputModality.DOCUMENT_PDF,
        ".docx": InputModality.DOCUMENT_PDF,
        ".doc": InputModality.DOCUMENT_PDF,
        ".txt": InputModality.TEXT,
        ".md": InputModality.TEXT,
        # Spreadsheets
        ".csv": InputModality.SPREADSHEET,
        ".xlsx": InputModality.SPREADSHEET,
        ".xls": InputModality.SPREADSHEET,
        # Code
        ".py": InputModality.SOURCE_CODE,
        ".c": InputModality.SOURCE_CODE,
        ".cpp": InputModality.SOURCE_CODE,
        ".js": InputModality.SOURCE_CODE,
        ".sql": InputModality.SOURCE_CODE,
        ".sh": InputModality.SOURCE_CODE,
    }

    def analyze(
        self,
        query: str,
        files: Optional[List[Dict[str, Any]]] = None,
        risk_override: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> TaskProfile:
        """
        Executes hybrid task analysis.
        """
        import uuid
        req_id = request_id or f"req-{uuid.uuid4().hex[:8]}"
        query_text = query.strip()
        files = files or []

        # 1. Modality & File Analysis
        modality, file_signals, est_file_tokens = self._analyze_files(files)

        # 2. MRPL Entity Resolution (Pre-flight Entity Discovery)
        entity_res = self.entity_resolver.resolve(query_text)
        entity_name = entity_res.canonical_name or entity_res.raw_entity
        entity_type_val = entity_res.entity_type.value if entity_res.entity_type else "UNKNOWN"
        entity_status_val = entity_res.resolution_status.value

        # 3. Domain & Intent Classification
        task_type, intent, matched_keywords = self._classify_intent(query_text, modality)

        # Check if coding intent was detected and differentiate generic coding vs engineering coding
        is_coding_task = task_type in [TaskType.CODING, TaskType.GENERIC_CODING, TaskType.ENGINEERING_CODING, TaskType.CODE_GENERATION]
        has_mrpl_entity_or_data = bool(
            entity_res.resolution_status in [EntityResolutionStatus.FOUND_IN_MRPL_KB, EntityResolutionStatus.FOUND_IN_ASSET_REGISTRY]
            or (entity_name and entity_name not in ["GENERIC", "UNKNOWN"] and not getattr(entity_res, "is_generic_tag_inquiry", False))
            or any(k in query_text.lower() for k in [
                "v-201", "p-201", "tk-201", "c-101", "e-801", "e-101", "psv-201", "xv-201", "xv-203", "mov-204", "pcv-201", "y-201",
                "mrpl datasheet", "datasheet", "inspection data", "inspection report", "thickness measurements from", "plant record", "mrpl record"
            ])
            or (files and any(f.get("name", "").endswith(".pdf") or "inspection" in f.get("name", "").lower() for f in files))
        )

        # 4. Knowledge Source & Tool Routing Decision
        if is_coding_task and not has_mrpl_entity_or_data:
            domain_val = DomainCategory.SOFTWARE.value
            knowledge_source_val = "LOCAL MODEL KNOWLEDGE"
            retrieval_mode_val = "NONE"
            reasoning_stage_val = "DIRECT EXECUTION"
            task_type = TaskType.GENERIC_CODING
            intent = "generic_code_generation"
            entity_name = None
            entity_type_val = "NOT_APPLICABLE"
            entity_status_val = "NOT_APPLICABLE"
        elif is_coding_task and has_mrpl_entity_or_data:
            domain_val = DomainCategory.MRPL_ENGINEERING.value
            knowledge_source_val = KnowledgeSourceType.MRPL_LOCAL_KNOWLEDGE_BASE.value
            retrieval_mode_val = "HYBRID"
            reasoning_stage_val = "AFTER RETRIEVAL"
            task_type = TaskType.ENGINEERING_CODING
            intent = "engineering_code_generation"
        elif getattr(entity_res, "is_generic_tag_inquiry", False):
            domain_val = DomainCategory.GENERAL.value
            knowledge_source_val = KnowledgeSourceType.GENERAL_PRETRAINED_KNOWLEDGE.value
            retrieval_mode_val = "NONE"
            reasoning_stage_val = "DIRECT EXECUTION"
            task_type = TaskType.GENERAL_REASONING
            intent = "GENERIC_NOMENCLATURE_EXPLANATION"
        elif entity_res.resolution_status == EntityResolutionStatus.FOUND_IN_MRPL_KB:
            domain_val = DomainCategory.MRPL_ENGINEERING.value
            knowledge_source_val = KnowledgeSourceType.MRPL_LOCAL_KNOWLEDGE_BASE.value
            retrieval_mode_val = "HYBRID"
            reasoning_stage_val = "AFTER RETRIEVAL"
            if "calculate" not in query_text.lower() and not any(k in query_text.lower() for k in ["compute", "remaining life", "corrosion rate"]):
                if task_type in (TaskType.GENERAL_REASONING, TaskType.ENGINEERING_CALCULATION):
                    intent = "KNOWLEDGE_RETRIEVAL"
                    task_type = TaskType.DOCUMENT_QA
        elif entity_res.resolution_status == EntityResolutionStatus.FOUND_IN_ASSET_REGISTRY:
            domain_val = DomainCategory.MRPL_ENGINEERING.value
            knowledge_source_val = KnowledgeSourceType.MRPL_ASSET_REGISTRY.value
            retrieval_mode_val = "HYBRID"
            reasoning_stage_val = "AFTER RETRIEVAL"
            if "calculate" not in query_text.lower() and not any(k in query_text.lower() for k in ["compute", "remaining life", "corrosion rate"]):
                if task_type in (TaskType.GENERAL_REASONING, TaskType.ENGINEERING_CALCULATION):
                    intent = "KNOWLEDGE_RETRIEVAL"
                    task_type = TaskType.DOCUMENT_QA
        elif entity_res.resolution_status in [EntityResolutionStatus.NOT_FOUND_IN_KB, EntityResolutionStatus.NOT_FOUND]:
            domain_val = DomainCategory.MRPL_ENGINEERING.value
            knowledge_source_val = KnowledgeSourceType.MRPL_LOCAL_KNOWLEDGE_BASE.value
            retrieval_mode_val = "NONE"
            reasoning_stage_val = "CONTEXT_GUARD_REFUSAL"
            intent = "UNKNOWN_ENTITY_CHECK"
            if entity_res.raw_entity or "mrpl" in query_text.lower():
                task_type = TaskType.UNKNOWN_MRPL_ENTITY
        elif files or modality in [InputModality.DOCUMENT_PDF, InputModality.SCANNED_PDF, InputModality.VISION]:
            domain_val = DomainCategory.MRPL_ENGINEERING.value
            knowledge_source_val = KnowledgeSourceType.UPLOADED_DOCUMENT.value
            retrieval_mode_val = "LOCAL_PARSER"
            reasoning_stage_val = "AFTER EXTRACTION"
        elif task_type in [TaskType.CODING, TaskType.CODE_GENERATION, TaskType.CODE_REVIEW]:
            domain_val = DomainCategory.SOFTWARE.value
            knowledge_source_val = KnowledgeSourceType.GENERAL_PRETRAINED_KNOWLEDGE.value
            retrieval_mode_val = "NONE"
            reasoning_stage_val = "DIRECT EXECUTION"
        else:
            domain_val = DomainCategory.GENERAL.value
            knowledge_source_val = KnowledgeSourceType.GENERAL_PRETRAINED_KNOWLEDGE.value
            retrieval_mode_val = "NONE"
            reasoning_stage_val = "DIRECT EXECUTION"

        # 5. Required Capability Demand Vector
        capabilities = self._compute_required_capabilities(task_type, modality, query_text)

        # 6. Complexity Estimation
        complexity = self._estimate_complexity(query_text, files, task_type)

        # 7. Risk Assessment (incorporating user override)
        calculated_risk, requires_verification = self._determine_risk(task_type, query_text, complexity)

        final_risk = calculated_risk
        if risk_override:
            override_val = risk_override.lower().strip()
            if override_val in ["low", "medium", "high"]:
                final_risk = RiskLevel(override_val)
                if final_risk == RiskLevel.HIGH:
                    requires_verification = True

        # 8. Context Window Requirement
        prompt_tokens = max(32, len(query_text.split()) * 2)
        total_context = prompt_tokens + est_file_tokens + 1024  # Add headroom for reasoning and response

        # 9. Required Tools Selection (Knowledge/Tool Routing)
        required_tools = []
        if task_type != TaskType.GENERIC_CODING:
            if entity_res.resolution_status == EntityResolutionStatus.FOUND_IN_MRPL_KB:
                required_tools.append("ENGINEERING RAG")
            elif entity_res.resolution_status == EntityResolutionStatus.FOUND_IN_ASSET_REGISTRY:
                required_tools.append("ASSET_REGISTRY")
                required_tools.append("ENGINEERING RAG")
            elif entity_res.resolution_status in [EntityResolutionStatus.NOT_FOUND_IN_KB, EntityResolutionStatus.NOT_FOUND] and (entity_res.raw_entity or "mrpl" in query_text.lower()):
                required_tools.append("MRPL_CONTEXT_GUARD")

        if task_type in [TaskType.CODING, TaskType.GENERIC_CODING, TaskType.ENGINEERING_CODING, TaskType.CODE_GENERATION, TaskType.CODE_REVIEW] or capabilities.coding > 0.70:
            required_tools.append("python_sandbox")
        if task_type == TaskType.ENGINEERING_CALCULATION or capabilities.mathematics > 0.80 or "calculate" in query_text.lower():
            if "engineering_calculator" not in required_tools:
                required_tools.append("engineering_calculator")
            if "python_calculator" not in required_tools:
                required_tools.append("python_calculator")
        if modality in [InputModality.VISION, InputModality.DOCUMENT_PDF, InputModality.MULTIMODAL] or capabilities.vision > 0.60:
            required_tools.append("vision_multimodal_extractor")

        return TaskProfile(
            request_id=req_id,
            task_type=task_type,
            intent=intent,
            risk=final_risk,
            modality=modality,
            complexity=complexity,
            required_capabilities=capabilities,
            required_tools=required_tools,
            requires_verification=requires_verification,
            context_requirement=total_context,
            entity_name=entity_name,
            entity_type=entity_type_val,
            entity_resolution_status=entity_status_val,
            domain=domain_val,
            knowledge_source=knowledge_source_val,
            retrieval_mode=retrieval_mode_val,
            reasoning_stage=reasoning_stage_val,
            extracted_signals={
                "matched_keywords": matched_keywords,
                "file_signals": file_signals,
                "risk_overridden": bool(risk_override),
                "original_calculated_risk": calculated_risk.value,
                "entity_resolution": entity_res.model_dump(),
            },
        )

    def _analyze_files(self, files: List[Dict[str, Any]]) -> (InputModality, List[Dict[str, Any]], int):
        if not files:
            return InputModality.TEXT, [], 0

        detected_modalities = []
        file_signals = []
        total_tokens = 0

        for f in files:
            filename = f.get("name", "")
            size_bytes = f.get("size", 0)
            ext = os.path.splitext(filename)[1].lower()

            mod = self.FILE_MODALITY_MAP.get(ext, InputModality.TEXT)
            detected_modalities.append(mod)

            # Estimate token requirement from file size
            if mod == InputModality.VISION:
                tokens = 2048  # standard image token embedding budget
            elif mod == InputModality.DOCUMENT_PDF:
                tokens = min(32768, max(2048, int(size_bytes / 3)))
            elif mod == InputModality.SPREADSHEET:
                tokens = min(16384, max(1024, int(size_bytes / 4)))
            elif mod == InputModality.SOURCE_CODE:
                tokens = min(8192, max(512, int(size_bytes / 3)))
            else:
                tokens = min(8192, max(512, int(size_bytes / 4)))

            total_tokens += tokens
            file_signals.append({
                "filename": filename,
                "extension": ext,
                "modality": mod.value,
                "size_bytes": size_bytes,
                "est_tokens": tokens,
            })

        # Hierarchy for dominant modality
        unique_modalities = set(detected_modalities)
        if len(unique_modalities) > 1 and InputModality.VISION in unique_modalities:
            dominant = InputModality.MULTIMODAL
        elif InputModality.VISION in unique_modalities:
            dominant = InputModality.VISION
        elif InputModality.DOCUMENT_PDF in unique_modalities:
            dominant = InputModality.DOCUMENT_PDF
        elif InputModality.SPREADSHEET in unique_modalities:
            dominant = InputModality.SPREADSHEET
        elif InputModality.SOURCE_CODE in unique_modalities:
            dominant = InputModality.SOURCE_CODE
        else:
            dominant = detected_modalities[0]

        return dominant, file_signals, total_tokens

    def _classify_intent(self, query: str, modality: InputModality) -> (TaskType, str, List[str]):
        matched = []
        q_lower = query.lower()

        # 1. Check explicit code generation / Python requests FIRST (e.g. "Write Python parser for PID telemetry")
        if modality == InputModality.SOURCE_CODE or ("write" in q_lower and ("python" in q_lower or "code" in q_lower or "script" in q_lower or "parser" in q_lower)) or "def " in q_lower:
            matched.append("coding")
            return TaskType.CODING, "generate_or_debug_code", matched

        if "review" in q_lower and ("code" in q_lower or "script" in q_lower or "python" in q_lower):
            matched.append("code_review")
            return TaskType.CODE_REVIEW, "review_and_audit_code", matched

        # 2. Check equipment approval & critical operation
        if self.PATTERNS["equipment_approval"].search(query):
            matched.append("equipment_approval")
            return TaskType.EQUIPMENT_APPROVAL, "evaluate_equipment_continued_operation", matched

        # 3. Check engineering calculations (corrosion rate, thickness, engineering math)
        if self.PATTERNS["engineering_calc"].search(query) or ("calculate" in q_lower and ("corrosion" in q_lower or "thickness" in q_lower or "rate" in q_lower)):
            matched.append("engineering_calc")
            intent = "calculate_corrosion_rate" if ("corrosion" in q_lower or "thickness" in q_lower) else "calculate_engineering_parameters"
            return TaskType.ENGINEERING_CALCULATION, intent, matched

        # 4. Multimodal Engineering Analysis & Cross-Evidence Checking
        if ("contradiction" in q_lower or "cross-evidence" in q_lower or "conflict" in q_lower) and (
            "report" in q_lower or "p&id" in q_lower or "diagram" in q_lower or modality in [InputModality.DOCUMENT_PDF, InputModality.VISION, InputModality.MULTIMODAL]
        ):
            matched.append("multimodal_cross_evidence")
            return TaskType.MULTIMODAL_ENGINEERING_ANALYSIS, "check_cross_evidence_and_contradictions", matched

        if ("inspection" in q_lower or "report" in q_lower) and ("p&id" in q_lower or "diagram" in q_lower or "drawing" in q_lower):
            matched.append("multimodal_engineering_analysis")
            return TaskType.MULTIMODAL_DOCUMENT_ANALYSIS, "review_multimodal_inspection_and_diagram", matched

        # 5. Vision / P&ID / Visual Diagrams
        if modality in [InputModality.VISION, InputModality.MULTIMODAL] or self.PATTERNS["pid_inspection"].search(query) or "p&id" in q_lower or "diagram" in q_lower:
            matched.append("vision_modality")
            return TaskType.MULTIMODAL_DOCUMENT_ANALYSIS, "analyze_visual_diagram_or_pid", matched

        # 6. General Coding
        if self.PATTERNS["coding"].search(query):
            matched.append("coding")
            return TaskType.CODING, "generate_or_debug_code", matched

        # 7. Document QA & OCR extraction
        if "ocr" in q_lower or "scanned" in q_lower or modality == InputModality.SCANNED_PDF:
            matched.append("ocr_extraction")
            return TaskType.OCR_EXTRACTION, "extract_scanned_document_text", matched

        if modality == InputModality.DOCUMENT_PDF or ("read" in q_lower and ("report" in q_lower or "document" in q_lower or "thickness" in q_lower)):
            matched.append("document_qa")
            return TaskType.MULTIMODAL_DOCUMENT_ANALYSIS, "extract_and_answer_from_document", matched

        # 8. Check policy and safety compliance
        if self.PATTERNS["policy_safety"].search(query):
            matched.append("policy_safety")
            return TaskType.POLICY_COMPLIANCE, "verify_safety_compliance", matched

        # 9. Check memo summarization
        if self.PATTERNS["memo_summary"].search(query):
            matched.append("memo_summary")
            return TaskType.MEMO_SUMMARIZATION, "summarize_document_or_memo", matched

        return TaskType.GENERAL_REASONING, "general_knowledge_query", matched

    def _compute_required_capabilities(
        self,
        task_type: TaskType,
        modality: InputModality,
        query: str,
    ) -> CapabilityVector:
        """
        Builds the normalized capability vector required for the specific task.
        """
        # Base vector
        caps = {
            "reasoning": 0.50,
            "coding": 0.05,
            "vision": 0.05,
            "document_understanding": 0.40,
            "mathematics": 0.30,
            "ocr": 0.05,
            "tool_use": 0.40,
            "general": 0.60,
        }

        if task_type in [TaskType.MULTIMODAL_DOCUMENT_ANALYSIS, TaskType.MULTIMODAL_ENGINEERING_ANALYSIS] or modality in [InputModality.VISION, InputModality.MULTIMODAL]:
            caps["vision"] = 0.95
            caps["ocr"] = 0.90
            caps["document_understanding"] = 0.92
            caps["reasoning"] = 0.85
            caps["mathematics"] = 0.70
            caps["tool_use"] = 0.80
            caps["coding"] = 0.20

        elif task_type == TaskType.VISION_P_AND_ID:
            caps["vision"] = 0.98
            caps["document_understanding"] = 0.90
            caps["ocr"] = 0.85
            caps["reasoning"] = 0.80
            caps["tool_use"] = 0.60

        elif task_type in [TaskType.DOCUMENT_QA, TaskType.OCR_EXTRACTION]:
            caps["document_understanding"] = 0.95
            caps["reasoning"] = 0.85
            caps["ocr"] = 0.90
            caps["general"] = 0.80

        elif task_type == TaskType.EQUIPMENT_APPROVAL:
            caps["reasoning"] = 0.95
            caps["document_understanding"] = 0.90
            caps["mathematics"] = 0.85
            caps["tool_use"] = 0.80
            caps["coding"] = 0.40
            caps["general"] = 0.80

        elif task_type == TaskType.ENGINEERING_CALCULATION:
            caps["mathematics"] = 0.95
            caps["coding"] = 0.85
            caps["reasoning"] = 0.75
            caps["tool_use"] = 0.70
            caps["document_understanding"] = 0.20
            caps["general"] = 0.60
            caps["vision"] = 0.05
            caps["ocr"] = 0.05

        elif task_type in [TaskType.CODING, TaskType.GENERIC_CODING, TaskType.ENGINEERING_CODING, TaskType.CODE_GENERATION, TaskType.CODE_REVIEW]:
            caps["coding"] = 0.96
            caps["reasoning"] = 0.75
            caps["mathematics"] = 0.65
            caps["tool_use"] = 0.75
            caps["general"] = 0.50

        elif task_type == TaskType.POLICY_COMPLIANCE:
            caps["reasoning"] = 0.90
            caps["document_understanding"] = 0.95
            caps["general"] = 0.85
            caps["tool_use"] = 0.60

        elif task_type == TaskType.MEMO_SUMMARIZATION:
            caps["general"] = 0.90
            caps["document_understanding"] = 0.85
            caps["reasoning"] = 0.75
            caps["coding"] = 0.05

        elif task_type == TaskType.GENERAL_REASONING:
            caps["general"] = 0.90
            caps["reasoning"] = 0.85
            caps["document_understanding"] = 0.60
            caps["mathematics"] = 0.30
            caps["tool_use"] = 0.40
            caps["coding"] = 0.05
            caps["vision"] = 0.05
            caps["ocr"] = 0.05

        return CapabilityVector.from_dict(caps)

    def _estimate_complexity(self, query: str, files: List[Dict[str, Any]], task_type: TaskType) -> float:
        score = 0.4
        words = len(query.split())

        if words > 50:
            score += 0.2
        elif words > 20:
            score += 0.1

        if files:
            score += min(0.3, len(files) * 0.15)

        if task_type in [TaskType.EQUIPMENT_APPROVAL, TaskType.ENGINEERING_CALCULATION]:
            score += 0.2
        elif task_type == TaskType.MEMO_SUMMARIZATION:
            score -= 0.1

        return round(max(0.1, min(1.0, score)), 2)

    def _determine_risk(self, task_type: TaskType, query: str, complexity: float) -> (RiskLevel, bool):
        # High Risk: Equipment operation approval, safety overrides, hazardous decisions, critical flow path & uncertainty analysis
        q_lower = query.lower()
        if task_type == TaskType.EQUIPMENT_APPROVAL or "approve" in q_lower or "continued operation" in q_lower:
            return RiskLevel.HIGH, True

        if task_type == TaskType.POLICY_COMPLIANCE and ("sil" in q_lower or "shutdown" in q_lower or "peso" in q_lower):
            return RiskLevel.HIGH, True

        if task_type == TaskType.MULTIMODAL_DOCUMENT_ANALYSIS and (
            "uncertainty" in q_lower or "flow path" in q_lower or "critical" in q_lower or "safety" in q_lower or "isolation" in q_lower
        ):
            return RiskLevel.HIGH, True

        # Medium Risk: Engineering calculations, code generation for production scripts, standard visual traces
        if task_type in [TaskType.ENGINEERING_CALCULATION, TaskType.CODING, TaskType.MULTIMODAL_DOCUMENT_ANALYSIS]:
            return RiskLevel.MEDIUM, False

        # Low Risk: Memo summarization, internal correspondence, general inquiries
        return RiskLevel.LOW, False
