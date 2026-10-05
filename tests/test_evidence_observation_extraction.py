# tests/test_evidence_observation_extraction.py
"""
MRPL Sovereign AI Workbench — Phase 3A Test Suite:
Source-Grounded Observation Extraction & Deterministic Normalization/Validation.

Validates:
A. Valid structured observation
B. Missing observation date (degrades to None, no hallucination)
C. Missing revision (degrades to None)
D. Missing authority (degrades to UNKNOWN)
E. Missing measurement location (degrades to None)
F. Missing measurement method (degrades to None)
G. Exact raw statement preservation verbatim
H. Source span preservation
I. Multiple observations from one document
J. Multiple observations from multiple documents
K. Same entity/property with different values -> BOTH observations preserved
L. Same entity with different CMLs -> BOTH observations preserved
M. Range value in source -> no averaging/invention (verbatim range preservation)
N. Malformed chunk -> no exception (captured in malformed_records)
O. Missing source statement -> explicit validation failure
P. Deterministic observation ID calculation
Q. Reprocessing identical source -> identical observation ID
R. LLM extraction / unsupported input containing invented field -> safe rejection or validation error
S. Unknown authority -> AuthorityTier.UNKNOWN
T. Unknown approval status -> ApprovalStatus.UNKNOWN
"""

import pytest
from backend.services.evidence.reconciliation_models import (
    AuthorityTier,
    ApprovalStatus,
    ExtractionMethod,
    EvidenceObservation,
    MalformedObservationRecord,
    ObservationExtractionResult,
    DerivedObservation,
    DerivationStatus,
)
from backend.services.evidence.observation_extractor import EvidenceObservationExtractor


class TestEvidenceObservationExtraction:
    """Phase 3A comprehensive test suite for observation extraction & fidelity."""

    def test_a_valid_structured_observation(self):
        """A. Valid structured observation extracted with complete fidelity."""
        data = {
            "entity_tag": "P-201",
            "property_name": "wall_thickness",
            "value": 4.5,
            "unit": "mm",
            "measurement_location": "CML-01 Suction Nozzle",
            "measurement_method": "UT Pulse-Echo",
            "observation_date": "2024-06-15",
            "source_document": "MRPL-INSP-2024-P201.pdf",
            "document_id": "DOC-P201-2024",
            "document_type": "Inspection Reports",
            "page_number": 3,
            "section": "Thickness Measurement Survey",
            "revision_number": "Rev 1",
            "authority_tier": "APPROVED_AUTHORITATIVE",
            "approval_status": "APPROVED",
            "raw_statement": "Measured wall thickness at CML-01 Suction Nozzle is 4.5 mm via UT Pulse-Echo.",
        }
        res = EvidenceObservationExtractor.extract_from_dict(data)
        assert res.total_extracted == 1
        assert len(res.observations) == 1
        assert len(res.malformed_records) == 0

        obs = res.observations[0]
        assert obs.entity_tag == "P-201"
        assert obs.property_name == "wall_thickness"
        assert obs.value == 4.5
        assert obs.unit == "mm"
        assert obs.measurement_location == "CML-01 Suction Nozzle"
        assert obs.measurement_method == "UT Pulse-Echo"
        assert obs.observation_date == "2024-06-15"
        assert obs.source_document == "MRPL-INSP-2024-P201.pdf"
        assert obs.document_id == "DOC-P201-2024"
        assert obs.page_number == 3
        assert obs.revision_number == "Rev 1"
        assert obs.authority_tier == AuthorityTier.APPROVED_AUTHORITATIVE
        assert obs.approval_status == ApprovalStatus.APPROVED
        assert obs.raw_statement == "Measured wall thickness at CML-01 Suction Nozzle is 4.5 mm via UT Pulse-Echo."

    def test_b_missing_observation_date(self):
        """B. Missing observation date degrades to None without guessing."""
        data = {
            "entity_tag": "TK-201",
            "property_name": "design_pressure",
            "value": 15.0,
            "unit": "bar",
            "source_document": "TK201_Manual.pdf",
            "raw_statement": "Design pressure: 15.0 bar.",
        }
        res = EvidenceObservationExtractor.extract_from_dict(data)
        assert res.total_extracted == 1
        obs = res.observations[0]
        assert obs.observation_date is None

    def test_c_missing_revision(self):
        """C. Missing revision degrades to None."""
        data = {
            "entity_tag": "PSV-201",
            "property_name": "set_pressure",
            "value": 18.5,
            "unit": "bar",
            "source_document": "PSV_Data.pdf",
            "raw_statement": "Set pressure = 18.5 bar",
        }
        res = EvidenceObservationExtractor.extract_from_dict(data)
        assert res.total_extracted == 1
        obs = res.observations[0]
        assert obs.revision_number is None

    def test_d_missing_authority(self):
        """D. Missing authority tier degrades to UNKNOWN."""
        data = {
            "entity_tag": "E-101",
            "property_name": "operating_temperature",
            "value": 140.0,
            "unit": "°C",
            "source_document": "RandomNotes.txt",
            "raw_statement": "Operating temperature is 140 C.",
        }
        res = EvidenceObservationExtractor.extract_from_dict(data)
        assert res.total_extracted == 1
        obs = res.observations[0]
        assert obs.authority_tier == AuthorityTier.UNKNOWN

    def test_e_missing_measurement_location(self):
        """E. Missing measurement location degrades to None."""
        data = {
            "entity_tag": "P-201",
            "property_name": "wall_thickness",
            "value": 4.1,
            "unit": "mm",
            "source_document": "General_P201_Log.txt",
            "raw_statement": "Wall thickness measured at 4.1 mm.",
        }
        res = EvidenceObservationExtractor.extract_from_dict(data)
        assert res.total_extracted == 1
        obs = res.observations[0]
        assert obs.measurement_location is None

    def test_f_missing_measurement_method(self):
        """F. Missing measurement method degrades to None."""
        data = {
            "entity_tag": "P-201",
            "property_name": "vibration_velocity_rms",
            "value": 6.2,
            "unit": "mm/s",
            "source_document": "P201_Vib_Log.txt",
            "raw_statement": "Vibration velocity is 6.2 mm/s.",
        }
        res = EvidenceObservationExtractor.extract_from_dict(data)
        assert res.total_extracted == 1
        obs = res.observations[0]
        assert obs.measurement_method is None

    def test_g_exact_raw_statement_preservation(self):
        """G. Verbatim raw statement preservation."""
        raw_text = "SURVEY NOTE: At nozzle junction N1, nominal measured thickness is exactly 3.82 mm after grinding."
        data = {
            "entity_tag": "V-201",
            "property_name": "wall_thickness",
            "value": 3.82,
            "unit": "mm",
            "source_document": "V201_Survey.txt",
            "raw_statement": raw_text,
        }
        res = EvidenceObservationExtractor.extract_from_dict(data)
        assert res.total_extracted == 1
        assert res.observations[0].raw_statement == raw_text

    def test_h_source_span_preservation(self):
        """H. Source span preservation in regex/chunk extraction."""
        chunk = {
            "text": "Inspection on P-201 shows wall thickness: 4.8 mm at CML-01.",
            "source": {
                "document": "MRPL-INSP-P201.pdf",
                "page": 2,
                "equipment_tag": "P-201",
            }
        }
        res = EvidenceObservationExtractor.extract_from_chunk(chunk)
        assert res.total_extracted >= 1
        obs = res.observations[0]
        assert obs.source_span is not None
        assert "char:" in obs.source_span

    def test_i_multiple_observations_from_one_document(self):
        """I. Multiple observations from one document extracted distinctly."""
        data = {
            "equipment_tag": "P-201",
            "document_name": "MRPL-INSP-2024-P201.json",
            "inspection_history": [
                {
                    "date": "2024-06-01",
                    "cml": "CML-01 Suction",
                    "wall_thickness": 4.5,
                    "method": "UT",
                    "remarks": "CML-01 measured 4.5 mm",
                },
                {
                    "date": "2024-06-01",
                    "cml": "CML-02 Discharge",
                    "wall_thickness": 4.2,
                    "method": "UT",
                    "remarks": "CML-02 measured 4.2 mm",
                },
            ]
        }
        res = EvidenceObservationExtractor.extract_from_dict(data)
        assert res.total_extracted == 2
        assert len(res.observations) == 2
        locs = [o.measurement_location for o in res.observations]
        assert "CML-01 Suction" in locs
        assert "CML-02 Discharge" in locs

    def test_j_multiple_observations_from_multiple_documents(self):
        """J. Multiple observations from multiple documents in batch extraction."""
        doc1 = {
            "entity_tag": "P-201",
            "property_name": "wall_thickness",
            "value": 5.0,
            "observation_date": "2020-01-10",
            "source_document": "MRPL-DS-2020-P201.pdf",
            "raw_statement": "Nominal design thickness: 5.0 mm",
        }
        doc2 = {
            "entity_tag": "P-201",
            "property_name": "wall_thickness",
            "value": 4.2,
            "observation_date": "2024-06-15",
            "source_document": "MRPL-INSP-2024-P201.pdf",
            "raw_statement": "Measured thickness: 4.2 mm",
        }
        res = EvidenceObservationExtractor.extract_from_sources([doc1, doc2])
        assert res.total_extracted == 2
        docs = [o.source_document for o in res.observations]
        assert "MRPL-DS-2020-P201.pdf" in docs
        assert "MRPL-INSP-2024-P201.pdf" in docs

    def test_k_same_entity_property_different_values_both_preserved(self):
        """K. Same entity/property with different values -> BOTH observations preserved (zero deletion)."""
        doc1 = {
            "entity_tag": "P-201",
            "property_name": "wall_thickness",
            "value": 4.5,
            "measurement_location": "CML-01",
            "source_document": "SurveyA.pdf",
            "raw_statement": "Survey A: 4.5 mm",
        }
        doc2 = {
            "entity_tag": "P-201",
            "property_name": "wall_thickness",
            "value": 3.9,
            "measurement_location": "CML-01",
            "source_document": "SurveyB.pdf",
            "raw_statement": "Survey B: 3.9 mm",
        }
        res = EvidenceObservationExtractor.extract_from_sources([doc1, doc2])
        assert res.total_extracted == 2
        values = [o.value for o in res.observations]
        assert 4.5 in values
        assert 3.9 in values
        assert len(res.observations) == 2

    def test_l_same_entity_with_different_cmls_both_preserved(self):
        """L. Same entity with different CMLs -> BOTH observations preserved."""
        cml1 = {
            "entity_tag": "P-201",
            "property_name": "wall_thickness",
            "value": 4.6,
            "measurement_location": "CML-01",
            "source_document": "Survey.pdf",
            "raw_statement": "CML-01: 4.6 mm",
        }
        cml2 = {
            "entity_tag": "P-201",
            "property_name": "wall_thickness",
            "value": 3.8,
            "measurement_location": "CML-02",
            "source_document": "Survey.pdf",
            "raw_statement": "CML-02: 3.8 mm",
        }
        res = EvidenceObservationExtractor.extract_from_sources([cml1, cml2])
        assert res.total_extracted == 2
        locations = {o.measurement_location: o.value for o in res.observations}
        assert locations["CML-01"] == 4.6
        assert locations["CML-02"] == 3.8

    def test_m_range_value_in_source_no_averaging(self):
        """M. Range value in source -> no averaging/invention, preserves range string."""
        chunk = {
            "text": "P-201 inspection notes: wall thickness: 4.4 - 4.6 mm observed across elbow.",
            "source": {"document": "P201_Notes.txt", "equipment_tag": "P-201"},
        }
        res = EvidenceObservationExtractor.extract_from_chunk(chunk)
        assert res.total_extracted >= 1
        obs = res.observations[0]
        # Must preserve range as string, NOT average to 4.5!
        assert obs.value == "4.4 - 4.6"
        assert obs.value != 4.5

    def test_n_malformed_chunk_no_exception(self):
        """N. Malformed chunk does not crash extraction, records in malformed_records."""
        res1 = EvidenceObservationExtractor.extract_from_chunk(None)
        assert res1.total_extracted == 0
        assert len(res1.malformed_records) == 1
        assert "None" in res1.malformed_records[0].error_reason

        res2 = EvidenceObservationExtractor.extract_from_dict("not a dict")
        assert res2.total_extracted == 0
        assert len(res2.malformed_records) == 1

    def test_o_missing_source_statement_explicit_validation_failure(self):
        """O. Missing source statement causes explicit validation failure."""
        invalid_data = {
            "entity_tag": "P-201",
            "property_name": "wall_thickness",
            "value": 4.5,
            "source_document": "Doc.pdf",
            "raw_statement": "",  # Empty verbatim statement
        }
        res = EvidenceObservationExtractor.extract_from_dict(invalid_data)
        assert res.total_extracted == 0
        assert len(res.malformed_records) == 1
        assert "raw_statement" in res.malformed_records[0].error_reason

    def test_p_deterministic_observation_id(self):
        """P. Deterministic observation ID generation produces expected format."""
        obs_id = EvidenceObservationExtractor.generate_observation_id(
            document_id="DOC-123",
            source_document="MRPL-INSP-2024.pdf",
            page_number=2,
            entity_tag="P-201",
            property_name="wall_thickness",
            measurement_location="CML-01",
            raw_statement="wall thickness at CML-01: 4.5 mm",
        )
        assert obs_id.startswith("OBS-P201-WALLTHIC-")
        assert len(obs_id.split("-")) >= 4

    def test_q_reprocessing_identical_source_same_observation_id(self):
        """Q. Reprocessing identical source yields exactly identical observation ID."""
        data = {
            "entity_tag": "P-201",
            "property_name": "wall_thickness",
            "value": 4.5,
            "unit": "mm",
            "measurement_location": "CML-01",
            "source_document": "MRPL-INSP-2024-P201.pdf",
            "document_id": "DOC-P201-2024",
            "page_number": 3,
            "raw_statement": "Measured wall thickness at CML-01 is 4.5 mm",
        }
        res1 = EvidenceObservationExtractor.extract_from_dict(data)
        res2 = EvidenceObservationExtractor.extract_from_dict(data)
        assert res1.observations[0].observation_id == res2.observations[0].observation_id

    def test_r_llm_or_unsupported_input_missing_entity_rejected(self):
        """R. Unsupported / invalid input without valid entity tag is safely rejected."""
        unsupported = {
            "entity_tag": "",
            "property_name": "wall_thickness",
            "value": 4.5,
            "raw_statement": "wall thickness 4.5 mm",
        }
        res = EvidenceObservationExtractor.extract_from_dict(unsupported)
        assert res.total_extracted == 0
        assert len(res.malformed_records) == 1
        assert "entity_tag" in res.malformed_records[0].error_reason

    def test_s_unknown_authority(self):
        """S. Unknown authority mapping maps to AuthorityTier.UNKNOWN."""
        assert EvidenceObservationExtractor.map_authority_tier("NON_EXISTENT_TIER") == AuthorityTier.UNKNOWN
        assert EvidenceObservationExtractor.map_authority_tier(None) == AuthorityTier.UNKNOWN

    def test_t_unknown_approval_status(self):
        """T. Unknown approval status maps to ApprovalStatus.UNKNOWN."""
        assert EvidenceObservationExtractor.map_approval_status("INVALID_STATUS") == ApprovalStatus.UNKNOWN
        assert EvidenceObservationExtractor.map_approval_status(None) == ApprovalStatus.UNKNOWN

    def test_derived_observation_model_instantiation(self):
        """Validates Phase 3 DerivedObservation data model support without calculations."""
        deriv = DerivedObservation(
            derived_id="DERIV-CR-P201-001",
            property_name="corrosion_rate",
            derived_value=0.25,
            unit="mm/year",
            derivation_status=DerivationStatus.CALCULATED,
            source_observation_ids=["OBS-P201-001", "OBS-P201-002"],
            derivation_method="API 570 Short-Term Corrosion Rate Formula",
            input_parameters={"t_initial": 5.0, "t_actual": 4.5, "delta_t_years": 2.0},
            time_interval_years=2.0,
            source_verified_assumptions=["Monotonic linear metal loss verified by NDT history"],
        )
        assert deriv.derived_id == "DERIV-CR-P201-001"
        assert deriv.derived_value == 0.25
        assert len(deriv.source_observation_ids) == 2
        assert deriv.derivation_status == DerivationStatus.CALCULATED
