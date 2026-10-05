import logging
from typing import Dict, Any, List, Optional
from backend.models.task_profile import TaskProfile, RiskLevel, InputModality, TaskType
from backend.models.routing_decision import RoutingDecision
from backend.models.execution_plan import (
    ExecutionPlan,
    ModelRoleAssignment,
    VerificationSpec,
    ExecutionStrategy,
)
from backend.services.registry import ModelRegistry

logger = logging.getLogger("mrpl.planner")


class ExecutionPlanner:
    """
    Constructs the first-class ExecutionPlan object defining the complete
    local execution, verification, and governance strategy for a given task.
    """

    def __init__(self, registry: ModelRegistry):
        self.registry = registry

    def create_execution_plan(self, task: TaskProfile, decision: RoutingDecision) -> ExecutionPlan:
        # Check if unknown organization-specific entity requires strict Context Guard plan
        status_str = str(task.entity_resolution_status)
        primary_role = next((m for m in decision.selected_models if m.role == "primary"), None)
        if "NOT_FOUND_IN_KB" in status_str or (primary_role and primary_role.ollama_name == "NONE"):
            primary_assignment = ModelRoleAssignment(
                model_id="MRPL_CONTEXT_GUARD",
                ollama_name="NONE",
                display_name="NONE",
                role="primary",
                architecture="guard",
            )
            return ExecutionPlan(
                request_id=task.request_id or decision.request_id,
                risk=task.risk,
                strategy=ExecutionStrategy.SINGLE_PASS_DIRECT,
                primary_model=primary_assignment,
                verifier_model=None,
                verification_independence="NOT_APPLICABLE",
                required_tools=["MRPL_CONTEXT_GUARD"],
                required_capabilities={"safety": 1.0},
                verification_spec=VerificationSpec(
                    cross_model="NOT_REQUIRED",
                    evidence="NOT_REQUIRED",
                    deterministic="NOT_REQUIRED",
                    contradiction_check="NOT_REQUIRED",
                ),
                human_approval_required=False,
                fallback_models=[],
                deliverable_type="guarded_entity_resolution_refusal",
                local_only=True,
                rag_required=False,
                plan_rationale="Organization-specific entity was not found in the MRPL Local Knowledge Base.",
            )

        # 1. Resolve Primary Model
        if not primary_role:
            raise ValueError("No primary model selected in routing decision.")

        primary_profile = (self.registry.get_by_id(primary_role.model_id) or self.registry.get_by_name(primary_role.ollama_name)) if self.registry else None
        primary_arch = primary_profile.family if primary_profile else ("qwen2" if "coder" in primary_role.ollama_name else "qwen3" if "qwen3" in primary_role.ollama_name else "qwen25vl" if "vl" in primary_role.ollama_name else "unknown")

        primary_assignment = ModelRoleAssignment(
            model_id=primary_role.model_id,
            ollama_name=primary_role.ollama_name,
            display_name=primary_role.display_name or primary_role.ollama_name,
            role="primary",
            architecture=primary_arch,
        )

        # 2. Resolve Verifier Model & Independence Level
        verifier_assignment = None
        independence_level = "NOT_APPLICABLE"

        verifier_role = next((m for m in decision.selected_models if m.role == "independent_verifier"), None)
        if verifier_role:
            verifier_profile = (self.registry.get_by_id(verifier_role.model_id) or self.registry.get_by_name(verifier_role.ollama_name)) if self.registry else None
            verifier_arch = verifier_profile.family if verifier_profile else ("qwen2" if "coder" in verifier_role.ollama_name else "qwen3" if "qwen3" in verifier_role.ollama_name else "qwen25vl" if "vl" in verifier_role.ollama_name else "unknown")

            verifier_assignment = ModelRoleAssignment(
                model_id=verifier_role.model_id,
                ollama_name=verifier_role.ollama_name,
                display_name=verifier_role.display_name or verifier_role.ollama_name,
                role="independent_verifier",
                architecture=verifier_arch,
            )

            # Check genuine architecture diversity
            if verifier_arch != primary_arch and verifier_arch not in ("unknown", ""):
                independence_level = "HIGHER"
            else:
                independence_level = "LIMITED"

        # 3. Determine Verification Requirements
        is_high_risk = task.risk == RiskLevel.HIGH
        is_calc = (
            task.task_type == TaskType.ENGINEERING_CALCULATION
            or task.required_capabilities.mathematics > 0.80
            or "calculate" in task.intent.lower()
        )
        is_doc = task.task_type in [
            TaskType.MULTIMODAL_DOCUMENT_ANALYSIS,
            TaskType.EQUIPMENT_APPROVAL,
            TaskType.POLICY_COMPLIANCE,
        ] or task.modality in [InputModality.VISION, InputModality.DOCUMENT_PDF, InputModality.SPREADSHEET]

        cross_model_req = "REQUIRED" if (is_high_risk or (verifier_assignment is not None)) else "NOT_REQUIRED"
        evidence_req = "REQUIRED" if (is_doc or is_high_risk) else "NOT_REQUIRED"
        deterministic_req = "REQUIRED" if is_calc else "NOT_REQUIRED"
        contradiction_req = "REQUIRED"

        verification_spec = VerificationSpec(
            cross_model=cross_model_req,
            evidence=evidence_req,
            deterministic=deterministic_req,
            contradiction_check=contradiction_req,
        )

        # 4. Determine Required Tools & Sandboxes
        required_tools = list(task.required_tools)
        if is_calc or task.task_type == TaskType.CODING:
            if "python_calculator" not in required_tools:
                required_tools.append("python_calculator")
        if task.modality in [InputModality.VISION, InputModality.DOCUMENT_PDF]:
            if "vision_multimodal_extractor" not in required_tools:
                required_tools.append("vision_multimodal_extractor")
        if is_doc or "ENGINEERING RAG" in task.required_tools:
            if "ENGINEERING RAG" not in required_tools:
                required_tools.append("ENGINEERING RAG")
            if "local_rag" not in required_tools:
                required_tools.append("local_rag")

        # 5. Determine Fallback Models (Ordered eligible candidates excluding selected primary)
        fallback_models = [
            c.ollama_name for c in decision.candidates
            if c.eligible and c.ollama_name != primary_assignment.ollama_name
        ]

        # 6. Expected Deliverable Type
        if task.task_type == TaskType.EQUIPMENT_APPROVAL:
            deliverable_type = "approval_recommendation_and_evidence_trace"
        elif task.task_type == TaskType.ENGINEERING_CALCULATION:
            deliverable_type = "engineering_calculation_sheet"
        elif task.task_type == TaskType.CODING:
            deliverable_type = "verified_source_code"
        elif task.task_type == TaskType.MULTIMODAL_DOCUMENT_ANALYSIS:
            deliverable_type = "inspection_and_equipment_trace_report"
        elif task.task_type == TaskType.DOCUMENT_QA:
            deliverable_type = "document_qa"
        elif task.task_type == TaskType.GENERAL_REASONING:
            deliverable_type = "general_reasoning"
        else:
            deliverable_type = "verified_technical_summary"

        # 7. Plan Strategy & Rationale
        strategy = (
            ExecutionStrategy.MULTI_MODEL_CROSS_VERIFICATION
            if verifier_assignment
            else (ExecutionStrategy.DETERMINISTIC_TOOL_VERIFICATION if is_calc else ExecutionStrategy.SINGLE_PASS_DIRECT)
        )

        rationale = (
            f"Execution plan for {task.task_type.value} under {task.risk.value.upper()} risk protocol. "
            f"Primary model '{primary_assignment.ollama_name}' assigned for generation. "
        )
        if verifier_assignment:
            rationale += (
                f"Independent verifier '{verifier_assignment.ollama_name}' assigned for dual-model verification "
                f"with {independence_level} architectural diversity."
            )
        else:
            rationale += "Single-pass execution with deterministic tool checks."

        return ExecutionPlan(
            request_id=decision.request_id,
            risk=task.risk,
            strategy=strategy,
            primary_model=primary_assignment,
            verifier_model=verifier_assignment,
            verification_independence=independence_level,
            required_tools=required_tools,
            required_capabilities=task.required_capabilities.to_score_dict(),
            verification_spec=verification_spec,
            human_approval_required=is_high_risk,
            fallback_models=fallback_models,
            deliverable_type=deliverable_type,
            local_only=True,
            vision_required=task.modality == InputModality.VISION,
            ocr_required=task.modality in [InputModality.VISION, InputModality.DOCUMENT_PDF],
            rag_required="local_rag" in required_tools,
            plan_rationale=rationale,
        )
