# backend/services/evidence/evidence_requirement_engine.py
"""
MRPL Sovereign AI Workbench — Evidence Requirement Engine.
Dynamically synthesizes formal Evidence Contracts tailored to specific industrial tasks,
risk profiles, entity scopes, and modality requirements.
"""

import time
import uuid
import logging
from typing import Dict, Any, List, Optional, Callable

from backend.models.task_profile import TaskProfile, TaskType, RiskLevel
from backend.services.evidence.evidence_models import (
    EvidenceContract,
    EvidenceRequirement,
    EvidenceType,
    AuthorityLevel,
    EvidenceModality,
    FreshnessRequirement,
    ContractGenerationContext,
)

logger = logging.getLogger("mrpl.evidence.requirement_engine")


class EvidenceRequirementEngine:
    """
    Synthesizes first-class Evidence Contracts based on task context, domain rules,
    and risk parameters.
    """

    def __init__(self):
        self._template_registry: Dict[str, Callable[[ContractGenerationContext], EvidenceContract]] = {}
        self._register_built_in_templates()

    def generate_contract(
        self,
        task_profile: Optional[TaskProfile] = None,
        context: Optional[ContractGenerationContext] = None,
        query: Optional[str] = None,
        files: Optional[List[Dict[str, Any]]] = None,
        risk_override: Optional[str] = None,
    ) -> EvidenceContract:
        """
        Main entry point to construct an EvidenceContract from a TaskProfile or raw context.
        """
        ctx = context or self._build_context_from_profile(task_profile, query, files, risk_override)
        task_type_str = (ctx.task_type or "general_reasoning").lower()

        # Resolve matching template generator
        generator = self._find_matching_generator(task_type_str, ctx)
        contract = generator(ctx)

        # Apply entity scope adjustments (only for MRPL plant tasks, never for general knowledge / generic coding)
        if task_type_str not in ("general_reasoning", "general", "generic_coding"):
            if ctx.entity_name and ctx.entity_name not in contract.required_entities:
                contract.required_entities.append(ctx.entity_name)
                for req in contract.required_evidence:
                    if req.evidence_type in (
                        EvidenceType.ULTRASONIC_THICKNESS_DATA,
                        EvidenceType.BASELINE_INSPECTION,
                        EvidenceType.CURRENT_INSPECTION,
                        EvidenceType.EQUIPMENT_DATASHEET,
                    ):
                        req.entity_scope = ctx.entity_name
        else:
            # Ensure general reasoning never carries mandatory MRPL entity requirements
            contract.required_entities = []

        # Ensure risk level alignment
        if ctx.risk_level:
            contract.risk_level = ctx.risk_level.lower()

        return contract

    def register_custom_template(
        self,
        task_type: str,
        generator: Callable[[ContractGenerationContext], EvidenceContract],
    ):
        """Allows dynamic registration of domain-specific contract templates."""
        self._template_registry[task_type.lower()] = generator

    # ─────────────────────────────────────────────────────────────
    # Internal Template Registrations & Generators
    # ─────────────────────────────────────────────────────────────

    def _register_built_in_templates(self):
        # 1. Engineering Calculations (API 570, ASME, ISO)
        self._template_registry["engineering_calculation"] = self._generate_calculation_contract
        self._template_registry["calculation"] = self._generate_calculation_contract

        # 2. Equipment Inspection & Statutory Approval Note
        self._template_registry["equipment_approval"] = self._generate_approval_contract
        self._template_registry["approval_note"] = self._generate_approval_contract
        self._template_registry["inspection_review"] = self._generate_approval_contract

        # 3. Presentation Decks (PPTX)
        self._template_registry["presentation_generation"] = self._generate_presentation_contract
        self._template_registry["presentation"] = self._generate_presentation_contract

        # 4. Code & Script Generation
        self._template_registry["generic_coding"] = self._generate_generic_coding_contract
        self._template_registry["engineering_coding"] = self._generate_coding_contract
        self._template_registry["code_generation"] = self._generate_coding_contract
        self._template_registry["coding"] = self._generate_coding_contract
        self._template_registry["code_review"] = self._generate_coding_contract

        # 5. P&ID & Multimodal Vision Inspection
        self._template_registry["vision_p_and_id"] = self._generate_vision_contract
        self._template_registry["multimodal_engineering_analysis"] = self._generate_vision_contract
        self._template_registry["multimodal_document_analysis"] = self._generate_vision_contract
        self._template_registry["inspection_and_equipment_trace_report"] = self._generate_vision_contract

        # 6. Turnaround Memo & Summarization
        self._template_registry["memo_summarization"] = self._generate_summarization_contract
        self._template_registry["internal_correspondence"] = self._generate_summarization_contract
        self._template_registry["document_qa"] = self._generate_qa_contract
        self._template_registry["verified_technical_summary"] = self._generate_qa_contract

        # 7. Unknown MRPL Entity & Context Guard
        self._template_registry["unknown_mrpl_entity"] = self._generate_unknown_mrpl_entity_contract
        self._template_registry["guarded_entity_resolution_refusal"] = self._generate_unknown_mrpl_entity_contract
        # 8. P&ID Evidence Bridge Templates
        self._template_registry["pid_isolation_safety"] = self._generate_pid_isolation_contract
        self._template_registry["pid_isolation"] = self._generate_pid_isolation_contract
        self._template_registry["pid_protection_adequacy"] = self._generate_pid_protection_contract
        self._template_registry["pid_protection"] = self._generate_pid_protection_contract
        self._template_registry["pid_documentary_support"] = self._generate_pid_documentary_contract

        # 9. General Reasoning Fallback
        self._template_registry["general_reasoning"] = self._generate_general_contract

    def _find_matching_generator(
        self,
        task_type_str: str,
        ctx: ContractGenerationContext,
    ) -> Callable[[ContractGenerationContext], EvidenceContract]:
        query_l = ctx.query.lower()

        # Multimodal image attachment always mandates vision contract
        if ctx.has_images:
            return self._generate_vision_contract

        # Direct template match if explicit domain is defined (e.g. code_generation, engineering_calculation, equipment_approval)
        if task_type_str and task_type_str not in ("general_reasoning", "general") and task_type_str in self._template_registry:
            # Special case: if task was classified as memo but query is explicitly for a presentation deck
            if task_type_str in ("memo_summarization", "internal_correspondence") and any(k in query_l for k in ["presentation", "slide deck", "powerpoint", "make a ppt", "create a ppt"]):
                return self._generate_presentation_contract
            return self._template_registry[task_type_str]

        # Query / Modal heuristics when task_type is generic
        if "p&id" in query_l or "schematic" in query_l:
            return self._generate_vision_contract
        if any(k in query_l for k in ["presentation", "slide deck", "powerpoint", "make a ppt", "create a ppt"]):
            return self._generate_presentation_contract
        if any(k in query_l for k in ["calculate", "corrosion rate", "remaining life", "wall thickness", "api 570"]):
            return self._generate_calculation_contract
        if any(k in query_l for k in ["approval note", "statutory approval", "integrity assessment", "sign-off"]):
            return self._generate_approval_contract
        if any(k in query_l for k in ["python code", "script", "function", "write a program", "code"]):
            return self._generate_coding_contract
        if any(k in query_l for k in ["turnaround memo", "safety procedure", "summarize memo"]):
            return self._generate_summarization_contract

        if task_type_str in self._template_registry:
            return self._template_registry[task_type_str]

        return self._generate_general_contract

    def _build_context_from_profile(
        self,
        task_profile: Optional[TaskProfile],
        query: Optional[str],
        files: Optional[List[Dict[str, Any]]],
        risk_override: Optional[str],
    ) -> ContractGenerationContext:
        req_query = query or (task_profile.intent if task_profile else "")
        t_id = (task_profile.request_id if task_profile else None) or f"REQ-EVID-{uuid.uuid4().hex[:8]}"
        t_type = (task_profile.task_type.value if (task_profile and hasattr(task_profile.task_type, 'value')) else str(task_profile.task_type)) if task_profile else "general_reasoning"
        r_level = risk_override or ((task_profile.risk.value if (task_profile and hasattr(task_profile.risk, 'value')) else str(task_profile.risk)) if task_profile else "low")
        e_name = task_profile.entity_name if task_profile else None

        has_imgs = False
        has_csvs = False
        if files:
            for f in files:
                m_type = f.get("type", "") if isinstance(f, dict) else ""
                n_str = f.get("name", "") if isinstance(f, dict) else ""
                if "image" in m_type or any(ext in n_str.lower() for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                    has_imgs = True
                if "csv" in m_type or ".csv" in n_str.lower():
                    has_csvs = True

        return ContractGenerationContext(
            task_id=t_id,
            query=req_query,
            task_type=t_type,
            intent=task_profile.intent if task_profile else None,
            risk_level=r_level,
            entity_name=e_name,
            files=files,
            has_images=has_imgs,
            has_csv=has_csvs,
            domain=task_profile.domain if task_profile else "GENERAL",
        )

    # ─────────────────────────────────────────────────────────────
    # Domain-Specific Contract Synthesizers
    # ─────────────────────────────────────────────────────────────

    def _generate_calculation_contract(self, ctx: ContractGenerationContext) -> EvidenceContract:
        t_id = ctx.task_id or f"EVID-CALC-{uuid.uuid4().hex[:6]}"
        ent = ctx.entity_name or "Target Equipment"

        required = [
            EvidenceRequirement(
                id="REQ-CALC-001",
                evidence_type=EvidenceType.REQUIRED_NUMERIC_INPUTS,
                description=f"Measured current wall thickness ($t_{{curr}}$), baseline thickness ($t_{{prev}}$), and elapsed inspection interval for {ent}.",
                mandatory=True,
                authority_requirement=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
                entity_scope=ctx.entity_name,
                expected_modality=EvidenceModality.NUMERICAL,
                validation_rule="Must contain non-null positive float values for $t_{prev}$, $t_{curr}$, and interval.",
            ),
            EvidenceRequirement(
                id="REQ-CALC-002",
                evidence_type=EvidenceType.APPLICABLE_STANDARD,
                description="Governing statutory engineering standard (API 570 Section 7.1.1 / ASME B31.3 / ISO 10816).",
                mandatory=True,
                authority_requirement=AuthorityLevel.STANDARD_OPERATING_PROCEDURE,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Standard identifier must match API 570, API 510, ASME B31.3, or ISO 10816.",
            ),
            EvidenceRequirement(
                id="REQ-CALC-003",
                evidence_type=EvidenceType.FORMULA_DEFINITION,
                description="Deterministic mathematical equation for metal loss rate ($C_r = \\frac{t_{prev} - t_{curr}}{\\Delta t}$) and remaining life ($R_L = \\frac{t_{curr} - t_{min}}{C_r}$).",
                mandatory=True,
                authority_requirement=AuthorityLevel.STANDARD_OPERATING_PROCEDURE,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Formula must be resolvable via deterministic Python Float64 calculator.",
            ),
            EvidenceRequirement(
                id="REQ-CALC-004",
                evidence_type=EvidenceType.UNITS_SPECIFICATION,
                description="Engineering unit declarations (thickness in mm, rate in mm/year, interval in years).",
                mandatory=True,
                authority_requirement=AuthorityLevel.STANDARD_OPERATING_PROCEDURE,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Units must be normalized to standard metric units (mm, years).",
            ),
        ]

        optional = [
            EvidenceRequirement(
                id="REQ-CALC-OPT-001",
                evidence_type=EvidenceType.EQUIPMENT_DATASHEET,
                description=f"Equipment mechanical datasheet specifying nominal design thickness and minimum retirement thickness ($t_{{min}}$) for {ent}.",
                mandatory=False,
                authority_requirement=AuthorityLevel.AUTHORITATIVE_PSU,
                entity_scope=ctx.entity_name,
                expected_modality=EvidenceModality.DOCUMENT_PDF,
                validation_rule="Datasheet must define corrosion allowance and material specification.",
            )
        ]

        blocking = [
            "MISSING_INPUT_NUMERICAL_PARAMETERS",
            "INCOMPATIBLE_ENGINEERING_UNITS",
        ]

        return EvidenceContract(
            task_id=t_id,
            task_type="engineering_calculation",
            required_evidence=required,
            optional_evidence=optional,
            minimum_coverage=1.0,
            required_source_authority=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
            freshness_requirements={"statutory_cycle_years": 5.0},
            required_entities=[ctx.entity_name] if ctx.entity_name else [],
            blocking_conditions=blocking,
            risk_level=ctx.risk_level or "high",
            created_at=time.time(),
        )

    def _generate_approval_contract(self, ctx: ContractGenerationContext) -> EvidenceContract:
        t_id = ctx.task_id or f"EVID-APPR-{uuid.uuid4().hex[:6]}"
        ent = ctx.entity_name or "Target Asset"

        required = [
            EvidenceRequirement(
                id="REQ-APPR-001",
                evidence_type=EvidenceType.CURRENT_INSPECTION,
                description=f"Current turnaround ultrasonic thickness survey & NDT report for {ent}.",
                mandatory=True,
                authority_requirement=AuthorityLevel.AUTHORITATIVE_PSU,
                entity_scope=ctx.entity_name,
                expected_modality=EvidenceModality.DOCUMENT_PDF,
                validation_rule="Report must contain measured grid values and NDT inspector sign-off.",
            ),
            EvidenceRequirement(
                id="REQ-APPR-002",
                evidence_type=EvidenceType.BASELINE_INSPECTION,
                description=f"Previous statutory inspection baseline record (5-year baseline) for {ent}.",
                mandatory=True,
                authority_requirement=AuthorityLevel.AUTHORITATIVE_PSU,
                entity_scope=ctx.entity_name,
                expected_modality=EvidenceModality.DOCUMENT_PDF,
                validation_rule="Record must specify baseline thickness at commissioning / prior turnaround.",
            ),
            EvidenceRequirement(
                id="REQ-APPR-003",
                evidence_type=EvidenceType.EQUIPMENT_DATASHEET,
                description=f"Design datasheet for {ent} (material specification, design pressure/temperature, $t_{{min}}$ limit).",
                mandatory=True,
                authority_requirement=AuthorityLevel.AUTHORITATIVE_PSU,
                entity_scope=ctx.entity_name,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Datasheet must specify $t_{min}$ per ASME B31.3 / API 570.",
            ),
            EvidenceRequirement(
                id="REQ-APPR-004",
                evidence_type=EvidenceType.ACCEPTANCE_CRITERIA,
                description=r"Statutory continued operation criteria ($t_{curr} > t_{min}$ and remaining life $\ge$ next turnaround cycle).",
                mandatory=True,
                authority_requirement=AuthorityLevel.STANDARD_OPERATING_PROCEDURE,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Calculated remaining safe operating life must exceed the 3-year turnaround window.",
            ),
        ]

        optional = [
            EvidenceRequirement(
                id="REQ-APPR-OPT-001",
                evidence_type=EvidenceType.VIBRATION_SURVEY,
                description="Rotating equipment mechanical vibration spectrum compliant with ISO 10816 Zone A/B.",
                mandatory=False,
                authority_requirement=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
                entity_scope=ctx.entity_name,
                expected_modality=EvidenceModality.TEXT,
                validation_rule=r"Vibration overall RMS must be $\le 4.5$ mm/s.",
            ),
            EvidenceRequirement(
                id="REQ-APPR-OPT-002",
                evidence_type=EvidenceType.MOC_RECORD,
                description="Management of Change (MOC) history for impeller or material upgrades.",
                mandatory=False,
                authority_requirement=AuthorityLevel.AUTHORITATIVE_PSU,
                entity_scope=ctx.entity_name,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Validates MOC reference and metallurgical upgrade logs.",
            ),
        ]

        blocking = [
            "UNRESOLVED_EQUIPMENT_TAG",
            "MISSING_CURRENT_STATUTORY_INSPECTION",
            "RETIREMENT_THICKNESS_VIOLATION",
        ]

        return EvidenceContract(
            task_id=t_id,
            task_type="equipment_approval",
            required_evidence=required,
            optional_evidence=optional,
            minimum_coverage=1.0,
            required_source_authority=AuthorityLevel.AUTHORITATIVE_PSU,
            freshness_requirements={"statutory_cycle_years": 5.0, "max_age_days": 1825},
            required_entities=[ctx.entity_name] if ctx.entity_name else [],
            blocking_conditions=blocking,
            risk_level="high",
            created_at=time.time(),
        )

    def _generate_presentation_contract(self, ctx: ContractGenerationContext) -> EvidenceContract:
        t_id = ctx.task_id or f"EVID-PPT-{uuid.uuid4().hex[:6]}"

        required = [
            EvidenceRequirement(
                id="REQ-PPT-001",
                evidence_type=EvidenceType.USER_SCOPE,
                description="Defined presentation topic, audience scope, and objective outline.",
                mandatory=True,
                authority_requirement=AuthorityLevel.ANY,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="User prompt must specify presentation topic or deliverable goal.",
            ),
            EvidenceRequirement(
                id="REQ-PPT-002",
                evidence_type=EvidenceType.FACTUAL_ASSERTIONS,
                description="Factual assertions and slide content bullets relevant to requested subject.",
                mandatory=True,
                authority_requirement=AuthorityLevel.ANY,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Minimum 3 distinct slide headings with structured bullet points.",
            ),
        ]

        optional = [
            EvidenceRequirement(
                id="REQ-PPT-OPT-001",
                evidence_type=EvidenceType.SOURCE_DOCUMENTS,
                description="Background briefing documents or MRPL technical records.",
                mandatory=False,
                authority_requirement=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
                expected_modality=EvidenceModality.DOCUMENT_PDF,
                validation_rule="Optional source citations for slide notes.",
            )
        ]

        return EvidenceContract(
            task_id=t_id,
            task_type="presentation_generation",
            required_evidence=required,
            optional_evidence=optional,
            minimum_coverage=1.0,
            required_source_authority=AuthorityLevel.ANY,
            freshness_requirements={},
            required_entities=[ctx.entity_name] if ctx.entity_name else [],
            blocking_conditions=["EMPTY_TOPIC_SPECIFICATION"],
            risk_level="low",
            created_at=time.time(),
        )

    def _generate_generic_coding_contract(self, ctx: ContractGenerationContext) -> EvidenceContract:
        t_id = ctx.task_id or f"EVID-CODE-GENERIC-{uuid.uuid4().hex[:6]}"
        return EvidenceContract(
            task_id=t_id,
            task_type="generic_coding",
            required_evidence=[],
            optional_evidence=[],
            minimum_coverage=1.0,
            required_source_authority=AuthorityLevel.ANY,
            freshness_requirements={},
            required_entities=[],
            blocking_conditions=[],
            risk_level="low",
            created_at=time.time(),
        )

    def _generate_coding_contract(self, ctx: ContractGenerationContext) -> EvidenceContract:
        t_id = ctx.task_id or f"EVID-CODE-{uuid.uuid4().hex[:6]}"

        required = [
            EvidenceRequirement(
                id="REQ-CODE-001",
                evidence_type=EvidenceType.FUNCTIONAL_REQUIREMENTS,
                description="Input data specifications, algorithm expectations, and expected outputs.",
                mandatory=True,
                authority_requirement=AuthorityLevel.ANY,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Prompt must specify input format and target logic.",
            ),
            EvidenceRequirement(
                id="REQ-CODE-002",
                evidence_type=EvidenceType.TEST_CRITERIA,
                description="Deterministic verification test cases or assertion boundaries.",
                mandatory=True,
                authority_requirement=AuthorityLevel.ANY,
                expected_modality=EvidenceModality.SOURCE_CODE,
                validation_rule="Code structure must support automated test assertions or unit testing.",
            ),
        ]

        optional = [
            EvidenceRequirement(
                id="REQ-CODE-OPT-001",
                evidence_type=EvidenceType.LOCAL_DOCUMENTATION,
                description="Local API documentation or library schemas.",
                mandatory=False,
                authority_requirement=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Compatibility with Python 3.10+ standard library.",
            )
        ]

        return EvidenceContract(
            task_id=t_id,
            task_type="code_generation",
            required_evidence=required,
            optional_evidence=optional,
            minimum_coverage=1.0,
            required_source_authority=AuthorityLevel.ANY,
            freshness_requirements={},
            required_entities=[],
            blocking_conditions=["MISSING_FUNCTIONAL_SPECIFICATION"],
            risk_level="low",
            created_at=time.time(),
        )

    def _generate_vision_contract(self, ctx: ContractGenerationContext) -> EvidenceContract:
        t_id = ctx.task_id or f"EVID-VIS-{uuid.uuid4().hex[:6]}"

        required = [
            EvidenceRequirement(
                id="REQ-VIS-001",
                evidence_type=EvidenceType.P_AND_ID_SCHEMATIC,
                description="Decodable high-resolution engineering drawing or P&ID schematic image.",
                mandatory=True,
                authority_requirement=AuthorityLevel.USER_PROVIDED_ATTACHMENT,
                expected_modality=EvidenceModality.IMAGE_VISION,
                validation_rule="Base64 or binary image payload must exceed 100 bytes and decode cleanly.",
            ),
            EvidenceRequirement(
                id="REQ-VIS-002",
                evidence_type=EvidenceType.USER_SCOPE,
                description="Specific equipment tag, instrument loop, or flow path inspection target.",
                mandatory=True,
                authority_requirement=AuthorityLevel.ANY,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Query specifies visual tracing scope or target equipment.",
            ),
        ]

        optional = [
            EvidenceRequirement(
                id="REQ-VIS-OPT-001",
                evidence_type=EvidenceType.EQUIPMENT_DATASHEET,
                description="Operating parameters and instrument loop calibration schedules.",
                mandatory=False,
                authority_requirement=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Correlates diagram bubbles with physical transmitter tags.",
            )
        ]

        return EvidenceContract(
            task_id=t_id,
            task_type="vision_p_and_id",
            required_evidence=required,
            optional_evidence=optional,
            minimum_coverage=1.0,
            required_source_authority=AuthorityLevel.USER_PROVIDED_ATTACHMENT,
            freshness_requirements={},
            required_entities=[ctx.entity_name] if ctx.entity_name else [],
            blocking_conditions=["MISSING_IMAGE_PAYLOAD", "CORRUPTED_IMAGE_BYTES"],
            risk_level="medium",
            created_at=time.time(),
        )

    def _generate_summarization_contract(self, ctx: ContractGenerationContext) -> EvidenceContract:
        t_id = ctx.task_id or f"EVID-MEMO-{uuid.uuid4().hex[:6]}"

        required = [
            EvidenceRequirement(
                id="REQ-MEMO-001",
                evidence_type=EvidenceType.SOURCE_DOCUMENTS,
                description="Source text, turnaround safety procedure, or engineering memo.",
                mandatory=True,
                authority_requirement=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Input text or retrieved context must contain substantive operational procedures.",
            )
        ]

        optional = [
            EvidenceRequirement(
                id="REQ-MEMO-OPT-001",
                evidence_type=EvidenceType.SOP_PROCEDURE,
                description="OISD safety standard reference (e.g. OISD-118, OISD-140).",
                mandatory=False,
                authority_requirement=AuthorityLevel.STANDARD_OPERATING_PROCEDURE,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="References official PSU refinery safety guidelines.",
            )
        ]

        return EvidenceContract(
            task_id=t_id,
            task_type="memo_summarization",
            required_evidence=required,
            optional_evidence=optional,
            minimum_coverage=1.0,
            required_source_authority=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
            freshness_requirements={},
            required_entities=[ctx.entity_name] if ctx.entity_name else [],
            blocking_conditions=["EMPTY_SOURCE_DOCUMENT"],
            risk_level="low",
            created_at=time.time(),
        )

    def _generate_qa_contract(self, ctx: ContractGenerationContext) -> EvidenceContract:
        t_id = ctx.task_id or f"EVID-QA-{uuid.uuid4().hex[:6]}"

        required = [
            EvidenceRequirement(
                id="REQ-QA-001",
                evidence_type=EvidenceType.USER_SCOPE,
                description="Clearly articulated engineering inquiry.",
                mandatory=True,
                authority_requirement=AuthorityLevel.ANY,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Prompt must not be empty.",
            ),
            EvidenceRequirement(
                id="REQ-QA-002",
                evidence_type=EvidenceType.SOURCE_DOCUMENTS,
                description="Supporting MRPL engineering documentation or knowledge base records.",
                mandatory=True,
                authority_requirement=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Must retrieve or be provided with relevant factual evidence chunks.",
            ),
        ]

        return EvidenceContract(
            task_id=t_id,
            task_type="document_qa",
            required_evidence=required,
            optional_evidence=[],
            minimum_coverage=1.0,
            required_source_authority=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
            freshness_requirements={},
            required_entities=[ctx.entity_name] if ctx.entity_name else [],
            blocking_conditions=["ZERO_RETRIEVED_EVIDENCE_FOR_ORGANIZATION_ENTITY"],
            risk_level="low",
            created_at=time.time(),
        )

    def _generate_pid_isolation_contract(self, ctx: ContractGenerationContext) -> EvidenceContract:
        t_id = ctx.task_id or f"EVID-PID-ISO-{uuid.uuid4().hex[:6]}"
        ent = ctx.entity_name or "Target Equipment"

        required = [
            EvidenceRequirement(
                id="REQ-PID-ISO-001",
                evidence_type=EvidenceType.P_AND_ID_SCHEMATIC,
                description=f"Verified P&ID topology establishing positive suction and discharge isolation boundary valves and low-point drains for {ent}.",
                mandatory=True,
                authority_requirement=AuthorityLevel.AUTHORITATIVE_PSU,
                entity_scope=ctx.entity_name,
                expected_modality=EvidenceModality.TEXT,
                validation_rule=f"P&ID knowledge graph must resolve suction/discharge block valves isolating {ent}.",
            ),
            EvidenceRequirement(
                id="REQ-PID-ISO-002",
                evidence_type=EvidenceType.SOP_PROCEDURE,
                description=f"Approved MRPL Standard Operating Procedure (SOP) or Lockout/Tagout (LOTO) isolation guideline governing maintenance on {ent}.",
                mandatory=True,
                authority_requirement=AuthorityLevel.STANDARD_OPERATING_PROCEDURE,
                entity_scope=ctx.entity_name,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Retrieved evidence must contain formal MRPL SOP or LOTO procedure requirements.",
            ),
            EvidenceRequirement(
                id="REQ-PID-ISO-003",
                evidence_type=EvidenceType.ACCEPTANCE_CRITERIA,
                description="Mandatory depressurization, hydrocarbon purging, and positive drain verification criteria before breaking containment.",
                mandatory=True,
                authority_requirement=AuthorityLevel.STANDARD_OPERATING_PROCEDURE,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="SOP or safety procedure must define zero-energy verification and drainage sequence.",
            ),
        ]

        optional = [
            EvidenceRequirement(
                id="REQ-PID-ISO-OPT-001",
                evidence_type=EvidenceType.MOC_RECORD,
                description="Active Work Permit or Management of Change (MOC) authorization record.",
                mandatory=False,
                authority_requirement=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Permit to Work (PTW) or MOC log reference.",
            )
        ]

        return EvidenceContract(
            task_id=t_id,
            task_type="pid_isolation_safety",
            required_evidence=required,
            optional_evidence=optional,
            minimum_coverage=1.0,
            required_source_authority=AuthorityLevel.STANDARD_OPERATING_PROCEDURE,
            freshness_requirements={},
            required_entities=[ctx.entity_name] if ctx.entity_name else [],
            blocking_conditions=["UNRESOLVED_ISOLATION_BOUNDARY", "MISSING_MANDATORY_SOP", "UNVERIFIED_FIELD_DEPRESSURIZATION"],
            risk_level="high",
            created_at=time.time(),
        )

    def _generate_pid_protection_contract(self, ctx: ContractGenerationContext) -> EvidenceContract:
        t_id = ctx.task_id or f"EVID-PID-PROT-{uuid.uuid4().hex[:6]}"
        ent = ctx.entity_name or "Target Equipment"

        required = [
            EvidenceRequirement(
                id="REQ-PID-PROT-001",
                evidence_type=EvidenceType.P_AND_ID_SCHEMATIC,
                description=f"Verified P&ID topology establishing safety relief valve (PSV) connection to {ent} and discharge header routing.",
                mandatory=True,
                authority_requirement=AuthorityLevel.AUTHORITATIVE_PSU,
                entity_scope=ctx.entity_name,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="P&ID graph establishes overpressure protection edge from PSV to target equipment.",
            ),
            EvidenceRequirement(
                id="REQ-PID-PROT-002",
                evidence_type=EvidenceType.EQUIPMENT_DATASHEET,
                description=f"Authoritative PSV equipment datasheet with certified set pressure, orifice designation, and relieving capacity for {ent}.",
                mandatory=True,
                authority_requirement=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
                entity_scope=ctx.entity_name,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Datasheet must specify set pressure, orifice size, and design relieving rate.",
            ),
            EvidenceRequirement(
                id="REQ-PID-PROT-003",
                evidence_type=EvidenceType.APPLICABLE_STANDARD,
                description="Governing statutory relief valve sizing standard (API 520 / API 521 / OISD-106).",
                mandatory=True,
                authority_requirement=AuthorityLevel.STANDARD_OPERATING_PROCEDURE,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Standard must match API 520, API 521, or OISD-106.",
            ),
            EvidenceRequirement(
                id="REQ-PID-PROT-004",
                evidence_type=EvidenceType.FORMULA_DEFINITION,
                description="Relief capacity sizing equation and scenario overpressure contingency calculation model.",
                mandatory=True,
                authority_requirement=AuthorityLevel.STANDARD_OPERATING_PROCEDURE,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Relieving rate calculation must be deterministically verifiable.",
            ),
        ]

        return EvidenceContract(
            task_id=t_id,
            task_type="pid_protection_adequacy",
            required_evidence=required,
            optional_evidence=[],
            minimum_coverage=1.0,
            required_source_authority=AuthorityLevel.STANDARD_OPERATING_PROCEDURE,
            freshness_requirements={},
            required_entities=[ctx.entity_name] if ctx.entity_name else [],
            blocking_conditions=["MISSING_PSV_TOPOLOGY", "MISSING_SIZING_CALCULATION", "UNVERIFIED_RELIEF_CAPACITY"],
            risk_level="critical",
            created_at=time.time(),
        )

    def _generate_pid_documentary_contract(self, ctx: ContractGenerationContext) -> EvidenceContract:
        t_id = ctx.task_id or f"EVID-PID-DOC-{uuid.uuid4().hex[:6]}"
        ent = ctx.entity_name or "Target Equipment"

        required = [
            EvidenceRequirement(
                id="REQ-PID-DOC-001",
                evidence_type=EvidenceType.SOURCE_DOCUMENTS,
                description=f"Authoritative MRPL Knowledge Base operating manual, equipment dossier, or maintenance records for {ent}.",
                mandatory=True,
                authority_requirement=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
                entity_scope=ctx.entity_name,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="RAG retrieval must yield relevant MRPL knowledge documents.",
            ),
            EvidenceRequirement(
                id="REQ-PID-DOC-002",
                evidence_type=EvidenceType.P_AND_ID_SCHEMATIC,
                description=f"P&ID drawing document number and revision metadata for {ent}.",
                mandatory=True,
                authority_requirement=AuthorityLevel.AUTHORITATIVE_PSU,
                entity_scope=ctx.entity_name,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="P&ID drawing number and revision must be matched from knowledge base.",
            ),
        ]

        return EvidenceContract(
            task_id=t_id,
            task_type="pid_documentary_support",
            required_evidence=required,
            optional_evidence=[],
            minimum_coverage=1.0,
            required_source_authority=AuthorityLevel.VERIFIED_ENGINEERING_RECORD,
            freshness_requirements={},
            required_entities=[ctx.entity_name] if ctx.entity_name else [],
            blocking_conditions=["ZERO_RETRIEVED_EVIDENCE_FOR_ORGANIZATION_ENTITY"],
            risk_level="medium",
            created_at=time.time(),
        )

    def _generate_unknown_mrpl_entity_contract(self, ctx: ContractGenerationContext) -> EvidenceContract:
        t_id = ctx.task_id or f"EVID-GUARD-{uuid.uuid4().hex[:6]}"
        ent = ctx.entity_name or "Unknown Equipment"

        required = [
            EvidenceRequirement(
                id="REQ-GUARD-001",
                evidence_type=EvidenceType.EQUIPMENT_DATASHEET,
                description=f"Authoritative MRPL equipment master record or engineering datasheet for {ent}.",
                mandatory=True,
                authority_requirement=AuthorityLevel.AUTHORITATIVE_PSU,
                entity_scope=ctx.entity_name,
                expected_modality=EvidenceModality.DOCUMENT_PDF,
                validation_rule=f"Entity {ent} must exist in MRPL Local Knowledge Base or Asset Registry.",
            )
        ]

        return EvidenceContract(
            task_id=t_id,
            task_type="unknown_mrpl_entity",
            required_evidence=required,
            optional_evidence=[],
            minimum_coverage=1.0,
            required_source_authority=AuthorityLevel.AUTHORITATIVE_PSU,
            freshness_requirements={},
            required_entities=[ctx.entity_name] if ctx.entity_name else [],
            blocking_conditions=[f"MISSING_ENTITY_AUTHORITATIVE_RECORD: {ent}"],
            risk_level="high",
            created_at=time.time(),
        )

    def _generate_general_contract(self, ctx: ContractGenerationContext) -> EvidenceContract:
        t_id = ctx.task_id or f"EVID-GEN-{uuid.uuid4().hex[:6]}"

        required = [
            EvidenceRequirement(
                id="REQ-GEN-001",
                evidence_type=EvidenceType.USER_SCOPE,
                description="User prompt stating topic, question, or task instructions.",
                mandatory=True,
                authority_requirement=AuthorityLevel.ANY,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Prompt text must be non-empty.",
            ),
            EvidenceRequirement(
                id="REQ-GEN-002",
                evidence_type=EvidenceType.GENERAL_KNOWLEDGE_DECLARATION,
                description="Declared context mode acknowledging general pretrained reasoning without unverified PSU claims.",
                mandatory=True,
                authority_requirement=AuthorityLevel.ANY,
                expected_modality=EvidenceModality.TEXT,
                validation_rule="Context guard must mark response as general knowledge if entity is unverified.",
            ),
        ]

        return EvidenceContract(
            task_id=t_id,
            task_type="general_reasoning",
            required_evidence=required,
            optional_evidence=[],
            minimum_coverage=1.0,
            required_source_authority=AuthorityLevel.ANY,
            freshness_requirements={},
            required_entities=[],
            blocking_conditions=[],
            risk_level="low",
            created_at=time.time(),
        )
