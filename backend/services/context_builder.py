import os
import mimetypes
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from backend.services.multimodal_processor import MultimodalFileProcessor, MultimodalDocument


class AttachedFile(BaseModel):
    name: str
    size: int = 0
    mime_type: str = "text/plain"
    extension: str = ""
    base64_data: Optional[str] = None
    preview_text: Optional[str] = None


class RequestContext(BaseModel):
    query: str
    files: List[AttachedFile] = Field(default_factory=list)
    documents: List[MultimodalDocument] = Field(default_factory=list)
    evidence_envelope: str = ""
    ingestion_trace: List[str] = Field(default_factory=list)
    risk_override: Optional[str] = None
    session_id: Optional[str] = None
    system_prompt_override: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def get_augmented_prompt(self) -> str:
        """
        Combines extracted multimodal evidence with user query and Evidence Authority Hierarchy.
        Ensures both Primary and Verifier models receive the real extracted evidence
        and adhere strictly to deterministic truth without contradicting verified facts.
        """
        if self.evidence_envelope:
            return (
                f"USER REQUEST:\n{self.query}\n\n"
                f"{self.evidence_envelope}\n\n"
                f"EVIDENCE AUTHORITY HIERARCHY & STRICT REASONING RULES:\n"
                f"• LEVEL 1 — VERIFIED STRUCTURED EXTRACTION: Highest authority for factual document values.\n"
                f"• LEVEL 2 — DETERMINISTIC CALCULATION: Highest authority for arithmetic & engineering values.\n"
                f"• LEVEL 3 — FORMULA REGISTRY: Highest authority for equations & applicability metadata.\n"
                f"• LEVEL 4 — VISION MODEL: Visual interpretation and diagram understanding.\n"
                f"• LEVEL 5 — LLM REASONING: Explanations only. LLM MUST NEVER override Levels 1–3.\n\n"
                f"MANDATORY CONSTRAINTS:\n"
                f"1. Once a value is extracted and verified (e.g. Previous thickness, Current thickness, Interval), DO NOT state that it is missing.\n"
                f"2. Cite exact page provenance: 'Previous thickness: 6.0 mm — verified from Page 1.'\n"
                f"3. Note on historical records: 'Previous and current thickness values required for this calculation are present in the supplied document. Additional historical inspection records beyond these values are not established.'\n"
                f"4. DO NOT compare corrosion rate (mm/year) numerically against minimum allowable thickness threshold (mm). Report thickness margin (mm) and corrosion rate (mm/year) separately.\n"
                f"5. Final operational governance remains HUMAN ENGINEERING REVIEW REQUIRED per refinery safety policy."
            )
        return self.query


class RequestContextBuilder:
    """
    Transforms raw incoming HTTP payloads into a sanitized, validated RequestContext
    with full multimodal extraction, OCR, and diagram vision processing.
    """

    _processor = MultimodalFileProcessor()

    @classmethod
    def set_ollama_adapter(cls, adapter):
        cls._processor = MultimodalFileProcessor(ollama_adapter=adapter)

    @classmethod
    def build_context(
        cls,
        query: str,
        files: Optional[List[Dict[str, Any]]] = None,
        risk_override: Optional[str] = None,
        session_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> RequestContext:
        parsed_files: List[AttachedFile] = []
        parsed_documents: List[MultimodalDocument] = []
        ingestion_trace: List[str] = []

        if files:
            for f in files:
                name = f.get("name", "unnamed_file")
                ext = os.path.splitext(name)[1].lower()
                size = f.get("size", 0)
                b64 = f.get("base64") or f.get("content") or f.get("base64_data") or f.get("data")
                if b64 and isinstance(b64, str) and "," in b64:
                    b64 = b64.split(",", 1)[1]

                mime = f.get("type") or mimetypes.guess_type(name)[0] or "application/octet-stream"

                attached = AttachedFile(
                    name=name,
                    size=size,
                    mime_type=mime,
                    extension=ext,
                    base64_data=b64,
                    preview_text=f.get("preview"),
                )
                parsed_files.append(attached)

                # Process file content through Multimodal Processor
                try:
                    doc = cls._processor.process_file(
                        name=name,
                        base64_data=b64,
                        query_context=query,
                    )
                    parsed_documents.append(doc)
                    ingestion_trace.extend(doc.processing_trace)
                except Exception as e:
                    ingestion_trace.append(f"FILE PROCESSING FAILED on {name}: {e}")

        evidence_envelope = MultimodalFileProcessor.format_evidence_envelope(parsed_documents)

        return RequestContext(
            query=query.strip(),
            files=parsed_files,
            documents=parsed_documents,
            evidence_envelope=evidence_envelope,
            ingestion_trace=ingestion_trace,
            risk_override=risk_override,
            session_id=session_id,
            system_prompt_override=system_prompt,
        )
