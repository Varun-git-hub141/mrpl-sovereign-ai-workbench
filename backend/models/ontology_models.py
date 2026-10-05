from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DisciplineCategory(BaseModel):
    code: str = Field(..., description="Letter code (A-AL)")
    name: str = Field(..., description="Full discipline name")
    description: str = Field(..., description="Scope of engineering discipline")
    key_topics: List[str] = Field(default_factory=list)
    applicable_standards: List[str] = Field(default_factory=list)


class EquipmentKnowledgeProfile(BaseModel):
    equipment_type: str = Field(..., description="Canonical equipment type key")
    display_name: str = Field(..., description="Formatted display name")
    purpose: str = Field(..., description="Refinery operational purpose")
    function: str = Field(..., description="Detailed engineering function")
    major_components: List[str] = Field(default_factory=list)
    common_failure_modes: List[str] = Field(default_factory=list)
    inspection_methods: List[str] = Field(default_factory=list)
    ndt_methods: List[str] = Field(default_factory=list)
    typical_measurements: List[str] = Field(default_factory=list)
    operating_parameters: Dict[str, str] = Field(default_factory=dict)
    design_parameters: Dict[str, str] = Field(default_factory=dict)
    integrity_parameters: Dict[str, str] = Field(default_factory=dict)
    applicable_calculations: List[str] = Field(default_factory=list)
    applicable_standards: List[str] = Field(default_factory=list)
    common_alarms: List[str] = Field(default_factory=list)
    common_risks: List[str] = Field(default_factory=list)
    isolation_requirements: List[str] = Field(default_factory=list)
    maintenance_actions: List[str] = Field(default_factory=list)
    failure_consequences: List[str] = Field(default_factory=list)
    pid_symbols: List[str] = Field(default_factory=list)
    pid_relationships: List[str] = Field(default_factory=list)


# ── Full 38 Discipline Ontology Registry (A-AL) ──
DISCIPLINE_ONTOLOGY: List[DisciplineCategory] = [
    DisciplineCategory(code="A", name="Refinery Process Engineering", description="Crude fractionation, distillation curves, tower hydraulic loading, reflux ratio, cut points.", key_topics=["Crude Distillation", "Vacuum Unit", "FCC", "Hydrocracker", "Reformer", "LPG Recovery"], applicable_standards=["OISD-STD-118", "API RP 521"]),
    DisciplineCategory(code="B", name="Mechanical Engineering", description="Static & rotating machinery design, stress limits, thermal expansion, shaft alignment.", key_topics=["Vibration analysis", "Bearing lube", "Coupling balance", "Thermal growth"], applicable_standards=["API 610", "ISO 10816", "ASME Sec VIII"]),
    DisciplineCategory(code="C", name="Static Equipment", description="Pressure vessels, columns, drums, bullet tanks, reactors, skirt supports.", key_topics=["MAWP", "Nozzle reinforcement", "Hydrotest", "Post-weld heat treatment"], applicable_standards=["ASME Sec VIII Div 1 & 2", "API 510", "IS 2825"]),
    DisciplineCategory(code="D", name="Rotating Equipment", description="Centrifugal pumps, reciprocating compressors, steam turbines, gearboxes, mechanical seals.", key_topics=["NPSHa/NPSHr", "Specific speed", "Vibration severity", "Seal flush plan 53A"], applicable_standards=["API 610", "API 617", "API 682", "ISO 10816-3"]),
    DisciplineCategory(code="E", name="Piping", description="Process piping, line classes, ASME B31.3 wall thickness calculations, pipe stress, thermal loops.", key_topics=["Piping Schedule", "Wall loss rate", "Corrosion allowance", "Flange ratings"], applicable_standards=["ASME B31.3", "API 570", "OISD-STD-141"]),
    DisciplineCategory(code="F", name="Pipeline", description="Cross-country crude/product transfer lines, pigging, cathodic protection, ASME B31.4/B31.8.", key_topics=["Intelligent pigging", "CP survey", "Yield strength ratio", "Surge analysis"], applicable_standards=["ASME B31.4", "ASME B31.8", "OISD-STD-140"]),
    DisciplineCategory(code="G", name="Pressure Vessels", description="Design calculation, minimum retirement wall thickness, corrosion allowance, joint efficiency.", key_topics=["Formed heads", "Cylindrical shell stress", "Lethal service", "Impact test"], applicable_standards=["ASME Sec VIII Div 1", "API 510", "TEMA"]),
    DisciplineCategory(code="H", name="Heat Exchangers", description="Shell & tube, plate type, air coolers, LMTD calculation, tube fouling factor, bundle pull.", key_topics=["Tube vibration", "Baffle spacing", "TEMA classes R/B/C", "Energy balance"], applicable_standards=["TEMA Standard", "API 660", "API 661"]),
    DisciplineCategory(code="I", name="Pumps", description="Crude booster pumps, boiler feed pumps, slurry pumps, seal systems, cavitation prevention.", key_topics=["Head-capacity curve", "Shutoff head", "Min continuous flow", "Suction specific speed"], applicable_standards=["API 610 12th Ed", "ISO 13709", "HI Standards"]),
    DisciplineCategory(code="J", name="Compressors", description="Wet gas compressors, recycle gas centrifugal & screw compressors, surge control, interstage cooling.", key_topics=["Polytropic efficiency", "Anti-surge valves", "Dry gas seals", "Labyrinth seals"], applicable_standards=["API 617", "API 618", "API 619"]),
    DisciplineCategory(code="K", name="Tanks", description="Atmospheric crude storage, floating roof tanks, cone roof tanks, API 650 bottom plate inspection.", key_topics=["Settlement survey", "Rim seal gap", "Venting API 2000", "High-high level trip"], applicable_standards=["API 650", "API 653", "OISD-STD-117"]),
    DisciplineCategory(code="L", name="Valves", description="Gate, globe, check, ball, plug, butterfly, double block & bleed, fugitive emission packing.", key_topics=["API 598 seat leakage", "Fire-safe API 607", "Stellited trim", "Torque seating"], applicable_standards=["API 598", "API 600", "API 602", "API 609"]),
    DisciplineCategory(code="M", name="Safety Relief Devices", description="Pressure safety valves (PSVs), rupture discs, flare relief sizing, set pressure tolerances.", key_topics=["Relief capacity API 520", "Orifice designation D-T", "Backpressure correction", "Chatter"], applicable_standards=["API RP 520 Pt I & II", "API RP 526", "API RP 521", "ASME Sec I & VIII"]),
    DisciplineCategory(code="N", name="Corrosion", description="Naphthenic acid corrosion, high-temp sulfidic corrosion, wet H2S cracking, MIC, ammonium chloride salts.", key_topics=["Corrosion loops", "Material degradation", "Amines SCC", "Polythionic acid cracking"], applicable_standards=["NACE SP0169", "NACE MR0175", "API 571"]),
    DisciplineCategory(code="O", name="Inspection", description="In-service baseline, shutdown turnaround inspections, external visual, condition monitoring.", key_topics=["Circuit identification", "CML location", "Deadlegs", "CUI inspection"], applicable_standards=["API 570", "API 510", "API 653", "OISD-STD-129"]),
    DisciplineCategory(code="P", name="RBI (Risk-Based Inspection)", description="PoF and CoF evaluation, inspection prioritization, degradation modeling per API 580/581.", key_topics=["Probability of failure", "Consequence area", "Risk matrix", "Target interval"], applicable_standards=["API RP 580", "API RP 581"]),
    DisciplineCategory(code="Q", name="NDT (Non-Destructive Testing)", description="Ultrasonic thickness (UT), radiography (RT), magnetic particle (MPI), dye penetrant (DPT), eddy current.", key_topics=["UT Pulse-echo", "Phased array PAUT", "TOFD", "Hardness testing"], applicable_standards=["ASME Sec V", "ASTM E797", "ASNT SNT-TC-1A"]),
    DisciplineCategory(code="R", name="Thickness Monitoring", description="Condition Monitoring Locations (CMLs), ultrasonic grid scans, trend wall thinning analysis.", key_topics=["Point-to-point comparison", "Nominal vs measured", "Grid scan min reading", "Retirement limit"], applicable_standards=["API 570 Section 5.6", "API 574"]),
    DisciplineCategory(code="S", name="Integrity Management", description="Fitness-For-Service (FFS), remaining life assessment, de-rating, operating envelope enforcement.", key_topics=["Level 1/2/3 assessment", "Local metal loss", "Gouge & dent", "Creep-fatigue"], applicable_standards=["API 579-1 / ASME FFS-1", "OISD-STD-141"]),
    DisciplineCategory(code="T", name="Instrumentation", description="Flow transmitters, level radar, pressure gauges, thermocouple/RTD, smart transmitters.", key_topics=["4-20mA HART", "Orifice plate beta ratio", "Magnetic level indicator", "Impulse line"], applicable_standards=["ISA-5.1", "IEC 60751", "API RP 551"]),
    DisciplineCategory(code="U", name="Control Systems", description="DCS, ESD (Emergency Shutdown), PLC interlocks, SIS, SIL ratings, alarm management.", key_topics=["Fail-safe logic", "1oo2 / 2oo3 voting", "Permissive interlocks", "Sequence of events"], applicable_standards=["IEC 61508", "IEC 61511", "ISA-18.2"]),
    DisciplineCategory(code="V", name="Electrical", description="High-voltage switchgear, hazardous area classification (Zone 0/1/2), motor control centers (MCC).", key_topics=["Ex-d flameproof", "Ex-ia intrinsic safety", "Transformer protection", "Substation UPS"], applicable_standards=["IEC 60079", "IS 5571", "NFPA 70"]),
    DisciplineCategory(code="W", name="Process Safety", description="PSM, consequence modeling, toxic gas dispersion, safety instrumented functions, flare load.", key_topics=["Safe operating limits", "Overpressure scenario", "LOPA", "Layer of protection"], applicable_standards=["OSHA 1910.119", "OISD-STD-152", "API RP 754"]),
    DisciplineCategory(code="X", name="HAZOP", description="Hazard & Operability studies, guide words (NO, MORE, LESS, REVERSE), safeguard assessment.", key_topics=["Node definition", "Deviation cause/consequence", "Action item tracking", "Recommendations"], applicable_standards=["IEC 61882", "CCPS Guidelines"]),
    DisciplineCategory(code="Y", name="Maintenance", description="Preventive maintenance (PM), predictive maintenance (PdM), root cause failure analysis (RCFA).", key_topics=["Lube route", "Mechanical seal overhaul", "Dynamic balancing", "Torquing procedure"], applicable_standards=["ISO 55000", "OISD-STD-124"]),
    DisciplineCategory(code="Z", name="Reliability", description="MTBF, MTTR, Bad Actor identification, Weibull analysis, availability modeling.", key_topics=["Availability calculation", "Unscheduled downtime", "FMEA", "Pareto analysis"], applicable_standards=["ISO 14224", "IEEE 493"]),
    DisciplineCategory(code="AA", name="Shutdown / Turnaround", description="Unit TA planning, blind list, vessel entry isolation, de-inventory, purging & gas freeing.", key_topics=["Critical path schedule", "Positive isolation", "LOTO protocol", "Pre-commissioning"], applicable_standards=["OISD-STD-105", "API RP 2217A"]),
    DisciplineCategory(code="AB", name="Operations", description="Standard Operating Procedures (SOP), startup/shutdown sequences, shift handover, emergency protocols.", key_topics=["Pump startup sequence", "Steam tracing", "Off-spec diversion", "Emergency shutdown"], applicable_standards=["OISD-STD-111", "API RP 755"]),
    DisciplineCategory(code="AC", name="P&ID Interpretation", description="ISA symbols, line tagging conventions, control loops, battery limits, utility connections.", key_topics=["P&ID symbology", "Spec breaks", "Valve tag decoding", "Instrument bubbles"], applicable_standards=["ISA-5.1", "ISO 10628", "DIN 28004"]),
    DisciplineCategory(code="AD", name="Engineering Drawings", description="General arrangement (GA), piping isometrics, equipment cross-sections, foundation drawings.", key_topics=["Bill of materials", "Weld mapping", "Orientation plan", "Elevation datum"], applicable_standards=["ASME Y14.5", "ISO 128"]),
    DisciplineCategory(code="AE", name="Inspection Reports", description="UT thickness survey logs, external condition sheets, weld inspection records, NDT reports.", key_topics=["Original vs actual thickness", "Measurement uncertainty", "Equipment summary", "CML table"], applicable_standards=["API 570 Form App D", "API 510 App B"]),
    DisciplineCategory(code="AF", name="Technical Specifications", description="Piping class specs, metallurgy specs, insulation classes, coating specs.", key_topics=["Material grade (ASTM A106 Gr B)", "Corrosion allowance", "PWHT requirement", "Trim code"], applicable_standards=["ASTM Standards", "MRPL Project Specs"]),
    DisciplineCategory(code="AG", name="Datasheets", description="Process and mechanical equipment datasheets, pump curves, design pressure/temperature limits.", key_topics=["Operating flow / head", "Design pressure", "Design temperature", "Material of construction"], applicable_standards=["API 610 Datasheet", "API 660 Datasheet"]),
    DisciplineCategory(code="AH", name="Work Permits", description="Hot work permit, cold work, vessel entry, height work, electrical isolation certs.", key_topics=["Gas test (LEL < 1%)", "Fire watch", "O2 test 20.9%", "Energy isolation certificate"], applicable_standards=["OISD-STD-105", "IS 14489"]),
    DisciplineCategory(code="AI", name="Management of Change (MOC)", description="Technical, process, and administrative change authorization, risk reviews, P&ID redlines.", key_topics=["MOC classification", "Pre-startup safety review PSSR", "Redline updating", "HAZOP trigger"], applicable_standards=["OISD-STD-178", "OSHA 1910.119(l)"]),
    DisciplineCategory(code="AJ", name="Incident & Failure Analysis", description="Metallurgical failure analysis, vibration trip root causes, seal failure analysis.", key_topics=["Beach marks fatigue", "Pitting morphology", "Cavitation damage", "Erosion-corrosion"], applicable_standards=["API 571", "ASTM E8 / E23"]),
    DisciplineCategory(code="AK", name="Environmental & Safety Constraints", description="Flare smoke emissions, VOC leak detection (LDAR), effluent COD/BOD limits, noise abatement.", key_topics=["CPCB/KSPCB norms", "Fugitive emission standard", "Storm water segregation", "Noise < 85 dBA"], applicable_standards=["MoEFCC Norms", "EPA Method 21", "OISD-STD-116"]),
    DisciplineCategory(code="AL", name="Engineering Documentation", description="Technical memos, MOC sign-offs, inspection approval notes, chief engineer review documents.", key_topics=["Structured approval format", "Traceable evidence references", "Calculation appendix", "Sign-off block"], applicable_standards=["ISO 9001", "MRPL Quality Manual"]),
]
