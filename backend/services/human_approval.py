import time
import logging
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger("mrpl.approval")


class HumanApprovalState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"


class ApprovalItem(BaseModel):
    request_id: str
    task_type: str
    risk: str
    created_at: float = Field(default_factory=time.time)
    state: HumanApprovalState = Field(HumanApprovalState.PENDING_REVIEW)
    reviewer_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[float] = None
    deliverable_summary: str = ""


class HumanApprovalManager:
    """
    Manages human-in-the-loop signoff gates for High-Risk PSU engineering decisions.
    """

    def __init__(self):
        self._pending_items: Dict[str, ApprovalItem] = {}

    def register_for_review(self, request_id: str, task_type: str, risk: str, summary: str) -> ApprovalItem:
        item = ApprovalItem(
            request_id=request_id,
            task_type=task_type,
            risk=risk,
            deliverable_summary=summary,
            state=HumanApprovalState.PENDING_REVIEW,
        )
        self._pending_items[request_id] = item
        logger.info(f"Registered high-risk request {request_id} for Human Review Gate.")
        return item

    def submit_decision(
        self,
        request_id: str,
        action: str,  # approve, reject, revise
        reviewer_name: str = "PSU Chief Engineer",
        notes: Optional[str] = None,
    ) -> Optional[ApprovalItem]:
        item = self._pending_items.get(request_id)
        if not item:
            return None

        if action.lower() == "approve":
            item.state = HumanApprovalState.APPROVED
        elif action.lower() == "reject":
            item.state = HumanApprovalState.REJECTED
        else:
            item.state = HumanApprovalState.REVISION_REQUESTED

        item.reviewed_by = reviewer_name
        item.reviewer_notes = notes
        item.reviewed_at = time.time()
        logger.info(f"Human decision recorded for {request_id}: {item.state.value} by {reviewer_name}")
        return item

    def get_item(self, request_id: str) -> Optional[ApprovalItem]:
        return self._pending_items.get(request_id)

    def get_all_pending(self) -> List[ApprovalItem]:
        return [i for i in self._pending_items.values() if i.state == HumanApprovalState.PENDING_REVIEW]
