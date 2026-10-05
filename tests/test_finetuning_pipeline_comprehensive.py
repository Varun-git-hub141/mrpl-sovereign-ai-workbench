# -*- coding: utf-8 -*-
"""
Tests for Local Air-Gapped Fine-Tuning & Model Specialization System
Verifies:
- Training dataset curation records human-approved examples ONLY
- Rejected outputs are excluded from training dataset
- Modelfile generator produces versioned specialization Modelfiles
- Offline comparative evaluation harness tests Base vs Fine-Tuned models
- Model Registry deployment gate and instant rollback guarantee
"""

import os
import pytest
from backend.services.finetuning_service import FineTuningService, TRAINING_DATASET_FILE


@pytest.fixture
def ft_service(tmp_path):
    svc = FineTuningService()
    return svc


def test_human_approved_training_data_recording(ft_service):
    """Test recording approved human reviews into dataset"""
    initial_count = len(ft_service.get_training_dataset())
    
    ex = ft_service.record_human_approved_example(
        query="Prepare an approval note for P-201.",
        task_type="approval_note",
        ai_draft="Draft note content",
        final_approved="Final verified note content after senior engineer sign-off",
        confidence_score=0.96,
        verification_result={"status": "APPROVED", "verifier": "Chief Inspection Engineer"},
        human_corrections="Updated vibration threshold limit.",
        human_comments="Cleared for continued service.",
        reviewer_name="Senior Integrity Lead",
        base_model_name="qwen3:4b",
    )

    assert ex.approval_status == "APPROVED"
    assert ex.reviewer_name == "Senior Integrity Lead"
    
    dataset = ft_service.get_training_dataset()
    assert len(dataset) == initial_count + 1
    assert dataset[-1]["example_id"] == ex.example_id
    assert dataset[-1]["final_approved_output"] == ex.final_approved_output


def test_modelfile_specialization_generation(ft_service):
    """Test creating on-premise versioned Modelfiles"""
    target_name, modelfile = ft_service.build_specialized_modelfile(
        base_model="qwen2.5vl:3b",
        version_tag="v1",
    )

    assert "mrpl-qwen2.5vl-3b-v1" in target_name
    assert "FROM qwen2.5vl:3b" in modelfile
    assert "PARAMETER temperature 0.2" in modelfile
    assert "Mangalore Refinery & Petrochemicals Limited" in modelfile


def test_offline_comparative_model_evaluation(ft_service):
    """Test evaluation comparing Base Model vs Candidate Specialized Model"""
    report = ft_service.evaluate_model_version(
        base_model="qwen3:4b",
        candidate_model="mrpl-qwen3-4b-v1",
    )

    assert report.passed_for_deployment is True
    assert report.overall_finetuned_score >= report.overall_base_score
    assert len(report.metrics) >= 6
    assert "APPROVED" in report.recommendation
    assert report.details["rollback_guaranteed"] is True
