import re
import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("mrpl.intent_router")


class UserIntent(str, Enum):
    QUESTION = "QUESTION"
    EXPLANATION = "EXPLANATION"
    CALCULATION = "CALCULATION"
    COMPARISON = "COMPARISON"
    SUMMARY = "SUMMARY"
    DOCUMENT_GENERATION = "DOCUMENT_GENERATION"
    PRESENTATION_GENERATION = "PRESENTATION_GENERATION"
    SPREADSHEET_GENERATION = "SPREADSHEET_GENERATION"
    CODE_GENERATION = "CODE_GENERATION"
    GENERIC_CODING = "GENERIC_CODING"
    ENGINEERING_CODING = "ENGINEERING_CODING"
    P_AND_ID_REASONING = "P_AND_ID_REASONING"
    MULTIMODAL_ANALYSIS = "MULTIMODAL_ANALYSIS"
    GENERAL_AGENT_TASK = "GENERAL_AGENT_TASK"


class OutputFormat(str, Enum):
    CHAT_ANSWER = "CHAT_ANSWER"
    DOCX = "DOCX"
    APPROVAL_NOTE = "APPROVAL_NOTE_DOCX"
    APPROVAL_NOTE_DOCX = "APPROVAL_NOTE_DOCX"
    PDF = "PDF"
    PPTX = "PPTX"
    XLSX = "XLSX"
    CODE_SANDBOX = "CODE_SANDBOX"
    CALCULATION_SHEET = "CALCULATION_SHEET"


class IntentDetectionResult(BaseModel):
    intent: UserIntent
    output_format: OutputFormat
    requires_rag: bool = True
    requires_calculation: bool = False
    requires_vision: bool = False
    requires_deliverable: bool = False
    target_entity: Optional[str] = None
    suggested_model: str = "qwen2.5-coder:3b"
    reasoning: str = ""


class IntentRouter:
    """
    Automatic Command Understanding & Intent Detection Layer for MRPL Studio.
    
    Interprets unified natural-language user queries to automatically infer:
    - User Intent (e.g. CALCULATION, DOCUMENT_GENERATION, COMPARISON, SUMMARY, etc.)
    - Output Format (e.g. CHAT_ANSWER, APPROVAL_NOTE_DOCX, DOCX, PPTX, XLSX, CODE_SANDBOX)
    - Required Tools (Engineering RAG, Deterministic Calculator, Vision Extractor, Document Generator)
    """

    @classmethod
    def detect_intent(
        cls,
        query: str,
        files: Optional[List[Dict[str, Any]]] = None,
        entity_tag: Optional[str] = None,
    ) -> IntentDetectionResult:
        q_lower = query.lower().strip()
        has_files = bool(files and len(files) > 0)
        has_images = has_files and any(
            f.get("type", "").startswith("image") or f.get("name", "").endswith((".png", ".jpg", ".jpeg", ".bmp"))
            for f in (files or [])
        )

        # 1. Check for Multimodal / Image Uploads
        if has_images or ("p&id" in q_lower and ("drawing" in q_lower or "diagram" in q_lower or "analyse" in q_lower or "analyze" in q_lower)):
            return IntentDetectionResult(
                intent=UserIntent.MULTIMODAL_ANALYSIS if has_images else UserIntent.P_AND_ID_REASONING,
                output_format=OutputFormat.CHAT_ANSWER,
                requires_rag=bool(entity_tag),
                requires_calculation=False,
                requires_vision=True,
                requires_deliverable=False,
                target_entity=entity_tag,
                suggested_model="qwen2.5vl:3b",
                reasoning="Multimodal diagram or vision OCR processing required."
            )

        # 2. Check for Explicit Approval Note / Document Generation
        if any(w in q_lower for w in [
            "approval note", "prepare an approval", "draft approval", "approval document", "approval for p-",
            "statutory approval", "review note"
        ]):
            return IntentDetectionResult(
                intent=UserIntent.DOCUMENT_GENERATION,
                output_format=OutputFormat.APPROVAL_NOTE_DOCX,
                requires_rag=True,
                requires_calculation=True,
                requires_vision=False,
                requires_deliverable=True,
                target_entity=entity_tag,
                suggested_model="qwen2.5-coder:3b",
                reasoning="User requested a formal PSU engineering approval note. Automatically assembling evidence into Draft Approval Note for human review."
            )

        # 3. Check for Explicit Presentation Generation ("presentation", "slides", "deck", "pptx")
        if any(w in q_lower for w in ["presentation", "slides", "slide deck", "deck", "powerpoint", "pptx", "create a presentation", "make a presentation"]):
            return IntentDetectionResult(
                intent=UserIntent.PRESENTATION_GENERATION,
                output_format=OutputFormat.PPTX,
                requires_rag=True,
                requires_calculation=True,
                requires_vision=False,
                requires_deliverable=True,
                target_entity=entity_tag,
                suggested_model="qwen3:4b",
                reasoning="User requested a presentation deck. Automatically synthesizing evidence into structured PPTX deliverable."
            )

        # 4. Check for Explicit Spreadsheet Generation ("excel", "spreadsheet", "xlsx", "csv", "table of measurements")
        if any(w in q_lower for w in ["excel", "spreadsheet", "xlsx", "sheet containing", "table of measurements", "excel sheet", "create a spreadsheet"]):
            return IntentDetectionResult(
                intent=UserIntent.SPREADSHEET_GENERATION,
                output_format=OutputFormat.XLSX,
                requires_rag=True,
                requires_calculation=True,
                requires_vision=False,
                requires_deliverable=True,
                target_entity=entity_tag,
                suggested_model="qwen2.5-coder:3b",
                reasoning="User requested a structured data spreadsheet. Automatically compiling inspection matrix into XLSX deliverable."
            )

        # 5. Check for General Technical Report / Document Generation ("report", "official report", "technical report", "docx", "pdf", "memo")
        if any(w in q_lower for w in [
            "create a report", "detailed report", "technical report", "official report", "generate docx", "generate report"
        ]):
            return IntentDetectionResult(
                intent=UserIntent.DOCUMENT_GENERATION,
                output_format=OutputFormat.DOCX,
                requires_rag=True,
                requires_calculation=True,
                requires_vision=False,
                requires_deliverable=True,
                target_entity=entity_tag,
                suggested_model="qwen3:4b",
                reasoning="User requested a formal engineering technical report. Automatically assembling evidence into DOCX deliverable."
            )

        # 5. Check for Code Generation ("write code", "python script", "code to calculate", "write python", "two sum", "csv parser", "function")
        is_coding_request = any(w in q_lower for w in [
            "write code", "python code", "python script", "write a script", "code to calculate", 
            "function to compute", "write python", "python function", "javascript function", 
            "csv parser", "two sum", "write a program", "explain this python code", "explain this code",
            "sort an array", "def "
        ]) or (files and any(f.get("name", "").endswith((".py", ".js", ".cpp", ".c", ".java")) for f in files))

        if is_coding_request:
            has_mrpl_evidence = bool(
                entity_tag 
                or any(k in q_lower for k in [
                    "v-201", "p-201", "tk-201", "c-101", "e-801", "e-101", "psv-201", "xv-201", "xv-203", "mov-204", "pcv-201", "y-201",
                    "mrpl datasheet", "datasheet", "inspection data", "inspection report", "thickness measurements from", "plant record", "mrpl record"
                ])
                or (files and any(f.get("name", "").endswith(".pdf") or "inspection" in f.get("name", "").lower() for f in files))
            )

            if has_mrpl_evidence:
                return IntentDetectionResult(
                    intent=UserIntent.ENGINEERING_CODING,
                    output_format=OutputFormat.CODE_SANDBOX,
                    requires_rag=True,
                    requires_calculation=True,
                    requires_vision=False,
                    requires_deliverable=False,
                    target_entity=entity_tag,
                    suggested_model="qwen2.5-coder:3b",
                    reasoning="MRPL engineering coding requested with specific plant entity/datasheet context. RAG retrieval and evidence architecture active."
                )
            else:
                return IntentDetectionResult(
                    intent=UserIntent.GENERIC_CODING,
                    output_format=OutputFormat.CODE_SANDBOX,
                    requires_rag=False,
                    requires_calculation=False,
                    requires_vision=False,
                    requires_deliverable=False,
                    target_entity=None,
                    suggested_model="qwen2.5-coder:3b",
                    reasoning="Generic programming task. RAG not required; local coding model knowledge used directly."
                )

        # 6. Check for Deterministic Calculation ("calculate", "compute", "corrosion rate", "remaining life", "wall thickness", "formula")
        if any(w in q_lower for w in ["calculate", "compute", "corrosion rate", "remaining life", "wall thickness calculation", "api 570 rate"]):
            return IntentDetectionResult(
                intent=UserIntent.CALCULATION,
                output_format=OutputFormat.CALCULATION_SHEET,
                requires_rag=True,
                requires_calculation=True,
                requires_vision=False,
                requires_deliverable=False,
                target_entity=entity_tag,
                suggested_model="qwen2.5-coder:3b",
                reasoning="Deterministic engineering calculation requested. Invoking Level-2 Python Arithmetic Engine."
            )

        # 7. Check for Comparison ("compare", "comparison", "difference between", "versus", "vs")
        if any(w in q_lower for w in ["compare", "comparison", "difference between", "versus", "vs 2024", "2019 and 2024"]):
            return IntentDetectionResult(
                intent=UserIntent.COMPARISON,
                output_format=OutputFormat.CHAT_ANSWER,
                requires_rag=True,
                requires_calculation=True,
                requires_vision=False,
                requires_deliverable=False,
                target_entity=entity_tag,
                suggested_model="qwen2.5-coder:3b",
                reasoning="Comparative multi-temporal inspection analysis requested."
            )

        # 8. Check for Summary ("summarize", "summary", "brief", "recap", "overview")
        if any(w in q_lower for w in ["summarize", "summary", "brief overview", "recap", "executive summary"]):
            return IntentDetectionResult(
                intent=UserIntent.SUMMARY,
                output_format=OutputFormat.CHAT_ANSWER,
                requires_rag=True,
                requires_calculation=False,
                requires_vision=False,
                requires_deliverable=False,
                target_entity=entity_tag,
                suggested_model="qwen3:4b",
                reasoning="Document synthesis and executive summary requested."
            )

        # 9. Check for Explanation ("explain", "why", "how does", "describe")
        if any(w in q_lower for w in ["explain", "how does", "describe", "maintenance history", "operating history"]):
            return IntentDetectionResult(
                intent=UserIntent.EXPLANATION,
                output_format=OutputFormat.CHAT_ANSWER,
                requires_rag=True,
                requires_calculation=False,
                requires_vision=False,
                requires_deliverable=False,
                target_entity=entity_tag,
                suggested_model="qwen3:4b",
                reasoning="Technical explanation and operational background requested."
            )

        # 10. Check for P&ID Topological Reasoning ("valve", "isolate", "discharge", "line number", "piping", "connected to")
        if any(w in q_lower for w in ["valve", "isolate", "discharge", "connected to", "flow path", "p&id"]):
            return IntentDetectionResult(
                intent=UserIntent.P_AND_ID_REASONING,
                output_format=OutputFormat.CHAT_ANSWER,
                requires_rag=True,
                requires_calculation=False,
                requires_vision=False,
                requires_deliverable=False,
                target_entity=entity_tag,
                suggested_model="qwen2.5-coder:3b",
                reasoning="P&ID graph connectivity and isolation reasoning requested."
            )

        # 11. Default: Standard Question / Factual Inquiry
        return IntentDetectionResult(
            intent=UserIntent.QUESTION,
            output_format=OutputFormat.CHAT_ANSWER,
            requires_rag=bool(entity_tag),
            requires_calculation=False,
            requires_vision=False,
            requires_deliverable=False,
            target_entity=entity_tag,
            suggested_model="qwen2.5-coder:3b",
            reasoning="Direct factual inquiry grounded in local MRPL Knowledge Base."
        )
