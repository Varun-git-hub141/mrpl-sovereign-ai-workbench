import json
import os
import time
import uuid
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "activity_history.json")

class ActivityHistoryStore:
    """
    On-premise persistent Activity & Execution History store.
    Saves full execution records including query, intent, models, deliverables,
    and granular provenance (retrieved documents, calculation paths, claims).
    """

    def __init__(self, storage_path: str = HISTORY_FILE, max_items: int = 250):
        self.storage_path = os.path.abspath(storage_path)
        self.max_items = max_items
        self._lock = threading.Lock()
        self._items: List[Dict[str, Any]] = []
        self._load_from_disk()

    def _format_time_ago(self, ts: float) -> str:
        diff = time.time() - ts
        if diff < 60:
            return "Just now"
        elif diff < 3600:
            mins = int(diff / 60)
            return f"{mins} min{'s' if mins != 1 else ''} ago"
        elif diff < 86400:
            hrs = int(diff / 3600)
            return f"{hrs} hour{'s' if hrs != 1 else ''} ago"
        elif diff < 172800:
            return "Yesterday"
        else:
            days = int(diff / 86400)
            return f"{days} days ago"

    def _load_from_disk(self):
        with self._lock:
            if os.path.exists(self.storage_path):
                try:
                    with open(self.storage_path, "r", encoding="utf-8") as f:
                        self._items = json.load(f)
                except Exception as e:
                    print(f"Warning: Failed to load activity history: {e}")
                    self._items = []
            else:
                self._items = self._get_initial_seed_items()
                self._save_to_disk_unlocked()

    def _save_to_disk_unlocked(self):
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._items, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Failed to save activity history to disk: {e}")

    def _get_initial_seed_items(self) -> List[Dict[str, Any]]:
        now = time.time()
        return [
            {
                "id": "act-seed-001",
                "timestamp": now - 7200,
                "formatted_time": datetime.fromtimestamp(now - 7200).strftime("%d %b %Y %H:%M"),
                "time_ago": "2 hours ago",
                "query": "Analyze P-201_Inspection_Report.pdf and extract wall thickness values",
                "operation_type": "DOCUMENT_ANALYSIS",
                "file_badge": "PDF",
                "badge_class": "pdf",
                "file_name": "P-201_Inspection_Report.pdf",
                "entity_tag": "P-201",
                "routed_model": "qwen2.5-coder:3b",
                "executed_model": "qwen2.5-coder:3b",
                "execution_status": "MRPL_VERIFIED",
                "output_type": "CHAT_ANSWER",
                "download_url": None,
                "provenance": {
                    "entity": "P-201",
                    "knowledge_source": "MRPL Local Knowledge Base",
                    "retrieval_mode": "Hybrid RAG",
                    "retrieved_documents": ["MRPL-INSP-2024-P201.pdf", "MRPL-INSP-2019-P201.pdf"],
                    "calculation_origin": "DIRECT_MRPL_RECORD",
                    "verification_status": "MRPL_VERIFIED"
                },
                "summary": "Verified current wall thickness: 4.50 mm against t_min 3.50 mm (ASME B31.3)."
            },
            {
                "id": "act-seed-002",
                "timestamp": now - 10800,
                "formatted_time": datetime.fromtimestamp(now - 10800).strftime("%d %b %Y %H:%M"),
                "time_ago": "3 hours ago",
                "query": "Prepare an approval note for P-201 continuous operation",
                "operation_type": "APPROVAL_NOTE",
                "file_badge": "DOCX",
                "badge_class": "docx",
                "file_name": "Approval_Note_P201.docx",
                "entity_tag": "P-201",
                "routed_model": "qwen2.5-coder:3b",
                "executed_model": "qwen2.5-coder:3b",
                "execution_status": "SUCCESS",
                "output_type": "APPROVAL_NOTE_DOCX",
                "download_url": "/artifacts/Approval_Note_P201_v1.docx",
                "provenance": {
                    "entity": "P-201",
                    "knowledge_source": "MRPL Local Knowledge Base & SymPy Engine",
                    "retrieval_mode": "Hybrid RAG + API 570",
                    "retrieved_documents": ["MRPL-INSP-2024-P201.pdf"],
                    "calculation_origin": "CALCULATED_FROM_MRPL_EVIDENCE",
                    "verification_status": "VERIFIED"
                },
                "summary": "Generated 19-section Continued Operation Approval Note with SHA-256."
            },
            {
                "id": "act-seed-003",
                "timestamp": now - 86400,
                "formatted_time": datetime.fromtimestamp(now - 86400).strftime("%d %b %Y %H:%M"),
                "time_ago": "1 day ago",
                "query": "Calculate the corrosion rate of P-201 from inspection measurements",
                "operation_type": "CALCULATION",
                "file_badge": "XLS",
                "badge_class": "xlsx",
                "file_name": "Corrosion_Data.xlsx",
                "entity_tag": "P-201",
                "routed_model": "qwen2.5-coder:3b",
                "executed_model": "qwen2.5-coder:3b",
                "execution_status": "MRPL_VERIFIED",
                "output_type": "CALCULATION_SHEET",
                "download_url": "/artifacts/P201_Corrosion_Calculation.xlsx",
                "provenance": {
                    "entity": "P-201",
                    "knowledge_source": "MRPL Formula Library (CR-001)",
                    "retrieval_mode": "Deterministic Python Float64",
                    "retrieved_documents": ["MRPL-INSP-2024-P201.pdf", "MRPL-INSP-2019-P201.pdf"],
                    "calculation_origin": "CALCULATED_FROM_MRPL_EVIDENCE",
                    "verification_status": "MATCH (100% Deterministic Python)"
                },
                "summary": "Corrosion Rate = 0.30 mm/year • Remaining Operating Life = 3.33 Years."
            },
            {
                "id": "act-seed-004",
                "timestamp": now - 90000,
                "formatted_time": datetime.fromtimestamp(now - 90000).strftime("%d %b %Y %H:%M"),
                "time_ago": "1 day ago",
                "query": "Analyze P&ID topology for Crude Booster Pump P-101 and safety isolation loops",
                "operation_type": "PID_ANALYSIS",
                "file_badge": "IMG",
                "badge_class": "img",
                "file_name": "P&ID_Unit3.png",
                "entity_tag": "P-101",
                "routed_model": "qwen2.5vl:3b",
                "executed_model": "qwen2.5-coder:3b",
                "execution_status": "SUCCESS",
                "output_type": "GRAPH_QUERY",
                "download_url": None,
                "provenance": {
                    "entity": "P-101",
                    "knowledge_source": "CDU-P-101 Topological Graph",
                    "retrieval_mode": "Graph Topology Traversal",
                    "retrieved_documents": ["CDU-P-101 (21 nodes, 23 edges)"],
                    "calculation_origin": "GRAPH_TRAVERSAL",
                    "verification_status": "HIGH_CONFIDENCE"
                },
                "summary": "Identified 6 connected equipment nodes, suction valve HV-101, and PT-102 transmitter."
            },
            {
                "id": "act-seed-005",
                "timestamp": now - 172800,
                "formatted_time": datetime.fromtimestamp(now - 172800).strftime("%d %b %Y %H:%M"),
                "time_ago": "2 days ago",
                "query": "Summarize vendor correspondence and metallurgy recommendations for P-201",
                "operation_type": "DIRECT_QUERY",
                "file_badge": "PDF",
                "badge_class": "pdf",
                "file_name": "Vendor_Correspondence.pdf",
                "entity_tag": "P-201",
                "routed_model": "qwen2.5-coder:3b",
                "executed_model": "qwen2.5-coder:3b",
                "execution_status": "MRPL_VERIFIED",
                "output_type": "CHAT_ANSWER",
                "download_url": None,
                "provenance": {
                    "entity": "P-201",
                    "knowledge_source": "MRPL Local Knowledge Base",
                    "retrieval_mode": "Hybrid RAG",
                    "retrieved_documents": ["MRPL-DOC-2024-001"],
                    "calculation_origin": "DIRECT_MRPL_RECORD",
                    "verification_status": "MRPL_VERIFIED"
                },
                "summary": "Confirmed A216 WCB carbon steel casing specification and 18-month inspection cycle."
            }
        ]

    def record_activity(
        self,
        query: str,
        operation_type: str,
        entity_tag: Optional[str] = None,
        routed_model: Optional[str] = None,
        executed_model: Optional[str] = None,
        execution_status: str = "SUCCESS",
        output_type: str = "CHAT_ANSWER",
        file_name: Optional[str] = None,
        file_badge: Optional[str] = None,
        download_url: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
        full_result: Optional[Dict[str, Any]] = None,
        summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Records a completed operation in the persistent activity history.
        """
        now = time.time()
        item_id = f"act-{uuid.uuid4().hex[:8]}"

        # Infer appropriate file badge and badge class
        badge = file_badge
        if not badge:
            op_upper = (operation_type or "").upper()
            out_upper = (output_type or "").upper()
            if "DOCX" in out_upper or "APPROVAL" in op_upper:
                badge = "DOCX"
            elif "XLS" in out_upper or "SPREADSHEET" in op_upper:
                badge = "XLS"
            elif "PPT" in out_upper or "SLIDE" in op_upper:
                badge = "PPT"
            elif "PID" in op_upper or "IMAGE" in op_upper:
                badge = "IMG"
            elif "CALC" in op_upper:
                badge = "CALC"
            elif "CODE" in op_upper or "CODING" in op_upper or "SANDBOX" in out_upper or "SANDBOX" in op_upper:
                badge = "CODE"
            elif "PDF" in (file_name or "").upper():
                badge = "PDF"
            elif full_result and full_result.get("retrieved_evidence") and len(full_result.get("retrieved_evidence", [])) > 0:
                badge = "RAG"
            else:
                badge = "AI"

        badge_class_map = {
            "PDF": "pdf",
            "DOCX": "docx",
            "XLS": "xlsx",
            "XLSX": "xlsx",
            "PPT": "purple",
            "IMG": "img",
            "CALC": "calc",
            "CODE": "cyan",
            "SANDBOX": "cyan",
            "RAG": "cyan",
            "AI": "pdf",
        }
        badge_class = badge_class_map.get(badge, "pdf")

        # Display file name
        disp_name = file_name
        if not disp_name:
            if entity_tag and entity_tag != "General":
                disp_name = f"{entity_tag}_{operation_type.title().replace('_', '')}"
            else:
                disp_name = (query[:35] + "...") if len(query) > 35 else query

        item = {
            "id": item_id,
            "timestamp": now,
            "formatted_time": datetime.fromtimestamp(now).strftime("%d %b %Y %H:%M"),
            "time_ago": "Just now",
            "query": query,
            "operation_type": operation_type,
            "file_badge": badge,
            "badge_class": badge_class,
            "file_name": disp_name,
            "entity_tag": entity_tag or "General",
            "routed_model": routed_model or "qwen2.5-coder:3b",
            "executed_model": executed_model or "qwen2.5-coder:3b",
            "execution_status": execution_status,
            "output_type": output_type,
            "download_url": download_url,
            "provenance": provenance or {},
            "full_result": full_result or {},
            "summary": summary or (query[:120] if query else ""),
        }

        with self._lock:
            # Prepend to list
            self._items.insert(0, item)
            if len(self._items) > self.max_items:
                self._items = self._items[:self.max_items]
            self._save_to_disk_unlocked()

        return item

    def get_recent(
        self,
        limit: int = 5,
        query: Optional[str] = None,
        op_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with self._lock:
            results = []
            q_lower = query.lower().strip() if query else None
            t_lower = op_type.lower().strip() if op_type and op_type != "all" else None

            for item in self._items:
                # Refresh relative time
                item_copy = dict(item)
                item_copy["time_ago"] = self._format_time_ago(item.get("timestamp", time.time()))

                # Filter by search term
                if q_lower:
                    item_text = f"{item.get('query', '')} {item.get('file_name', '')} {item.get('entity_tag', '')} {item.get('summary', '')}".lower()
                    if q_lower not in item_text:
                        continue

                # Filter by operation / file type
                if t_lower:
                    b_type = str(item.get("file_badge", "")).lower()
                    o_type = str(item.get("operation_type", "")).lower()
                    if t_lower not in b_type and t_lower not in o_type:
                        continue

                results.append(item_copy)
                if limit and len(results) >= limit:
                    break

            return results

    def get_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for item in self._items:
                if item.get("id") == item_id:
                    item_copy = dict(item)
                    item_copy["time_ago"] = self._format_time_ago(item.get("timestamp", time.time()))
                    return item_copy
            return None

    def clear_history(self) -> bool:
        with self._lock:
            self._items = []
            self._save_to_disk_unlocked()
        return True


# Global Singleton
activity_store = ActivityHistoryStore()
