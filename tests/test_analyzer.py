import pytest
from backend.services.task_analyzer import TaskAnalyzer
from backend.models.task_profile import TaskType, RiskLevel, InputModality


def test_task_analyzer_general_reasoning():
    analyzer = TaskAnalyzer()
    query = "Explain why preventive maintenance is important in a refinery."
    profile = analyzer.analyze(query)

    assert profile.task_type == TaskType.GENERAL_REASONING
    assert profile.modality == InputModality.TEXT
    assert profile.risk == RiskLevel.LOW
    assert profile.required_capabilities.reasoning >= 0.80
    assert profile.required_capabilities.general >= 0.80
    assert profile.requires_verification is False


def test_task_analyzer_coding_query():
    analyzer = TaskAnalyzer()
    query = "Write Python code to calculate corrosion rate."
    profile = analyzer.analyze(query)

    assert profile.task_type in [TaskType.CODING, TaskType.ENGINEERING_CALCULATION]
    assert profile.required_capabilities.coding >= 0.80
    assert profile.required_capabilities.mathematics >= 0.60
    assert profile.risk == RiskLevel.MEDIUM


def test_task_analyzer_math_calculation():
    analyzer = TaskAnalyzer()
    query = "Calculate the percentage reduction from 5.0 mm to 3.8 mm."
    profile = analyzer.analyze(query)

    assert profile.task_type == TaskType.ENGINEERING_CALCULATION
    assert profile.required_capabilities.mathematics >= 0.85
    assert profile.risk == RiskLevel.MEDIUM


def test_task_analyzer_pid_inspection():
    analyzer = TaskAnalyzer()
    query = "Analyze this P&ID and identify equipment connected to P-101."
    files = [{"name": "pid_crude_distillation.png", "size": 150000}]

    profile = analyzer.analyze(query, files)

    assert profile.task_type == TaskType.MULTIMODAL_DOCUMENT_ANALYSIS
    assert profile.modality == InputModality.VISION
    assert profile.required_capabilities.vision >= 0.90
    assert profile.required_capabilities.ocr >= 0.85
    assert profile.required_capabilities.document_understanding >= 0.85


def test_task_analyzer_multimodal_multi_files():
    analyzer = TaskAnalyzer()
    query = "Analyze this scanned inspection report and explain the damaged equipment."
    files = [
        {"name": "damage_photo.jpg", "size": 250000},
        {"name": "inspection_notes.pdf", "size": 120000},
    ]
    profile = analyzer.analyze(query, files)

    assert profile.modality == InputModality.MULTIMODAL
    assert profile.required_capabilities.vision >= 0.90
    assert profile.required_capabilities.document_understanding >= 0.90


def test_task_analyzer_corrosion_calculation():
    analyzer = TaskAnalyzer()
    query = "Calculate the corrosion rate and remaining life from ultrasonic survey."
    files = [{"name": "corrosion_survey.csv", "size": 2048}]

    profile = analyzer.analyze(query, files)

    assert profile.task_type == TaskType.ENGINEERING_CALCULATION
    assert profile.modality == InputModality.SPREADSHEET
    assert profile.required_capabilities.mathematics >= 0.85
    assert profile.required_capabilities.coding >= 0.80
    assert profile.risk == RiskLevel.MEDIUM


def test_task_analyzer_equipment_approval_high_risk():
    analyzer = TaskAnalyzer()
    query = "Should P-101 be approved for continued operation despite high vibration?"

    profile = analyzer.analyze(query)

    assert profile.task_type == TaskType.EQUIPMENT_APPROVAL
    assert profile.risk == RiskLevel.HIGH
    assert profile.requires_verification is True
    assert profile.required_capabilities.reasoning >= 0.90


def test_task_analyzer_never_selects_model():
    """
    Task Analyzer MUST only classify task requirements and MUST NOT select or propose model names.
    """
    analyzer = TaskAnalyzer()
    profile = analyzer.analyze("Write Python code for crude distillation simulation.")
    profile_dict = profile.model_dump()

    assert "selected_model" not in profile_dict
    assert "primary_model" not in profile_dict
    assert "model" not in profile_dict


def test_task_analyzer_risk_override():
    analyzer = TaskAnalyzer()
    query = "Summarize this memo on shift handover."

    # Default low risk
    profile_default = analyzer.analyze(query)
    assert profile_default.risk == RiskLevel.LOW
    assert profile_default.requires_verification is False

    # Overridden to high risk
    profile_overridden = analyzer.analyze(query, risk_override="high")
    assert profile_overridden.risk == RiskLevel.HIGH
    assert profile_overridden.requires_verification is True
