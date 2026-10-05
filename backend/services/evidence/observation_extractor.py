# backend/services/evidence/observation_extractor.py
"""
MRPL Sovereign AI Workbench — Phase 3A: Source-Grounded Evidence Observation Extractor.
Transforms retrieved chunks, structured JSON records, and document excerpts into
high-fidelity, source-grounded EvidenceObservation instances.

Key Architectural Guarantees:
- Strict Source Fidelity: Raw statements and values are preserved verbatim (no averaging or invention).
- Deterministic Identity: Observation IDs are stably generated from source provenance coordinates.
- Safe Degradation: Unstated fields degrade to None / UNKNOWN rather than guessing.
- Malformed Input Resiliency: Invalid inputs populate MalformedObservationRecord without crashing.
"""

import re
import json
import hashlib
import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from backend.services.evidence.reconciliation_models import (
    AuthorityTier,
    ApprovalStatus,
    ExtractionMethod,
    EvidenceObservation,
    MalformedObservationRecord,
    ObservationExtractionResult,
)

logger = logging.getLogger("mrpl.evidence.observation_extractor")


class EvidenceObservationExtractor:
    """
    Source-grounded observation extraction engine for MRPL industrial evidence.
    Extracts atomic engineering observations from structured JSON, table representations,
    and text excerpts with complete provenance retention.
    """

    # Tag pattern: P-201, TK-201, PSV-201, XV-203, V-201, C-101, E-101, etc.
    ENTITY_TAG_PATTERN = re.compile(
        r"\b(?:P|TK|T|E|C|V|XV|CV|DV|PCV|PSV|PI|TI|PG|TE|PIC|K|R|F|S|MOC|WO|SOP)\-[0-9]{2,4}[A-Z]?\b",
        re.IGNORECASE,
    )

    # Date pattern: ISO 8601 YYYY-MM-DD or DD-Mon-YYYY or DD/MM/YYYY
    ISO_DATE_PATTERN = re.compile(r"\b(20[0-9]{2}-[0-1][0-9]-[0-3][0-9])\b")
    TEXT_DATE_PATTERN = re.compile(r"\b([0-3]?[0-9][\s\-\/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-\/]20[0-9]{2})\b", re.IGNORECASE)

    # Common physical property patterns
    PROPERTY_PATTERNS = [
        ("wall_thickness", re.compile(r"(?:current|measured|actual|original|nominal|design|min(?:imum)? allowable)?\s*(?:wall\s+)?thickness\s*(?:at\s+([A-Z0-9\-]+))?\s*[:=]\s*([0-9]+(?:\.[0-9]+)?(?:\s*(?:-|to)\s*[0-9]+(?:\.[0-9]+)?)?)\s*(mm|cm|in|inch(?:es)?)?", re.IGNORECASE)),
        ("vibration_velocity_rms", re.compile(r"(?:overall\s+)?vibration(?:\s+(?:velocity|rms))?\s*[:=]\s*([0-9]+(?:\.[0-9]+)?(?:\s*(?:-|to)\s*[0-9]+(?:\.[0-9]+)?)?)\s*(mm/s|mms|in/s)?", re.IGNORECASE)),
        ("design_pressure", re.compile(r"(?:design|operating|working|set)?\s*pressure\s*[:=]\s*([0-9]+(?:\.[0-9]+)?(?:\s*(?:-|to)\s*[0-9]+(?:\.[0-9]+)?)?)\s*(bar|barg|psi|psig|kpa|mpa)?", re.IGNORECASE)),
        ("operating_temperature", re.compile(r"(?:design|operating|working)?\s*temperature\s*[:=]\s*([0-9]+(?:\.[0-9]+)?(?:\s*(?:-|to)\s*[0-9]+(?:\.[0-9]+)?)?)\s*(°C|C|°F|F|K)?", re.IGNORECASE)),
        ("corrosion_rate", re.compile(r"(?:measured\s+)?corrosion\s*rate\s*[:=]\s*([0-9]+(?:\.[0-9]+)?(?:\s*(?:-|to)\s*[0-9]+(?:\.[0-9]+)?)?)\s*(mm/year|mm/yr|mpy)?", re.IGNORECASE)),
    ]

    @classmethod
    def generate_observation_id(
        cls,
        document_id: Optional[str],
        source_document: str,
        page_number: int,
        entity_tag: str,
        property_name: str,
        measurement_location: Optional[str] = None,
        raw_statement: str = "",
    ) -> str:
        """
        Generates a deterministic observation ID based on source coordinates and content.
        Reprocessing the identical source excerpt yields the identical ID.
        """
        norm_entity = (entity_tag or "UNKNOWN").upper().strip()
        norm_prop = (property_name or "GENERIC").lower().strip().replace(" ", "_")
        
        # Build stable seed
        seed_components = [
            str(document_id or ""),
            str(source_document or ""),
            str(page_number or 1),
            str(norm_entity),
            str(norm_prop),
            str(measurement_location or ""),
            str(raw_statement or "").strip(),
        ]
        seed_str = "||".join(seed_components)
        digest = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8].upper()
        
        # Clean entity tag for identifier format
        clean_tag = re.sub(r"[^A-Z0-9]", "", norm_entity)
        clean_prop = re.sub(r"[^A-Z0-9]", "", norm_prop.upper())[:8]
        
        return f"OBS-{clean_tag}-{clean_prop}-{digest}"

    @classmethod
    def map_authority_tier(cls, raw_tier: Any, doc_name: str = "") -> AuthorityTier:
        """
        Determines AuthorityTier from explicit field or document filename.
        Defaults to UNKNOWN if not determinable without guessing.
        """
        if isinstance(raw_tier, AuthorityTier):
            return raw_tier
        if isinstance(raw_tier, str):
            raw_upper = raw_tier.strip().upper()
            if raw_upper in AuthorityTier.__members__:
                return AuthorityTier[raw_upper]
            # Map legacy Phase 1/2 AuthorityLevel
            if raw_upper in ("A", "APPROVED_AUTHORITATIVE", "STATUTORY"):
                return AuthorityTier.APPROVED_AUTHORITATIVE
            if raw_upper in ("B", "APPROVED", "STANDARDS"):
                return AuthorityTier.APPROVED
            if raw_upper in ("C", "INTERNAL", "LOGS"):
                return AuthorityTier.INTERNAL
            if raw_upper in ("D", "E", "INFORMAL", "SCRATCHPAD"):
                return AuthorityTier.INFORMAL

        # Check document filename patterns deterministically
        doc_lower = (doc_name or "").lower()
        if any(doc_lower.startswith(p) for p in ["mrpl-insp-", "mrpl-ds-", "mrpl-eh-", "mrpl-iso-", "mrpl-moc-"]):
            return AuthorityTier.APPROVED_AUTHORITATIVE
        if any(s in doc_lower for s in ["api", "asme", "oisd", "iso", "astm"]):
            return AuthorityTier.APPROVED

        return AuthorityTier.UNKNOWN

    @classmethod
    def map_approval_status(cls, raw_status: Any) -> ApprovalStatus:
        """
        Maps raw approval status string to ApprovalStatus enum.
        Defaults to UNKNOWN if unstated.
        """
        if isinstance(raw_status, ApprovalStatus):
            return raw_status
        if isinstance(raw_status, str):
            raw_upper = raw_status.strip().upper()
            if raw_upper in ApprovalStatus.__members__:
                return ApprovalStatus[raw_upper]
            if raw_upper in ("CURRENT_APPROVED", "APPROVED", "SIGNED_OFF"):
                return ApprovalStatus.APPROVED
            if raw_upper in ("DRAFT", "PROPOSED"):
                return ApprovalStatus.DRAFT
            if raw_upper in ("SUPERSEDED", "RETIRED"):
                return ApprovalStatus.SUPERSEDED
            if raw_upper in ("PENDING_MOC", "UNDER_REVIEW"):
                return ApprovalStatus.PENDING_MOC

        return ApprovalStatus.UNKNOWN

    @classmethod
    def extract_from_dict(
        cls,
        data: Dict[str, Any],
        default_document: str = "structured_input.json",
    ) -> ObservationExtractionResult:
        """
        Extracts observations from a structured dictionary or JSON record.
        Handles both single-observation dicts and multi-observation/KB master documents.
        """
        result = ObservationExtractionResult()
        
        if not isinstance(data, dict):
            result.malformed_records.append(
                MalformedObservationRecord(
                    raw_input=data,
                    error_reason="Input data is not a dictionary.",
                )
            )
            return result

        # Check if this is already an observation-like schema
        if "property_name" in data or ("value" in data and "entity_tag" in data):
            obs, err = cls._validate_and_build_observation(data, default_document)
            if obs:
                result.observations.append(obs)
                result.total_extracted += 1
            elif err:
                result.malformed_records.append(err)
            return result

        # Multi-property KB document or inspection report structure
        entity_tag = data.get("equipment_tag") or data.get("tag") or data.get("entity_tag")
        source_doc = data.get("source_document") or data.get("document") or data.get("document_name") or default_document
        doc_id = data.get("document_id") or data.get("id")
        doc_type = data.get("document_type") or data.get("category") or "General"
        page_num = data.get("page_number") or data.get("page") or 1
        obs_date = data.get("date") or data.get("observation_date") or data.get("inspection_date")
        rev_num = data.get("revision") or data.get("revision_number")
        auth_tier = cls.map_authority_tier(data.get("authority_tier") or data.get("authority_level"), str(source_doc))
        appr_status = cls.map_approval_status(data.get("approval_status") or data.get("revision_status"))

        # Extract nested inspection or specification readings
        extracted_any = False

        # Check inspection_history or history arrays
        history_records = data.get("inspection_history") or data.get("history") or data.get("thickness_surveys")
        if isinstance(history_records, list):
            for rec in history_records:
                if isinstance(rec, dict):
                    rec_tag = rec.get("equipment_tag") or entity_tag
                    rec_date = rec.get("date") or rec.get("survey_date") or obs_date
                    rec_loc = rec.get("cml") or rec.get("cml_id") or rec.get("measurement_location") or rec.get("location")
                    rec_method = rec.get("method") or rec.get("measurement_method")
                    
                    for prop_key, prop_val in rec.items():
                        if prop_key in ("date", "survey_date", "cml", "cml_id", "measurement_location", "location", "method", "equipment_tag", "remarks"):
                            continue
                        if prop_val is not None:
                            stmt = rec.get("remarks") or f"{prop_key}: {prop_val} (Location: {rec_loc or 'Unstated'})"
                            raw_dict = {
                                "entity_tag": rec_tag,
                                "property_name": prop_key,
                                "value": prop_val,
                                "measurement_location": rec_loc,
                                "measurement_method": rec_method,
                                "observation_date": rec_date,
                                "source_document": source_doc,
                                "document_id": doc_id,
                                "document_type": doc_type,
                                "page_number": page_num,
                                "revision_number": rev_num,
                                "authority_tier": auth_tier,
                                "approval_status": appr_status,
                                "extraction_method": ExtractionMethod.STRUCTURED_JSON,
                                "raw_statement": stmt,
                            }
                            obs, err = cls._validate_and_build_observation(raw_dict, str(source_doc))
                            if obs:
                                result.observations.append(obs)
                                result.total_extracted += 1
                                extracted_any = True
                            elif err:
                                result.malformed_records.append(err)

        # Check key-value specifications
        spec_dict = data.get("specifications") or data.get("key_properties") or data.get("design_parameters")
        if isinstance(spec_dict, dict):
            for k, v in spec_dict.items():
                if v is not None:
                    raw_dict = {
                        "entity_tag": entity_tag,
                        "property_name": k,
                        "value": v,
                        "observation_date": obs_date,
                        "source_document": source_doc,
                        "document_id": doc_id,
                        "document_type": doc_type,
                        "page_number": page_num,
                        "revision_number": rev_num,
                        "authority_tier": auth_tier,
                        "approval_status": appr_status,
                        "extraction_method": ExtractionMethod.STRUCTURED_JSON,
                        "raw_statement": f"{k}: {v}",
                    }
                    obs, err = cls._validate_and_build_observation(raw_dict, str(source_doc))
                    if obs:
                        result.observations.append(obs)
                        result.total_extracted += 1
                        extracted_any = True
                    elif err:
                        result.malformed_records.append(err)

        # If data is a top-level flat dict and entity_tag is present
        if not extracted_any and entity_tag:
            for k, v in data.items():
                if k in ("equipment_tag", "tag", "entity_tag", "source_document", "document", "document_id", "document_type", "category", "page_number", "page", "date", "observation_date", "revision", "revision_number", "authority_tier", "authority_level", "approval_status", "revision_status"):
                    continue
                if isinstance(v, (int, float, str, bool)):
                    raw_dict = {
                        "entity_tag": entity_tag,
                        "property_name": k,
                        "value": v,
                        "observation_date": obs_date,
                        "source_document": source_doc,
                        "document_id": doc_id,
                        "document_type": doc_type,
                        "page_number": page_num,
                        "revision_number": rev_num,
                        "authority_tier": auth_tier,
                        "approval_status": appr_status,
                        "extraction_method": ExtractionMethod.STRUCTURED_JSON,
                        "raw_statement": f"{k}: {v}",
                    }
                    obs, err = cls._validate_and_build_observation(raw_dict, str(source_doc))
                    if obs:
                        result.observations.append(obs)
                        result.total_extracted += 1
                    elif err:
                        result.malformed_records.append(err)

        if result.total_extracted == 0 and not result.malformed_records:
            result.warnings.append(f"No valid observations extracted from record in document {source_doc}.")

        return result

    @classmethod
    def extract_from_chunk(
        cls,
        chunk: Any,
        default_document: str = "retrieved_chunk.txt",
    ) -> ObservationExtractionResult:
        """
        Extracts observations from a RetrievedChunk, dictionary chunk, or raw text chunk.
        Uses deterministic regex parsing while preserving verbatim statements.
        """
        result = ObservationExtractionResult()

        if chunk is None:
            result.malformed_records.append(
                MalformedObservationRecord(
                    raw_input=None,
                    error_reason="Chunk is None.",
                )
            )
            return result

        # Extract text and provenance safely
        text = ""
        source_doc = default_document
        doc_id = None
        doc_type = "General"
        page_num = 1
        section = "General"
        obs_date = None
        entity_tag = None
        auth_tier = AuthorityTier.UNKNOWN
        appr_status = ApprovalStatus.UNKNOWN
        rev_num = None

        if hasattr(chunk, "text"):
            text = getattr(chunk, "text", "") or ""
            src = getattr(chunk, "source", None)
            if src:
                source_doc = getattr(src, "document", default_document) or default_document
                doc_id = getattr(src, "document_id", None)
                doc_type = getattr(src, "document_type", "General") or "General"
                page_num = getattr(src, "page", 1) or 1
                section = getattr(src, "section", "General") or "General"
                obs_date = getattr(src, "date", None)
                entity_tag = getattr(src, "equipment_tag", None)
            auth_tier = cls.map_authority_tier(getattr(chunk, "authority_level", None), str(source_doc))
        elif isinstance(chunk, dict):
            text = chunk.get("text") or chunk.get("content") or ""
            src_dict = chunk.get("source")
            if isinstance(src_dict, dict):
                source_doc = src_dict.get("document", default_document) or default_document
                doc_id = src_dict.get("document_id")
                doc_type = src_dict.get("document_type", "General") or "General"
                page_num = src_dict.get("page", 1) or 1
                section = src_dict.get("section", "General") or "General"
                obs_date = src_dict.get("date")
                entity_tag = src_dict.get("equipment_tag")
            else:
                source_doc = chunk.get("filename") or chunk.get("source_document") or default_document
                doc_id = chunk.get("document_id")
                page_num = chunk.get("page", 1) or 1
                section = chunk.get("section", "General") or "General"
                obs_date = chunk.get("date") or chunk.get("observation_date")
                entity_tag = chunk.get("equipment_tag") or chunk.get("tag")

            auth_tier = cls.map_authority_tier(chunk.get("authority_tier") or chunk.get("authority_level"), str(source_doc))
            appr_status = cls.map_approval_status(chunk.get("approval_status") or chunk.get("revision_status"))
            rev_num = chunk.get("revision") or chunk.get("revision_number")
        else:
            text = str(chunk)

        if not text.strip():
            result.malformed_records.append(
                MalformedObservationRecord(
                    raw_input=chunk,
                    error_reason="Chunk text is empty.",
                    source_document=str(source_doc),
                )
            )
            return result

        # 1. Resolve entity tag if missing from metadata
        if not entity_tag:
            match_entity = cls.ENTITY_TAG_PATTERN.search(text)
            if match_entity:
                entity_tag = match_entity.group(0).upper()

        if not entity_tag:
            result.warnings.append(f"No equipment/entity tag found in chunk from {source_doc}.")
            return result

        # 2. Check for date in text if not in metadata
        if not obs_date:
            m_iso = cls.ISO_DATE_PATTERN.search(text)
            if m_iso:
                obs_date = m_iso.group(1)
            else:
                m_txt_date = cls.TEXT_DATE_PATTERN.search(text)
                if m_txt_date:
                    obs_date = m_txt_date.group(1)

        # 3. Deterministic Extraction of properties via regex
        for prop_name, regex in cls.PROPERTY_PATTERNS:
            for match in regex.finditer(text):
                raw_match_stmt = match.group(0).strip()
                groups = match.groups()
                
                # Extract groups based on pattern structure
                val_raw = None
                unit_raw = None
                loc_raw = None

                if prop_name == "wall_thickness":
                    loc_raw = groups[0]  # Optional CML point (e.g. CML-01)
                    val_raw = groups[1]
                    unit_raw = groups[2] if len(groups) > 2 else "mm"
                else:
                    val_raw = groups[0]
                    unit_raw = groups[1] if len(groups) > 1 else None

                # Value conversion: preserve numerical value or range string
                parsed_val: Any = val_raw
                if val_raw:
                    val_clean = val_raw.strip()
                    if "-" in val_clean or " to " in val_clean.lower():
                        # Preserve exact range representation without averaging!
                        parsed_val = val_clean
                    else:
                        try:
                            parsed_val = float(val_clean)
                        except ValueError:
                            parsed_val = val_clean

                # Check if there is a CML mentioned nearby in text
                if not loc_raw:
                    m_cml = re.search(r"\b(CML\-[0-9]{2}(?:\s+[A-Za-z0-9]+)?)\b", text, re.IGNORECASE)
                    if m_cml:
                        loc_raw = m_cml.group(1)

                raw_dict = {
                    "entity_tag": entity_tag,
                    "property_name": prop_name,
                    "value": parsed_val,
                    "unit": unit_raw,
                    "measurement_location": loc_raw,
                    "observation_date": obs_date,
                    "source_document": source_doc,
                    "document_id": doc_id,
                    "document_type": doc_type,
                    "page_number": int(page_num) if str(page_num).isdigit() else 1,
                    "section": section,
                    "revision_number": rev_num,
                    "authority_tier": auth_tier,
                    "approval_status": appr_status,
                    "extraction_method": ExtractionMethod.REGEX_PARSER,
                    "raw_statement": raw_match_stmt,
                    "source_span": f"char:{match.start()}-{match.end()}",
                }

                obs, err = cls._validate_and_build_observation(raw_dict, str(source_doc))
                if obs:
                    result.observations.append(obs)
                    result.total_extracted += 1
                elif err:
                    result.malformed_records.append(err)

        return result

    @classmethod
    def extract_from_sources(
        cls,
        sources: List[Any],
        default_document: str = "batch_input",
    ) -> ObservationExtractionResult:
        """
        Batch extractor accepting a heterogeneous list of chunks, dicts, or strings.
        """
        combined = ObservationExtractionResult()

        for idx, src in enumerate(sources):
            if isinstance(src, dict):
                sub_res = cls.extract_from_dict(src, default_document=f"{default_document}_{idx}")
            else:
                sub_res = cls.extract_from_chunk(src, default_document=f"{default_document}_{idx}")

            combined.observations.extend(sub_res.observations)
            combined.malformed_records.extend(sub_res.malformed_records)
            combined.warnings.extend(sub_res.warnings)
            combined.total_extracted += sub_res.total_extracted

        return combined

    @classmethod
    def _validate_and_build_observation(
        cls,
        data: Dict[str, Any],
        source_doc_fallback: str,
    ) -> tuple[Optional[EvidenceObservation], Optional[MalformedObservationRecord]]:
        """
        Validates observation fields deterministically and returns either
        (EvidenceObservation, None) or (None, MalformedObservationRecord).
        """
        try:
            entity_tag = data.get("entity_tag") or data.get("equipment_tag") or data.get("tag")
            property_name = data.get("property_name")
            raw_statement = data.get("raw_statement")
            value = data.get("value")

            # Validation 1: Entity Tag presence
            if not entity_tag or not str(entity_tag).strip():
                return None, MalformedObservationRecord(
                    raw_input=data,
                    error_reason="Missing or empty entity_tag.",
                    source_document=str(data.get("source_document", source_doc_fallback)),
                )

            # Validation 2: Property Name presence
            if not property_name or not str(property_name).strip():
                return None, MalformedObservationRecord(
                    raw_input=data,
                    error_reason="Missing or empty property_name.",
                    source_document=str(data.get("source_document", source_doc_fallback)),
                    entity_tag=str(entity_tag),
                )

            # Validation 3: Raw Statement presence (Critical Source-Fidelity invariant)
            if not raw_statement or not str(raw_statement).strip():
                return None, MalformedObservationRecord(
                    raw_input=data,
                    error_reason="Missing verbatim raw_statement in source observation.",
                    source_document=str(data.get("source_document", source_doc_fallback)),
                    entity_tag=str(entity_tag),
                )

            # Validation 4: Value presence (Value must not be None unless explicitly supported)
            if value is None:
                return None, MalformedObservationRecord(
                    raw_input=data,
                    error_reason="Observation value cannot be None.",
                    source_document=str(data.get("source_document", source_doc_fallback)),
                    entity_tag=str(entity_tag),
                )

            # Validation 5: Page Number must be valid integer >= 1
            page_raw = data.get("page_number", 1)
            try:
                page_num = int(page_raw)
                if page_num < 1:
                    page_num = 1
            except (ValueError, TypeError):
                page_num = 1

            source_doc = str(data.get("source_document") or source_doc_fallback)
            measurement_loc = data.get("measurement_location")
            if measurement_loc:
                measurement_loc = str(measurement_loc).strip()

            # Generate or validate observation_id
            obs_id = data.get("observation_id")
            if not obs_id:
                obs_id = cls.generate_observation_id(
                    document_id=data.get("document_id"),
                    source_document=source_doc,
                    page_number=page_num,
                    entity_tag=str(entity_tag),
                    property_name=str(property_name),
                    measurement_location=measurement_loc,
                    raw_statement=str(raw_statement),
                )

            # Build validated model
            observation = EvidenceObservation(
                observation_id=obs_id,
                entity_tag=str(entity_tag).strip().upper(),
                property_name=str(property_name).strip(),
                value=value,
                unit=data.get("unit"),
                measurement_location=measurement_loc or None,
                measurement_method=data.get("measurement_method") or None,
                observation_date=data.get("observation_date") or None,
                source_document=source_doc,
                document_id=data.get("document_id") or None,
                document_type=data.get("document_type") or "General",
                page_number=page_num,
                section=data.get("section") or "General",
                source_span=data.get("source_span") or None,
                revision_number=data.get("revision_number") or None,
                approval_status=cls.map_approval_status(data.get("approval_status", ApprovalStatus.UNKNOWN)),
                authority_tier=cls.map_authority_tier(data.get("authority_tier", AuthorityTier.UNKNOWN), source_doc),
                extraction_method=data.get("extraction_method", ExtractionMethod.STRUCTURED_JSON),
                raw_statement=str(raw_statement).strip(),
            )

            return observation, None

        except Exception as e:
            return None, MalformedObservationRecord(
                raw_input=data,
                error_reason=f"Pydantic / Validation Exception: {str(e)}",
                source_document=str(data.get("source_document", source_doc_fallback)),
            )
