"""
Decision HITL & Deliverable Packaging Service — Phase 4C
Approved Specification: v1.0.0-FINAL-CLARIFIED-R3

Integrates the DecisionEngine outputs with the existing HumanApprovalManager,
enforces role-resolution precedence without hardcoding organizational roles,
and produces auditable decision approval deliverables while preserving complete provenance.

SAFETY INVARIANTS:
1. Purely consumes existing HumanApprovalManager (no parallel state machine).
2. Never alters GovernanceOutcome (e.g. GOVERNANCE_GATE_BLOCKED remains blocked).
3. Zero hardcoded organizational roles (defaults strictly to [] if unresolved).
4. No free-form AI operational recommendations in deliverables.
5. Preserves exact semantics of ENGINEERING_ASSESSMENT_REQUIRED.
6. Human approval is workflow disposition only; NEVER converts to fit_for_service,
   is_safe, statutorily_compliant, or statutory_approval.
7. Preserves complete provenance back to source text spans and the SHA-256 audit hash.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.services.decision.decision_models import (
    DecisionRiskLevel,
    GovernanceOutcome,
    OperationalDecisionPackage,
    PolicyActionTemplate,
    PolicyEvaluationStatus,
    RuleEvaluationResult,
    TemplateActionCode,
)
from backend.services.human_approval import (
    ApprovalItem,
    HumanApprovalManager,
    HumanApprovalState,
)


class DecisionApprovalDeliverable(BaseModel):
    """
    Structured deliverable artifact combining the deterministic decision package
    with human-in-the-loop review state and auditable deliverable text.
    """
    deliverable_id: str
    package_id: str
    entity_tag: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    risk_level: DecisionRiskLevel
    governance_outcome: GovernanceOutcome
    policy_evaluation_status: PolicyEvaluationStatus
    applied_policy_id: Optional[str] = None
    applied_policy_version: Optional[str] = None
    rule_evaluations: List[RuleEvaluationResult] = Field(default_factory=list)
    recommended_action: Optional[str] = None
    action_template: Optional[PolicyActionTemplate] = None
    requires_human_approval: bool
    required_human_roles: List[str] = Field(default_factory=list)
    approval_state: HumanApprovalState
    approval_ticket_id: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewer_notes: Optional[str] = None
    reviewed_at: Optional[float] = None
    evidence_assessment_id: Optional[str] = None
    reconciliation_report_id: Optional[str] = None
    has_contested_evidence: bool = False
    contested_evidence_details: List[str] = Field(default_factory=list)
    provenance_source_spans: List[Dict[str, Any]] = Field(default_factory=list)
    audit_trail_hash: str
    deliverable_summary: str


class DecisionHITLManager:
    """
    Manages HITL workflow integration and deliverable packaging for Phase 4.
    """

    def __init__(self, approval_manager: Optional[HumanApprovalManager] = None):
        self.approval_manager = approval_manager or HumanApprovalManager()

    def create_approval_package(
        self,
        decision_package: OperationalDecisionPackage,
        external_role_config: Optional[Dict[str, List[str]]] = None,
        manager_role_config: Optional[List[str]] = None,
    ) -> DecisionApprovalDeliverable:
        """
        Integrates a decision package into the HITL workflow and generates an auditable deliverable.
        """
        # Resolve human roles according to strict precedence hierarchy:
        # 1. External policy roles (from package)
        # 2. External HITL role config
        # 3. Manager role config
        # 4. Fallback: [] (NEVER hardcode organizational roles)
        resolved_roles = self._resolve_roles(
            package_roles=decision_package.required_human_roles,
            external_role_config=external_role_config,
            manager_role_config=manager_role_config,
            risk_level=decision_package.risk_level,
        )

        # Update package with resolved roles if package did not have them
        if not decision_package.required_human_roles and resolved_roles:
            decision_package = decision_package.model_copy(update={"required_human_roles": resolved_roles})

        # Register in HumanApprovalManager if human approval is required
        approval_state = HumanApprovalState.NOT_REQUIRED
        ticket_id = decision_package.approval_ticket_id

        if decision_package.requires_human_approval:
            ticket_id = ticket_id or f"TICKET-{decision_package.package_id}"
            summary_text = self._build_registration_summary(decision_package, resolved_roles)
            item = self.approval_manager.register_for_review(
                request_id=ticket_id,
                task_type="governance_decision",
                risk=decision_package.risk_level.value,
                summary=summary_text,
            )
            approval_state = item.state
            decision_package = decision_package.model_copy(update={"approval_ticket_id": ticket_id})

        # Detect if any evidence in provenance was contested or unresolvable
        has_contested, contested_details = self._detect_contested_evidence(decision_package)

        # Generate structured deliverable summary text
        deliverable_summary = self._generate_deliverable_summary(decision_package, resolved_roles)

        return DecisionApprovalDeliverable(
            deliverable_id=f"DELIV-{decision_package.package_id}",
            package_id=decision_package.package_id,
            entity_tag=decision_package.entity_tag,
            risk_level=decision_package.risk_level,
            governance_outcome=decision_package.governance_outcome,
            policy_evaluation_status=decision_package.policy_evaluation_status,
            applied_policy_id=decision_package.applied_policy_id,
            applied_policy_version=decision_package.applied_policy_version,
            rule_evaluations=decision_package.rule_evaluations,
            recommended_action=decision_package.recommended_action,
            action_template=decision_package.action_template,
            requires_human_approval=decision_package.requires_human_approval,
            required_human_roles=resolved_roles,
            approval_state=approval_state,
            approval_ticket_id=ticket_id,
            evidence_assessment_id=decision_package.evidence_assessment_id,
            reconciliation_report_id=decision_package.reconciliation_report_id,
            has_contested_evidence=has_contested,
            contested_evidence_details=contested_details,
            provenance_source_spans=decision_package.provenance_source_spans,
            audit_trail_hash=decision_package.audit_trail_hash,
            deliverable_summary=deliverable_summary,
        )

    def submit_human_disposition(
        self,
        deliverable: DecisionApprovalDeliverable,
        action: str,  # "approve", "reject", "revise"
        reviewer_name: str,
        reviewer_notes: Optional[str] = None,
    ) -> DecisionApprovalDeliverable:
        """
        Record a human engineering workflow disposition using the existing HumanApprovalManager.
        Safety Invariant: Human disposition records workflow sign-off only; it NEVER creates
        autonomous statutory clearance, safety approval, or fit-for-service determinations.
        """
        ticket_id = deliverable.approval_ticket_id
        if not ticket_id:
            raise ValueError(f"Deliverable {deliverable.deliverable_id} has no associated approval ticket ID.")

        item = self.approval_manager.submit_decision(
            request_id=ticket_id,
            action=action,
            reviewer_name=reviewer_name,
            notes=reviewer_notes,
        )
        if not item:
            raise ValueError(f"Approval ticket {ticket_id} not found in HumanApprovalManager.")

        return deliverable.model_copy(
            update={
                "approval_state": item.state,
                "reviewed_by": item.reviewed_by,
                "reviewer_notes": item.reviewer_notes,
                "reviewed_at": item.reviewed_at,
            }
        )

    # ─────────────────────────────────────────────────────────────
    # Internal Helpers
    # ─────────────────────────────────────────────────────────────

    def _resolve_roles(
        self,
        package_roles: List[str],
        external_role_config: Optional[Dict[str, List[str]]],
        manager_role_config: Optional[List[str]],
        risk_level: DecisionRiskLevel,
    ) -> List[str]:
        """
        Resolve human reviewer roles strictly following the 4-tier hierarchy.
        """
        # Tier 1: Roles defined in package from external policy
        if package_roles:
            return list(package_roles)

        # Tier 2: External HITL role configuration mapping
        if external_role_config and risk_level.value in external_role_config:
            return list(external_role_config[risk_level.value])

        # Tier 3: Manager configured roles
        if manager_role_config:
            return list(manager_role_config)

        # Tier 4: Fallback to [] (Never hardcode organizational roles)
        return []

    def _detect_contested_evidence(self, pkg: OperationalDecisionPackage) -> tuple[bool, List[str]]:
        """
        Detect whether underlying evidence was contradictory or contested.
        """
        details: List[str] = []
        if pkg.policy_evaluation_status == PolicyEvaluationStatus.CONFLICT_PREVENTS_EVALUATION:
            details.append("Conflicting observations prevent deterministic policy evaluation.")
        if pkg.governance_outcome == GovernanceOutcome.GOVERNANCE_GATE_BLOCKED:
            details.append("Governance gate blocked due to evidence/conflict prerequisites.")

        return (len(details) > 0, details)

    def _build_registration_summary(self, pkg: OperationalDecisionPackage, roles: List[str]) -> str:
        """
        Build concise summary for HumanApprovalManager registration.
        """
        role_str = ", ".join(roles) if roles else "Unassigned (General Human Review)"
        return (
            f"Asset Tag: {pkg.entity_tag} | Risk: {pkg.risk_level.value} | "
            f"Governance: {pkg.governance_outcome.value} | Policy: {pkg.applied_policy_id or 'None'} | "
            f"Required Roles: {role_str} | Action: {pkg.recommended_action or 'None'} | "
            f"Audit Hash: {pkg.audit_trail_hash[:12]}..."
        )

    def _generate_deliverable_summary(self, pkg: OperationalDecisionPackage, roles: List[str]) -> str:
        """
        Generate structured, auditable text without free-form AI recommendations.
        """
        lines = [
            f"# Operational Governance Deliverable — Asset: {pkg.entity_tag}",
            f"- **Package ID**: {pkg.package_id}",
            f"- **Risk Level**: {pkg.risk_level.value}",
            f"- **Governance Outcome**: {pkg.governance_outcome.value}",
            f"- **Policy Evaluation Status**: {pkg.policy_evaluation_status.value}",
            f"- **Applied Policy**: {pkg.applied_policy_id or 'None'} (Version: {pkg.applied_policy_version or 'N/A'})",
            f"- **Human Approval Required**: {pkg.requires_human_approval}",
            f"- **Required Reviewer Roles**: {', '.join(roles) if roles else 'None / Unresolved'}",
            f"- **Recommended Action**: {pkg.recommended_action or 'None'}",
            f"- **SHA-256 Audit Trail Hash**: `{pkg.audit_trail_hash}`",
        ]
        if pkg.rule_evaluations:
            lines.append("\n## Policy Rule Evaluations:")
            for r in pkg.rule_evaluations:
                status_label = "SATISFIED" if r.satisfied else "BREACHED"
                lines.append(f"- **{r.rule_id}** ({r.target_property}): {status_label} — {r.evaluation_notes}")

        return "\n".join(lines)
