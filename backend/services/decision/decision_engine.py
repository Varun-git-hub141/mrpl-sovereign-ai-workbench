"""
Decision & Policy Evaluation Engine — Phase 4B
Approved Specification: v1.0.0-FINAL-CLARIFIED-R3

Provides deterministic governance routing, external statutory/engineering policy evaluation,
audit hash generation, and complete provenance preservation.

SAFETY INVARIANTS:
1. Purely deterministic execution: identical inputs produce identical outcomes and audit hashes.
2. Zero hardcoded statutory limits, corrosion thresholds, or retirement values.
3. Zero hardcoded organizational roles (required_human_roles defaults to []).
4. No numeric scoring, averaging of conflicting observations, or synthetic ground truth.
5. No free-form AI recommendations (recommended_action must originate from policy templates, None,
   or 'REQUIRES_ENGINEER_DISPOSITION').
6. No autonomous statutory/safety/fit-for-service verdicts.
7. No physical plant control (DCS/SCADA/PLC) integration.
"""

import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple

from backend.services.decision.decision_models import (
    DecisionRiskLevel,
    GovernanceOutcome,
    OperationalDecisionPackage,
    PolicyActionTemplate,
    PolicyEvaluationStatus,
    PolicyRule,
    RuleEvaluationResult,
    StatutoryDecisionPolicy,
    TemplateActionCode,
)
from backend.services.evidence.evidence_models import (
    EvidenceAssessment,
    SufficiencyStatus,
)
from backend.services.evidence.reconciliation_models import (
    ConsistencyState,
    EvidenceObservation,
    EvidenceSearchStatus,
    ReconciliationRelationship,
    ReconciliationResult,
    ReconciliationStatus,
    RelationshipType,
)


class DecisionEngine:
    """
    Deterministic Decision & Policy Evaluation Engine.
    Evaluates external policies, enforces governance safety gates, and produces
    cryptographically auditable OperationalDecisionPackages.
    """

    def evaluate(
        self,
        entity_tag: str,
        risk_level: DecisionRiskLevel = DecisionRiskLevel.LOW,
        evidence_assessment: Optional[EvidenceAssessment] = None,
        reconciliation_result: Optional[ReconciliationResult] = None,
        policy: Optional[StatutoryDecisionPolicy] = None,
        observations: Optional[List[EvidenceObservation]] = None,
        required_human_roles: Optional[List[str]] = None,
        package_id: Optional[str] = None,
        approval_ticket_id: Optional[str] = None,
    ) -> OperationalDecisionPackage:
        """
        Execute deterministic evaluation and routing for an industrial asset request.
        """
        resolved_package_id = package_id or f"PKG-{uuid.uuid4().hex[:12].upper()}"

        # Consolidate observations from reconciliation_result if not explicitly provided
        all_obs = observations or []
        if reconciliation_result and reconciliation_result.all_observations:
            all_obs = reconciliation_result.all_observations

        # Collect provenance source spans
        provenance_spans = self._extract_provenance_spans(
            evidence_assessment=evidence_assessment,
            reconciliation_result=reconciliation_result,
            observations=all_obs,
        )

        # Resolve human roles (No hardcoding)
        resolved_roles = self._resolve_roles(policy=policy, explicit_roles=required_human_roles)

        # -------------------------------------------------------------
        # 1. Evaluate External Policy Rules (if policy provided)
        # -------------------------------------------------------------
        policy_status, rule_evaluations, matched_template, has_conditions = (
            self._evaluate_policy(policy=policy, observations=all_obs, reconciliation_result=reconciliation_result)
        )

        # -------------------------------------------------------------
        # 2. Execute Mandatory Governance Routing Precedence
        # -------------------------------------------------------------
        governance_outcome, requires_hitl, recommended_action, final_template = (
            self._route_governance(
                risk_level=risk_level,
                evidence_assessment=evidence_assessment,
                reconciliation_result=reconciliation_result,
                policy=policy,
                policy_status=policy_status,
                matched_template=matched_template,
                has_conditions=has_conditions,
            )
        )

        # -------------------------------------------------------------
        # 3. Construct Canonical Hash and Final Decision Package
        # -------------------------------------------------------------
        audit_hash = self._compute_canonical_audit_hash(
            package_id=resolved_package_id,
            entity_tag=entity_tag,
            risk_level=risk_level,
            governance_outcome=governance_outcome,
            policy_evaluation_status=policy_status,
            applied_policy_id=policy.policy_id if policy else None,
            applied_policy_version=policy.policy_version if policy else None,
            rule_evaluations=rule_evaluations,
            recommended_action=recommended_action,
            requires_human_approval=requires_hitl,
            required_human_roles=resolved_roles,
            provenance_source_spans=provenance_spans,
        )

        return OperationalDecisionPackage(
            package_id=resolved_package_id,
            entity_tag=entity_tag,
            risk_level=risk_level,
            governance_outcome=governance_outcome,
            policy_evaluation_status=policy_status,
            applied_policy_id=policy.policy_id if policy else None,
            applied_policy_version=policy.policy_version if policy else None,
            rule_evaluations=rule_evaluations,
            recommended_action=recommended_action,
            action_template=final_template,
            requires_human_approval=requires_hitl,
            required_human_roles=resolved_roles,
            approval_ticket_id=approval_ticket_id,
            evidence_assessment_id=evidence_assessment.task_id if evidence_assessment else None,
            reconciliation_report_id=reconciliation_result.task_id if reconciliation_result else None,
            provenance_source_spans=provenance_spans,
            audit_trail_hash=audit_hash,
        )

    # ─────────────────────────────────────────────────────────────
    # Routing Logic (Priority 1 -> 6)
    # ─────────────────────────────────────────────────────────────

    def _route_governance(
        self,
        risk_level: DecisionRiskLevel,
        evidence_assessment: Optional[EvidenceAssessment],
        reconciliation_result: Optional[ReconciliationResult],
        policy: Optional[StatutoryDecisionPolicy],
        policy_status: PolicyEvaluationStatus,
        matched_template: Optional[PolicyActionTemplate],
        has_conditions: bool,
    ) -> Tuple[GovernanceOutcome, bool, Optional[str], Optional[PolicyActionTemplate]]:
        """
        Execute deterministic routing according to the approved 6-rule hierarchy.
        """
        # RULE 1: Phase 2 Evidence Precondition Gate
        if evidence_assessment is not None:
            if evidence_assessment.overall_status in [
                SufficiencyStatus.BLOCKED,
                SufficiencyStatus.INSUFFICIENT,
                SufficiencyStatus.CONTRADICTORY,
            ]:
                return (
                    GovernanceOutcome.GOVERNANCE_GATE_BLOCKED,
                    True,
                    TemplateActionCode.REQUIRES_ENGINEER_DISPOSITION.value,
                    None,
                )

        # RULE 2: Phase 3 Conflict / Anomaly Search Gate
        if reconciliation_result is not None:
            has_conflicts = (
                len(reconciliation_result.active_conflicts) > 0
                or len(reconciliation_result.unresolved_conflicts) > 0
                or reconciliation_result.reconciliation_status == ReconciliationStatus.UNRESOLVED_CONFLICT
                or reconciliation_result.consistency_state == ConsistencyState.CONFLICTING
            )

            has_unresolved_anomaly_search = False
            for rel in reconciliation_result.relationships:
                is_anomaly_rel = (
                    rel.is_anomaly
                    or rel.relationship_type in [
                        RelationshipType.ANOMALOUS_PROGRESSION_CANDIDATE,
                        RelationshipType.ANOMALOUS_PROGRESSION,
                    ]
                )
                if is_anomaly_rel:
                    if (
                        rel.relationship_type == RelationshipType.ANOMALOUS_PROGRESSION_CANDIDATE
                        or rel.evidence_search_status in [
                            EvidenceSearchStatus.EVIDENCE_SEARCH_NOT_PERFORMED,
                            EvidenceSearchStatus.EVIDENCE_SEARCH_IN_PROGRESS,
                        ]
                    ):
                        has_unresolved_anomaly_search = True
                        break

            if has_conflicts or has_unresolved_anomaly_search:
                return (
                    GovernanceOutcome.GOVERNANCE_GATE_BLOCKED,
                    True,
                    TemplateActionCode.REQUIRES_ENGINEER_DISPOSITION.value,
                    None,
                )

        # RULE 3: External Policy Breach Gate
        if policy_status == PolicyEvaluationStatus.CRITERIA_BREACHED:
            recommended_action = (
                matched_template.action_code.value
                if matched_template
                else TemplateActionCode.REQUIRES_ENGINEER_DISPOSITION.value
            )
            return (
                GovernanceOutcome.ESCALATE_HUMAN_REVIEW,
                True,
                recommended_action,
                matched_template,
            )

        # RULE 4: High / Statutory / Critical Safety Gate (Mandatory HITL)
        if risk_level in [
            DecisionRiskLevel.HIGH,
            DecisionRiskLevel.STATUTORY,
            DecisionRiskLevel.CRITICAL_SAFETY,
        ]:
            if policy_status == PolicyEvaluationStatus.CRITERIA_SATISFIED and has_conditions:
                recommended_action = matched_template.action_code.value if matched_template else None
                return (
                    GovernanceOutcome.PROCEED_WITH_CONDITIONS,
                    True,
                    recommended_action,
                    matched_template,
                )
            elif (
                policy_status in [
                    PolicyEvaluationStatus.DATA_INSUFFICIENT_FOR_POLICY,
                    PolicyEvaluationStatus.CONFLICT_PREVENTS_EVALUATION,
                ]
            ):
                return (
                    GovernanceOutcome.ESCALATE_HUMAN_REVIEW,
                    True,
                    TemplateActionCode.REQUIRES_ENGINEER_DISPOSITION.value,
                    None,
                )
            else:
                recommended_action = matched_template.action_code.value if matched_template else None
                return (
                    GovernanceOutcome.ESCALATE_HUMAN_REVIEW,
                    True,
                    recommended_action,
                    matched_template,
                )

        # RULE 5: Low / Medium Risk with Policy Conditions
        if risk_level in [DecisionRiskLevel.LOW, DecisionRiskLevel.MEDIUM]:
            if policy_status == PolicyEvaluationStatus.CRITERIA_SATISFIED and has_conditions:
                recommended_action = matched_template.action_code.value if matched_template else None
                return (
                    GovernanceOutcome.PROCEED_WITH_CONDITIONS,
                    False,
                    recommended_action,
                    matched_template,
                )
            elif (
                policy_status in [
                    PolicyEvaluationStatus.DATA_INSUFFICIENT_FOR_POLICY,
                    PolicyEvaluationStatus.CONFLICT_PREVENTS_EVALUATION,
                ]
            ):
                return (
                    GovernanceOutcome.ESCALATE_HUMAN_REVIEW,
                    True,
                    TemplateActionCode.REQUIRES_ENGINEER_DISPOSITION.value,
                    None,
                )

        # RULE 6: Low / Medium Advisory Gate
        recommended_action = matched_template.action_code.value if matched_template else None
        return (
            GovernanceOutcome.PROCEED_ADVISORY,
            False,
            recommended_action,
            matched_template,
        )

    # ─────────────────────────────────────────────────────────────
    # Policy Evaluation Logic
    # ─────────────────────────────────────────────────────────────

    def _evaluate_policy(
        self,
        policy: Optional[StatutoryDecisionPolicy],
        observations: List[EvidenceObservation],
        reconciliation_result: Optional[ReconciliationResult],
    ) -> Tuple[PolicyEvaluationStatus, List[RuleEvaluationResult], Optional[PolicyActionTemplate], bool]:
        """
        Evaluate supplied external policy rules deterministically.
        """
        if not policy:
            return PolicyEvaluationStatus.POLICY_NOT_SUPPLIED, [], None, False

        if not policy.rules:
            return PolicyEvaluationStatus.CRITERIA_SATISFIED, [], None, False

        rule_evaluations: List[RuleEvaluationResult] = []
        any_breach = False
        data_insufficient = False
        conflict_detected = False
        breach_template: Optional[PolicyActionTemplate] = None
        satisfied_template: Optional[PolicyActionTemplate] = None
        has_conditions = False

        for rule in policy.rules:
            # Locate observation value for target_property
            val_status, observed_val, obs_note = self._get_property_value(
                target_property=rule.target_property,
                observations=observations,
                reconciliation_result=reconciliation_result,
            )

            if val_status == "INSUFFICIENT":
                data_insufficient = True
                rule_evaluations.append(
                    RuleEvaluationResult(
                        rule_id=rule.rule_id,
                        target_property=rule.target_property,
                        observed_value=None,
                        threshold_value=rule.threshold_value,
                        operator=rule.operator,
                        satisfied=False,
                        evaluation_notes=f"Missing evidence for required property '{rule.target_property}'.",
                    )
                )
                continue
            elif val_status == "CONFLICT":
                conflict_detected = True
                rule_evaluations.append(
                    RuleEvaluationResult(
                        rule_id=rule.rule_id,
                        target_property=rule.target_property,
                        observed_value=None,
                        threshold_value=rule.threshold_value,
                        operator=rule.operator,
                        satisfied=False,
                        evaluation_notes=f"Conflicting observations prevent deterministic evaluation of '{rule.target_property}'.",
                    )
                )
                continue

            # Evaluate operator expression
            satisfied, eval_note = self._evaluate_operator(
                observed_value=observed_val,
                operator=rule.operator,
                threshold_value=rule.threshold_value,
            )

            rule_evaluations.append(
                RuleEvaluationResult(
                    rule_id=rule.rule_id,
                    target_property=rule.target_property,
                    observed_value=observed_val,
                    threshold_value=rule.threshold_value,
                    operator=rule.operator,
                    satisfied=satisfied,
                    evaluation_notes=eval_note,
                )
            )

            if not satisfied:
                any_breach = True
                if rule.on_breach_template and not breach_template:
                    breach_template = rule.on_breach_template
            else:
                if rule.on_satisfied_template:
                    satisfied_template = rule.on_satisfied_template
                    if rule.on_satisfied_template.action_code != TemplateActionCode.NO_ACTION_REQUIRED:
                        has_conditions = True

        # Determine aggregate status
        if data_insufficient:
            return PolicyEvaluationStatus.DATA_INSUFFICIENT_FOR_POLICY, rule_evaluations, None, False
        if conflict_detected:
            return PolicyEvaluationStatus.CONFLICT_PREVENTS_EVALUATION, rule_evaluations, None, False
        if any_breach:
            return PolicyEvaluationStatus.CRITERIA_BREACHED, rule_evaluations, breach_template, False

        return PolicyEvaluationStatus.CRITERIA_SATISFIED, rule_evaluations, satisfied_template, has_conditions

    def _get_property_value(
        self,
        target_property: str,
        observations: List[EvidenceObservation],
        reconciliation_result: Optional[ReconciliationResult],
    ) -> Tuple[str, Any, str]:
        """
        Locate candidate observation value for a property without averaging or guessing.
        """
        matching_obs = [
            obs for obs in observations
            if obs.property_name.lower() == target_property.lower()
        ]

        if not matching_obs:
            return "INSUFFICIENT", None, f"No observations found for '{target_property}'."

        if len(matching_obs) == 1:
            obs_val = getattr(matching_obs[0], "value", getattr(matching_obs[0], "observed_value", None))
            return "OK", obs_val, "Single observation available."

        # Multiple observations exist: check if applicability context has resolved candidate
        if reconciliation_result and reconciliation_result.applicable_contexts:
            for ctx in reconciliation_result.applicable_contexts:
                if (
                    ctx.property_name.lower() == target_property.lower()
                    and ctx.selected_observation_id is not None
                ):
                    for obs in matching_obs:
                        if obs.observation_id == ctx.selected_observation_id:
                            obs_val = getattr(obs, "value", getattr(obs, "observed_value", None))
                            return "OK", obs_val, f"Selected via applicability policy {ctx.policy_identifier}."

        # Check if all observations report the exact identical value (corroborating)
        distinct_vals = {getattr(obs, "value", getattr(obs, "observed_value", None)) for obs in matching_obs}
        if len(distinct_vals) == 1:
            obs_val = getattr(matching_obs[0], "value", getattr(matching_obs[0], "observed_value", None))
            return "OK", obs_val, "Corroborating matching observations."

        # Conflicting unresolved observations exist: DO NOT AVERAGE
        return "CONFLICT", None, f"Multiple unresolved distinct observations for '{target_property}'."

    def _evaluate_operator(
        self,
        observed_value: Any,
        operator: str,
        threshold_value: Any,
    ) -> Tuple[bool, str]:
        """
        Execute deterministic mathematical comparison.
        """
        try:
            obs = float(observed_value) if isinstance(observed_value, (int, float, str)) and str(observed_value).replace('.', '', 1).isdigit() else observed_value
            thresh = threshold_value

            if operator == ">":
                passed = float(obs) > float(thresh)
                note = f"Observed {obs} > threshold {thresh}: {passed}"
            elif operator == ">=":
                passed = float(obs) >= float(thresh)
                note = f"Observed {obs} >= threshold {thresh}: {passed}"
            elif operator == "<":
                passed = float(obs) < float(thresh)
                note = f"Observed {obs} < threshold {thresh}: {passed}"
            elif operator == "<=":
                passed = float(obs) <= float(thresh)
                note = f"Observed {obs} <= threshold {thresh}: {passed}"
            elif operator == "==":
                passed = obs == thresh
                note = f"Observed {obs} == threshold {thresh}: {passed}"
            elif operator == "!=":
                passed = obs != thresh
                note = f"Observed {obs} != threshold {thresh}: {passed}"
            elif operator == "IN_RANGE":
                if isinstance(thresh, (list, tuple)) and len(thresh) == 2:
                    passed = float(thresh[0]) <= float(obs) <= float(thresh[1])
                    note = f"Observed {obs} in range [{thresh[0]}, {thresh[1]}]: {passed}"
                else:
                    return False, f"Invalid IN_RANGE threshold structure: {thresh}"
            else:
                return False, f"Unsupported policy operator '{operator}'"

            return passed, note
        except Exception as e:
            return False, f"Comparison error: {str(e)}"

    # ─────────────────────────────────────────────────────────────
    # Helpers: Roles, Provenance, and SHA-256 Audit Hashing
    # ─────────────────────────────────────────────────────────────

    def _resolve_roles(
        self,
        policy: Optional[StatutoryDecisionPolicy],
        explicit_roles: Optional[List[str]],
    ) -> List[str]:
        """
        Resolve human reviewer roles from external inputs without hardcoding defaults.
        """
        if policy and policy.required_human_roles:
            return list(policy.required_human_roles)
        if explicit_roles:
            return list(explicit_roles)
        return []

    def _extract_provenance_spans(
        self,
        evidence_assessment: Optional[EvidenceAssessment],
        reconciliation_result: Optional[ReconciliationResult],
        observations: List[EvidenceObservation],
    ) -> List[Dict[str, Any]]:
        """
        Extract verbatim source document spans and references.
        """
        spans: List[Dict[str, Any]] = []
        for obs in observations:
            obs_val = getattr(obs, "value", getattr(obs, "observed_value", None))
            raw_doc = getattr(obs, "source_document", getattr(obs, "raw_source_document", ""))
            raw_statement = getattr(obs, "raw_statement", getattr(obs, "verbatim_source_span", ""))
            page_info = getattr(obs, "page_number", getattr(obs, "source_page_or_sheet", ""))
            doc_ref = getattr(obs, "document_id", getattr(obs, "document_reference", None))
            span_entry = {
                "observation_id": obs.observation_id,
                "property_name": obs.property_name,
                "observed_value": obs_val,
                "raw_source_document": raw_doc,
                "source_page_or_sheet": page_info,
                "verbatim_source_span": raw_statement,
                "document_reference": doc_ref,
            }
            spans.append(span_entry)

        if evidence_assessment:
            spans.append({
                "assessment_id": evidence_assessment.task_id,
                "overall_status": evidence_assessment.overall_status.value,
                "coverage_score": evidence_assessment.coverage_score,
                "debt_summary": evidence_assessment.evidence_debt.debt_summary if evidence_assessment.evidence_debt else "",
            })

        return spans

    def _compute_canonical_audit_hash(
        self,
        package_id: str,
        entity_tag: str,
        risk_level: DecisionRiskLevel,
        governance_outcome: GovernanceOutcome,
        policy_evaluation_status: PolicyEvaluationStatus,
        applied_policy_id: Optional[str],
        applied_policy_version: Optional[str],
        rule_evaluations: List[RuleEvaluationResult],
        recommended_action: Optional[str],
        requires_human_approval: bool,
        required_human_roles: List[str],
        provenance_source_spans: List[Dict[str, Any]],
    ) -> str:
        """
        Compute deterministic SHA-256 hash over canonical representation.
        """
        canonical_dict = {
            "package_id": package_id,
            "entity_tag": entity_tag,
            "risk_level": risk_level.value,
            "governance_outcome": governance_outcome.value,
            "policy_evaluation_status": policy_evaluation_status.value,
            "applied_policy_id": applied_policy_id,
            "applied_policy_version": applied_policy_version,
            "rule_evaluations": [
                {
                    "rule_id": r.rule_id,
                    "target_property": r.target_property,
                    "observed_value": r.observed_value,
                    "threshold_value": r.threshold_value,
                    "operator": r.operator,
                    "satisfied": r.satisfied,
                    "evaluation_notes": r.evaluation_notes,
                }
                for r in rule_evaluations
            ],
            "recommended_action": recommended_action,
            "requires_human_approval": requires_human_approval,
            "required_human_roles": sorted(required_human_roles),
            "provenance_source_spans": provenance_source_spans,
        }
        canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
