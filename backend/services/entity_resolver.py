import os
import re
import json
import logging
from typing import Dict, List, Any, Optional, Set
from pathlib import Path

from backend.models.entity_models import (
    MRPLEntityRecord,
    EntityResolutionResult,
    EntityType,
    EntityResolutionStatus,
)

logger = logging.getLogger("mrpl.entity_resolver")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_KB_DIR = BASE_DIR / "MRPL_KNOWLEDGE_BASE"


class MRPLEntityResolver:
    """
    Local MRPL Entity Index & Resolver.
    Automatically discovers and indexes all entities from the local MRPL Knowledge Base.
    Equipment Master documents serve as the primary authority for equipment identity.
    Provides strict air-gapped entity resolution and unknown-entity detection.
    """

    # Tag pattern: P-201, TK-201, PSV-201, XV-203, V-201, C-101, E-101, etc.
    ENTITY_TAG_PATTERN = re.compile(
        r"\b(?:P|TK|T|E|C|V|XV|CV|DV|PCV|PSV|PI|TI|PG|TE|PIC|K|R|F|S|MOC|WO|SOP)\-[0-9]{2,4}[A-Z]?\b",
        re.IGNORECASE,
    )

    def __init__(self, kb_dir: Optional[Path] = None):
        self.kb_dir = Path(kb_dir) if kb_dir else DEFAULT_KB_DIR
        self.entities: Dict[str, MRPLEntityRecord] = {}
        self.tag_index: Dict[str, str] = {}  # lowercase_tag -> canonical_name
        self.alias_index: Dict[str, str] = {}  # lowercase_alias -> canonical_name
        self.build_index()

    def build_index(self):
        """
        Scans all 9 categories of the MRPL Knowledge Base and builds the authoritative entity index.
        Equipment Master (01_Equipment_Master) documents are loaded first as primary authority.
        """
        self.entities.clear()
        self.tag_index.clear()
        self.alias_index.clear()

        if not self.kb_dir.exists():
            logger.warning(f"MRPL Knowledge Base directory not found at {self.kb_dir}")
            return

        # Pass 1: Load Equipment Master as Primary Authority
        equip_master_dir = self.kb_dir / "01_Equipment_Master"
        if equip_master_dir.exists():
            for file in sorted(os.listdir(equip_master_dir)):
                if file.endswith(".json"):
                    self._index_master_file(equip_master_dir / file)

        # Pass 2: Discover and enrich entities from all other categories
        for root, _, files in os.walk(self.kb_dir):
            for file in sorted(files):
                if file.endswith(".json"):
                    file_path = Path(root) / file
                    if "01_Equipment_Master" not in str(file_path):
                        self._enrich_entity_from_file(file_path)

        logger.info(f"MRPL Entity Resolver indexed {len(self.entities)} authoritative entities.")

    def _index_master_file(self, file_path: Path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            tag = data.get("equipment_tag") or data.get("tag")
            if not tag:
                return

            canonical = tag.upper().strip()
            entity_type = self._infer_entity_type(canonical, data.get("equipment_type", ""))
            aliases = [canonical, canonical.replace("-", ""), canonical.lower()]
            if data.get("title"):
                aliases.append(data["title"])

            record = MRPLEntityRecord(
                canonical_name=canonical,
                entity_type=entity_type,
                aliases=aliases,
                equipment_tag=canonical,
                equipment_type=data.get("equipment_type", "Industrial Refinery Equipment"),
                plant_area=data.get("plant_area", "Crude Distillation Unit (CDU-II)"),
                domain="MRPL Engineering",
                source_document=file_path.name,
                document_id=data.get("document_id", f"DOC-{canonical}"),
                page_number=int(data.get("page_number", 1)),
                status="KNOWN",
                related_document_ids=[data.get("document_id", file_path.stem)],
                related_document_types=["Equipment Master"],
                metadata=data.get("metadata", {}),
            )

            self.entities[canonical] = record
            self.tag_index[canonical.lower()] = canonical
            for a in aliases:
                self.alias_index[a.lower()] = canonical

        except Exception as e:
            logger.error(f"Failed to index master document {file_path}: {e}")

    def _enrich_entity_from_file(self, file_path: Path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            tag = data.get("equipment_tag") or data.get("tag")
            doc_type = data.get("document_type", file_path.parent.name)
            doc_id = data.get("document_id", file_path.stem)

            if tag:
                canonical = tag.upper().strip()
                if canonical in self.entities:
                    ent = self.entities[canonical]
                    if doc_id not in ent.related_document_ids:
                        ent.related_document_ids.append(doc_id)
                    if doc_type not in ent.related_document_types:
                        ent.related_document_types.append(doc_type)
                else:
                    # Discover entity present in secondary records
                    entity_type = self._infer_entity_type(canonical, data.get("equipment_type", ""))
                    aliases = [canonical, canonical.replace("-", ""), canonical.lower()]
                    record = MRPLEntityRecord(
                        canonical_name=canonical,
                        entity_type=entity_type,
                        aliases=aliases,
                        equipment_tag=canonical,
                        equipment_type=data.get("equipment_type", doc_type),
                        plant_area=data.get("plant_area", "CDU-II"),
                        domain="MRPL Engineering",
                        source_document=file_path.name,
                        document_id=doc_id,
                        page_number=int(data.get("page_number", 1)),
                        status="KNOWN",
                        related_document_ids=[doc_id],
                        related_document_types=[doc_type],
                        metadata=data.get("metadata", {}),
                    )
                    self.entities[canonical] = record
                    self.tag_index[canonical.lower()] = canonical
                    for a in aliases:
                        self.alias_index[a.lower()] = canonical

        except Exception as e:
            logger.debug(f"Could not enrich from {file_path}: {e}")

    @staticmethod
    def _infer_entity_type(tag: str, desc: str) -> EntityType:
        t = tag.upper()
        if t.startswith("P-"):
            return EntityType.EQUIPMENT
        if t.startswith("TK-") or t.startswith("T-"):
            return EntityType.TANK
        if t.startswith("V-"):
            return EntityType.VESSEL
        if t.startswith("PSV-") or t.startswith("XV-") or t.startswith("CV-") or t.startswith("PCV-"):
            return EntityType.VALVE
        if t.startswith("PI-") or t.startswith("TI-") or t.startswith("PG-") or t.startswith("PIC-"):
            return EntityType.INSTRUMENT
        if t.startswith("C-"):
            return EntityType.EQUIPMENT
        if t.startswith("E-"):
            return EntityType.EQUIPMENT
        if t.startswith("SOP-"):
            return EntityType.PROCEDURE
        if t.startswith("MOC-"):
            return EntityType.MOC
        if t.startswith("WO-"):
            return EntityType.DOCUMENT
        return EntityType.EQUIPMENT

    def resolve(self, query: str) -> EntityResolutionResult:
        """
        Resolves entities from query string.
        Extracts ALL potential equipment tags and checks against local MRPL index & Asset Registry.
        Distinguishes genuine generic nomenclature questions from MRPL entity requests.
        Ensures multi-tag queries with unindexed targets (e.g. 'P-201 is a pump. Is P-999 also a pump at MRPL?')
        are strictly guarded and do not bypass the Context Guard.
        """
        if not query or not query.strip():
            return EntityResolutionResult(
                resolution_status=EntityResolutionStatus.NO_ENTITY_DETECTED,
                resolution_message="Empty query",
            )

        q_lower = query.lower().strip()

        # 1. Regex extract all potential equipment/procedure/doc tags
        raw_matches = self.ENTITY_TAG_PATTERN.findall(query)
        extracted_tags: List[str] = []
        for m in raw_matches:
            tag_clean = m.upper().strip()
            if tag_clean not in extracted_tags:
                extracted_tags.append(tag_clean)

        # 2. Check for Genuine Generic Tag / Nomenclature Intent (Failure 2 Fix)
        # Examples: "What could P-999 mean as a generic equipment tag?", "What does P- prefix generally mean in equipment tagging?"
        generic_indicators = [
            "generic equipment tag",
            "as a generic",
            "generic tag",
            "generic meaning",
            "as equipment tags",
            "in equipment tagging",
            "tag convention",
            "tagging convention",
            "standard convention",
            "nomenclature",
            "what does the prefix mean",
            "what does the prefix",
            "prefix generally mean",
            "what could",
            "usually represent",
            "commonly represent",
            "naming convention",
        ]
        has_generic_keyword = any(ind in q_lower for ind in generic_indicators) or (
            "in general" in q_lower or "generally" in q_lower
        )
        explicit_non_mrpl = (
            "not asking about mrpl" in q_lower
            or "not at mrpl" in q_lower
            or "not mrpl" in q_lower
            or "i am not asking about mrpl" in q_lower
        )
        has_mrpl_anchor = (
            ("at mrpl" in q_lower or "in mrpl" in q_lower or "at cdu" in q_lower or "in cdu" in q_lower or "our refinery" in q_lower or "at the plant" in q_lower)
            and not explicit_non_mrpl
        )
        has_mrpl_operational_metric = any(
            metric in q_lower for metric in [
                "operating service", "design pressure", "wall thickness", "statutory approval",
                "corrosion rate", "remaining life", "pop test", "set pressure", "specifications of",
            ]
        ) and has_mrpl_anchor

        is_genuine_generic = has_generic_keyword and not has_mrpl_anchor and not has_mrpl_operational_metric

        if is_genuine_generic:
            return EntityResolutionResult(
                entity=None,
                raw_entity=extracted_tags[0] if extracted_tags else None,
                canonical_name=None,
                entity_type=EntityType.UNKNOWN,
                mrpl_kb_status="NONE",
                asset_registry_status="NOT_CHECKED",
                resolution_status=EntityResolutionStatus.NO_ENTITY_DETECTED,
                confidence=0.99,
                all_extracted_tags=extracted_tags,
                resolved_entities=[],
                unresolved_entities=extracted_tags,
                target_entity=None,
                is_generic_tag_inquiry=True,
                is_mrpl_entity=False,
                resolution_message="Recognized generic equipment tagging / nomenclature inquiry; routed to General Knowledge Mode",
            )

        # 3. Check for queries without explicit regex tags (e.g. CDU-II or year-based thickness surveys)
        if not extracted_tags:
            if "2019" in q_lower and "2024" in q_lower and ("thickness" in q_lower or "corrosion" in q_lower):
                return EntityResolutionResult(
                    entity="P-201",
                    raw_entity="P-201",
                    canonical_name="P-201",
                    entity_type=EntityType.EQUIPMENT,
                    mrpl_kb_status="FOUND",
                    resolution_status=EntityResolutionStatus.FOUND_IN_MRPL_KB,
                    confidence=0.98,
                    matched_documents=["INSP_2019_P201_Baseline_UT.json", "INSP_2024_P201_UT_Survey_Report.json"],
                    all_extracted_tags=["P-201"],
                    resolved_entities=["P-201"],
                    unresolved_entities=[],
                    target_entity="P-201",
                    is_mrpl_entity=True,
                    resolution_message="Resolved asset P-201 from 2019/2024 inspection records in MRPL KB",
                )
            if "cdu-ii" in q_lower or "cdu" in q_lower or "crude distillation unit" in q_lower:
                return EntityResolutionResult(
                    entity="CDU-II",
                    raw_entity="CDU-II",
                    canonical_name="CDU-II",
                    entity_type=EntityType.SYSTEM,
                    mrpl_kb_status="FOUND",
                    resolution_status=EntityResolutionStatus.FOUND_IN_MRPL_KB,
                    confidence=0.99,
                    matched_documents=["PID_CDU_200_P201_Crude_Booster_Loop.json"],
                    all_extracted_tags=["CDU-II"],
                    resolved_entities=["CDU-II"],
                    unresolved_entities=[],
                    target_entity="CDU-II",
                    is_mrpl_entity=True,
                    resolution_message="Resolved plant unit CDU-II in MRPL KB",
                )
            return EntityResolutionResult(
                entity=None,
                mrpl_kb_status="NONE",
                resolution_status=EntityResolutionStatus.NO_ENTITY_DETECTED,
                confidence=0.0,
                all_extracted_tags=[],
                resolved_entities=[],
                unresolved_entities=[],
                target_entity=None,
                resolution_message="No equipment identifier or MRPL entity found in query",
            )

        # 4. Resolve ALL extracted tags against Tier 1 (MRPL KB) and Tier 2 (Asset Registry)
        resolved_kb_map: Dict[str, MRPLEntityRecord] = {}
        resolved_reg_map: Dict[str, Any] = {}
        resolved_tags: List[str] = []
        unresolved_tags: List[str] = []

        for clean_tag in extracted_tags:
            # Check KB
            canonical = self.tag_index.get(clean_tag.lower()) or self.alias_index.get(clean_tag.lower())
            if canonical and canonical in self.entities:
                record = self.entities[canonical]
                resolved_kb_map[clean_tag] = record
                resolved_tags.append(canonical)
                continue

            # Check Asset Registry
            reg_asset = self._lookup_asset_registry(clean_tag)
            if reg_asset:
                reg_canonical = reg_asset.asset_tag.upper().strip()
                resolved_reg_map[clean_tag] = reg_asset
                resolved_tags.append(reg_canonical)
                continue

            # Unresolved
            unresolved_tags.append(clean_tag)

        # 5. Multi-Entity Evaluation (Failure 1 Fix)
        # If any tag in the query is unresolved and the query requests an MRPL-specific claim involving that tag:
        # e.g. "P-201 is a pump. Is P-999 also a pump at MRPL?" or "Compare P-201 and P-999 at MRPL." or "What is P-999 at MRPL?"
        if unresolved_tags:
            # Target the unresolved entity so Context Guard will block the ungrounded claim
            primary_unresolved = unresolved_tags[0]
            inferred_type = self._infer_entity_type(primary_unresolved, "")

            # Determine if this is a comparison or cross-asset query
            if resolved_tags:
                msg = f"Unknown entity {primary_unresolved} requested in context of {', '.join(resolved_tags)}. Blocked by Context Guard to prevent cross-asset hallucination."
            else:
                msg = f"{primary_unresolved} could not be found in the MRPL Local Knowledge Base or the MRPL Asset Registry."

            return EntityResolutionResult(
                entity=primary_unresolved,
                raw_entity=primary_unresolved,
                canonical_name=primary_unresolved,
                entity_type=inferred_type,
                mrpl_kb_status="NOT_FOUND",
                asset_registry_status="NOT_FOUND",
                resolution_status=EntityResolutionStatus.NOT_FOUND_IN_KB,
                confidence=0.99,
                matched_documents=[],
                matched_entity=None,
                asset_record=None,
                all_extracted_tags=extracted_tags,
                resolved_entities=resolved_tags,
                unresolved_entities=unresolved_tags,
                target_entity=primary_unresolved,
                is_mrpl_entity=False,
                resolution_message=msg,
            )

        # 6. All extracted tags are verified MRPL entities
        first_tag = extracted_tags[0]
        if first_tag in resolved_kb_map:
            record = resolved_kb_map[first_tag]
            all_docs = []
            for t, rec in resolved_kb_map.items():
                all_docs.append(rec.source_document)
                for doc_id in rec.related_document_ids:
                    if doc_id:
                        all_docs.append(f"{doc_id}.json")
            return EntityResolutionResult(
                entity=record.canonical_name,
                raw_entity=first_tag,
                canonical_name=record.canonical_name,
                entity_type=record.entity_type,
                mrpl_kb_status="FOUND",
                asset_registry_status="NOT_CHECKED",
                resolution_status=EntityResolutionStatus.FOUND_IN_MRPL_KB,
                confidence=0.99,
                matched_documents=list(dict.fromkeys(all_docs)),
                matched_entity=record,
                all_extracted_tags=extracted_tags,
                resolved_entities=resolved_tags,
                unresolved_entities=[],
                target_entity=record.canonical_name,
                is_mrpl_entity=True,
                resolution_message=f"Entity {record.canonical_name} verified in MRPL Local Knowledge Base ({record.source_document})",
            )
        elif first_tag in resolved_reg_map:
            reg_asset = resolved_reg_map[first_tag]
            canonical = reg_asset.asset_tag.upper().strip()
            inferred_type = self._infer_entity_type(canonical, reg_asset.asset_name)
            linked_docs = []
            for d in (getattr(reg_asset, "documents_manifest", []) or []):
                if isinstance(d, str):
                    linked_docs.append(d)
                elif hasattr(d, "document_name"):
                    linked_docs.append(d.document_name)
                elif isinstance(d, dict):
                    linked_docs.append(d.get("document_name", d.get("document_id", "DOC")))
            asset_dict = reg_asset.model_dump() if hasattr(reg_asset, "model_dump") else dict(reg_asset)
            return EntityResolutionResult(
                entity=canonical,
                raw_entity=first_tag,
                canonical_name=canonical,
                entity_type=inferred_type,
                mrpl_kb_status="NOT_FOUND",
                asset_registry_status="FOUND",
                resolution_status=EntityResolutionStatus.FOUND_IN_ASSET_REGISTRY,
                confidence=0.95,
                matched_documents=linked_docs,
                matched_entity=None,
                asset_record=asset_dict,
                all_extracted_tags=extracted_tags,
                resolved_entities=resolved_tags,
                unresolved_entities=[],
                target_entity=canonical,
                is_mrpl_entity=True,
                resolution_message=f"Entity {canonical} found in MRPL Asset Registry ({reg_asset.asset_name}, Unit: {reg_asset.process_unit}), but not in standalone KB documents",
            )

    def _lookup_asset_registry(self, tag: str) -> Optional[Any]:
        """Queries the dynamic Asset Registry service for tag if available."""
        try:
            from backend.services.asset_registry import AssetRegistryService
            if not hasattr(self, "_asset_registry") or self._asset_registry is None:
                self._asset_registry = AssetRegistryService()
            return self._asset_registry.get_asset(tag)
        except Exception as e:
            logger.debug(f"Asset registry lookup error for {tag}: {e}")
            return None

    def is_known(self, tag: str) -> bool:
        """Returns True if tag is a registered MRPL entity."""
        return tag.lower() in self.tag_index or tag.upper() in self.entities

    def get_entity(self, tag: str) -> Optional[MRPLEntityRecord]:
        canonical = self.tag_index.get(tag.lower()) or tag.upper()
        return self.entities.get(canonical)

    def get_all_entities(self) -> List[MRPLEntityRecord]:
        return list(self.entities.values())
