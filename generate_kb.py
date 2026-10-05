"""
Script to create the 57-document MRPL Knowledge Base.
Generates all 57 documents across 9 categories with comprehensive metadata and engineering data.
"""

import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
KB_DIR = BASE_DIR / "MRPL_KNOWLEDGE_BASE"

CATEGORIES = [
    "01_Equipment_Master",
    "02_Equipment_History",
    "03_Inspection_Reports",
    "04_Maintenance_Records",
    "05_PIDs_Drawings",
    "06_SOPs",
    "07_Engineering_Manuals",
    "08_Previous_Engineering_Decisions",
    "09_Technical_Datasheets",
]

for cat in CATEGORIES:
    (KB_DIR / cat).mkdir(parents=True, exist_ok=True)

docs = []

# ==========================================
# 01. Equipment Master (8 documents)
# ==========================================
docs.append({
    "category": "01_Equipment_Master",
    "filename": "EM_P201_Crude_Distillation_Feed_Pump.json",
    "document_id": "MRPL-EM-P201",
    "document_type": "Equipment Master",
    "title": "Equipment Master Record: Crude Distillation Feed Pump P-201",
    "equipment_tag": "P-201",
    "equipment_type": "Centrifugal Pump",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2021-01-15",
    "source_file": "EM_P201_Crude_Distillation_Feed_Pump.json",
    "page_number": 1,
    "section": "1.0 Equipment Identification & Design Specifications",
    "metadata": {
        "manufacturer": "Sulzer Pumps Ltd",
        "model": "API 610 Type OH2 (Single Stage Overhung)",
        "serial_number": "SZ-2019-CDU-9942",
        "service": "Atmospheric Crude Oil Feed",
        "rated_capacity": "320 m3/hr",
        "differential_head": "75 m",
        "design_pressure": "14.5 barg",
        "design_temperature": "165 deg C",
        "moc_casing": "ASTM A216 Grade WCB / CA15 Impeller",
        "nominal_thickness": "6.0 mm",
        "minimum_allowable_thickness": "3.5 mm",
        "corrosion_allowance": "2.5 mm",
        "seal_plan": "API Plan 53B Dual Pressurized Mechanical Seal"
    },
    "content": (
        "MRPL EQUIPMENT MASTER RECORD — P-201\n"
        "Equipment Tag: P-201\n"
        "Description: Primary Crude Distillation Feed Booster Pump for CDU-II.\n"
        "Plant Area: CDU-II / Hydrocarbon Processing Block A.\n"
        "Manufacturer: Sulzer Pumps Ltd | Model: OH2 Centrifugal Pump per API 610 12th Ed.\n"
        "Operating Service: Heavy Desalted Crude Oil (Specific Gravity 0.88, Viscosity 12 cSt @ 40C).\n"
        "Operating Parameters: Rated Flow: 320 m3/hr, Differential Head: 75 m, Suction Pressure: 2.1 barg, Discharge Pressure: 9.8 barg, Design Pressure: 14.5 barg, Design Temperature: 165 C.\n"
        "Materials of Construction (MOC): Casing: ASTM A216 Gr. WCB Carbon Steel; Impeller: 12% Cr ASTM A487 Gr. CA6NM; Shaft: AISI 4140 with 316SS Sleeves.\n"
        "Casing Wall Thickness Specifications:\n"
        "- Original Design Nominal Wall Thickness: 6.0 mm\n"
        "- Minimum Allowable Retirement Thickness (t_min): 3.5 mm (per ASME B31.3 & API 570 Section 7)\n"
        "- Total Available Corrosion Allowance: 2.5 mm\n"
        "Driver: 110 kW Ex-d IIB T3 Induction Motor (3-Phase, 415V, 50 Hz, 2950 RPM).\n"
        "Overpressure Protection: PSV-201 set at 12.0 barg routing discharge to Refinery Flare Header.\n"
        "Critical Interlocks: Low Suction Pressure Trip (< 0.8 barg), High DE/NDE Bearing Temp Trip (> 85 C), High Vibration Trip (> 7.1 mm/s RMS)."
    )
})

docs.append({
    "category": "01_Equipment_Master",
    "filename": "EM_P101_Atmospheric_Residue_Pump.json",
    "document_id": "MRPL-EM-P101",
    "document_type": "Equipment Master",
    "title": "Equipment Master Record: Atmospheric Residue Pump P-101",
    "equipment_tag": "P-101",
    "equipment_type": "Centrifugal Pump",
    "plant_area": "Crude Distillation Unit (CDU-I)",
    "date": "2020-04-10",
    "source_file": "EM_P101_Atmospheric_Residue_Pump.json",
    "page_number": 1,
    "section": "1.0 Equipment Identification & Design Specifications",
    "metadata": {
        "manufacturer": "Flowserve India",
        "model": "API 610 BB2 (Between Bearings Single Stage)",
        "serial_number": "FS-2018-CDU-1102",
        "service": "Atmospheric Bottoms Residue",
        "rated_capacity": "280 m3/hr",
        "differential_head": "68 m",
        "design_pressure": "16.0 barg",
        "nominal_thickness": "5.0 mm",
        "minimum_allowable_thickness": "3.2 mm"
    },
    "content": (
        "MRPL EQUIPMENT MASTER RECORD — P-101\n"
        "Equipment Tag: P-101 (P-101A / P-101B duty/standby)\n"
        "Description: Atmospheric Tower Bottoms Residue Booster Pump.\n"
        "Plant Area: CDU-I / ADU-1 Fractionation Train.\n"
        "Manufacturer: Flowserve India | Model: API 610 Type BB2.\n"
        "Operating Service: Atmospheric Residue @ 320 C.\n"
        "Casing Thickness: Nominal 5.0 mm, Minimum allowable retirement thickness t_min 3.2 mm, Corrosion allowance 1.8 mm.\n"
        "Material of Construction: ASTM A217 Gr. C5 (5Cr-0.5Mo) Alloy Steel Casing.\n"
        "Mechanical Seal: Plan 53A with synthetic barrier fluid."
    )
})

docs.append({
    "category": "01_Equipment_Master",
    "filename": "EM_V201_High_Pressure_Separator.json",
    "document_id": "MRPL-EM-V201",
    "document_type": "Equipment Master",
    "title": "Equipment Master Record: High Pressure Separator Vessel V-201",
    "equipment_tag": "V-201",
    "equipment_type": "Pressure Vessel",
    "plant_area": "CDU-II / Light Ends Recovery",
    "date": "2019-11-20",
    "source_file": "EM_V201_High_Pressure_Separator.json",
    "page_number": 1,
    "section": "1.0 Vessel Mechanical Datasheet & Integrity Limits",
    "metadata": {
        "manufacturer": "L&T Heavy Engineering",
        "design_code": "ASME Sec VIII Div 1",
        "nominal_shell_thickness": "18.0 mm",
        "minimum_allowable_thickness": "12.5 mm",
        "design_pressure": "28.0 barg",
        "design_temp": "120 deg C"
    },
    "content": (
        "MRPL EQUIPMENT MASTER RECORD — V-201\n"
        "Equipment Tag: V-201\n"
        "Description: High Pressure 3-Phase Gas/Oil/Water Separator Vessel.\n"
        "Plant Area: CDU-II Light Ends Unit.\n"
        "Design Code: ASME Section VIII Div 1 Edition 2019.\n"
        "Shell Nominal Thickness: 18.0 mm, Head Nominal Thickness: 16.0 mm. Minimum allowable shell thickness: 12.5 mm.\n"
        "Operating Pressure: 22.0 barg; Design Pressure: 28.0 barg. Design Temperature: 120 C.\n"
        "Relief Valve: PSV-201B set at 28.0 barg discharging to Flare."
    )
})

docs.append({
    "category": "01_Equipment_Master",
    "filename": "EM_TK201_Crude_Feed_Storage_Tank.json",
    "document_id": "MRPL-EM-TK201",
    "document_type": "Equipment Master",
    "title": "Equipment Master Record: Crude Storage Tank TK-201",
    "equipment_tag": "TK-201",
    "equipment_type": "Atmospheric Storage Tank",
    "plant_area": "Tank Farm Area 3",
    "date": "2018-08-14",
    "source_file": "EM_TK201_Crude_Feed_Storage_Tank.json",
    "page_number": 1,
    "section": "1.0 Tank Construction & Shell Courses",
    "metadata": {
        "design_code": "API 650 13th Ed",
        "capacity": "50,000 m3",
        "diameter": "64.0 m",
        "height": "16.5 m",
        "shell_bottom_course_nominal": "24.0 mm",
        "shell_bottom_course_tmin": "16.2 mm"
    },
    "content": (
        "MRPL EQUIPMENT MASTER RECORD — TK-201\n"
        "Equipment Tag: TK-201\n"
        "Description: 50,000 m3 External Floating Roof Crude Storage Tank.\n"
        "Plant Area: Tank Farm Area 3.\n"
        "Design Standard: API 650 13th Edition.\n"
        "Shell Course 1 (Bottom Course) Nominal Thickness: 24.0 mm; Minimum allowable thickness: 16.2 mm.\n"
        "Bottom Annular Plate Nominal: 12.0 mm; Retirement: 6.0 mm.\n"
        "Service: Imported Sour Arab Heavy / Arab Light Crude Blends."
    )
})

docs.append({
    "category": "01_Equipment_Master",
    "filename": "EM_C101_Atmospheric_Distillation_Column.json",
    "document_id": "MRPL-EM-C101",
    "document_type": "Equipment Master",
    "title": "Equipment Master Record: Atmospheric Distillation Column C-101",
    "equipment_tag": "C-101",
    "equipment_type": "Distillation Column",
    "plant_area": "Crude Distillation Unit (CDU-I)",
    "date": "2017-06-12",
    "source_file": "EM_C101_Atmospheric_Distillation_Column.json",
    "page_number": 1,
    "section": "1.0 Column Shell & Internal Tray Specifications",
    "metadata": {
        "height": "52.0 m",
        "diameter": "5.4 m",
        "total_trays": "48 valve trays",
        "shell_thickness_flash_zone": "26.0 mm",
        "shell_thickness_overhead": "16.0 mm"
    },
    "content": (
        "MRPL EQUIPMENT MASTER RECORD — C-101\n"
        "Equipment Tag: C-101\n"
        "Description: Main Atmospheric Crude Fractionation Column.\n"
        "Plant Area: CDU-I Process Train.\n"
        "Design Code: ASME Section VIII Div 1.\n"
        "Flash Zone Shell Thickness: 26.0 mm (Clad with 3.0 mm 410S SS). Overhead Shell Thickness: 16.0 mm (Monel 400 Clad).\n"
        "48 Koch-Glitsch Type BD Valve Trays. Design Temperature: 380 C in Flash Zone."
    )
})

docs.append({
    "category": "01_Equipment_Master",
    "filename": "EM_E101_Crude_Preheat_Exchanger_Train.json",
    "document_id": "MRPL-EM-E101",
    "document_type": "Equipment Master",
    "title": "Equipment Master Record: Crude Preheat Exchanger Train E-101A/B",
    "equipment_tag": "E-101",
    "equipment_type": "Shell and Tube Heat Exchanger",
    "plant_area": "CDU-I Preheat Train",
    "date": "2019-03-25",
    "source_file": "EM_E101_Crude_Preheat_Exchanger_Train.json",
    "page_number": 1,
    "section": "1.0 Exchanger TEMA Configuration",
    "metadata": {
        "tema_type": "AES Shell & Tube",
        "shell_id": "1400 mm",
        "tube_od": "25.4 mm (19.05 mm wall)",
        "tube_moc": "Carbon Steel A179 / Titanium Clad Tube Sheet",
        "design_pressure_shell": "25.0 barg",
        "design_pressure_tube": "35.0 barg"
    },
    "content": (
        "MRPL EQUIPMENT MASTER RECORD — E-101\n"
        "Equipment Tag: E-101 (E-101A through E-101D)\n"
        "Description: Crude Preheat Shell & Tube Heat Exchanger Train.\n"
        "Plant Area: CDU-I Preheat Train.\n"
        "TEMA Type: AES Shell & Tube Exchanger.\n"
        "Shell Side: Residue / Vacuum Gas Oil @ 290 C. Tube Side: Cold Desalted Crude Oil @ 140 C.\n"
        "Shell Nominal Thickness: 16.0 mm; Minimum allowable: 11.0 mm."
    )
})

docs.append({
    "category": "01_Equipment_Master",
    "filename": "EM_PSV201_Pump_Discharge_Relief_Valve.json",
    "document_id": "MRPL-EM-PSV201",
    "document_type": "Equipment Master",
    "title": "Equipment Master Record: Pressure Safety Valve PSV-201",
    "equipment_tag": "PSV-201",
    "equipment_type": "Safety Relief Valve",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2020-02-18",
    "source_file": "EM_PSV201_Pump_Discharge_Relief_Valve.json",
    "page_number": 1,
    "section": "1.0 Safety Valve Sizing & Setpoint Record",
    "metadata": {
        "manufacturer": "Anderson Greenwood / Tyco",
        "model": "Series 81 Pilot Operated Safety Relief Valve",
        "set_pressure": "12.0 barg",
        "orifice_size": "2J3 (Orifice Area 8.30 cm2)",
        "inlet_flange": "2 inch 300# RF",
        "outlet_flange": "3 inch 150# RF",
        "protects_equipment": "P-201 Pump Discharge Casing and Piping"
    },
    "content": (
        "MRPL EQUIPMENT MASTER RECORD — PSV-201\n"
        "Equipment Tag: PSV-201\n"
        "Description: Thermal / Blocked Discharge Safety Relief Valve for P-201.\n"
        "Plant Area: CDU-II Process Area.\n"
        "Set Pressure: 12.0 barg (Overpressure limit: 13.2 barg per API 520).\n"
        "Discharge Destination: Closed Blowdown Header to Refinery Flare.\n"
        "Inspection Interval: Mandatory 24-month calibration and seat bench test."
    )
})

docs.append({
    "category": "01_Equipment_Master",
    "filename": "EM_XV203_Suction_Isolation_Valve.json",
    "document_id": "MRPL-EM-XV203",
    "document_type": "Equipment Master",
    "title": "Equipment Master Record: Automated Suction Emergency Shutdown Valve XV-203",
    "equipment_tag": "XV-203",
    "equipment_type": "Emergency Shutdown Valve (ESDV)",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2020-05-14",
    "source_file": "EM_XV203_Suction_Isolation_Valve.json",
    "page_number": 1,
    "section": "1.0 Actuated Valve Specification & SIL Rating",
    "metadata": {
        "manufacturer": "Rotork / Fisher",
        "size": "12 inch Class 300",
        "action": "Fail Closed (FC)",
        "sil_level": "SIL-2 Certified per IEC 61511",
        "stroke_time": "< 8 seconds"
    },
    "content": (
        "MRPL EQUIPMENT MASTER RECORD — XV-203\n"
        "Equipment Tag: XV-203\n"
        "Description: Automated Suction Isolation Emergency Shutdown Valve for Crude Feed Pump P-201.\n"
        "Plant Area: CDU-II Battery Limits.\n"
        "Valve Size: 12-inch ASME Class 300 Full Bore Metal Seated Ball Valve.\n"
        "Actuator: Pneumatic Spring Return with fail-close action on ESD trigger.\n"
        "Safety Integrity Level: SIL-2 certified for hydrocarbon containment."
    )
})

# ==========================================
# 02. Equipment History (8 documents)
# ==========================================
docs.append({
    "category": "02_Equipment_History",
    "filename": "EH_P201_Operating_And_Integrity_History.json",
    "document_id": "MRPL-EH-P201",
    "document_type": "Equipment History",
    "title": "Equipment Operating & Degradation History: P-201",
    "equipment_tag": "P-201",
    "equipment_type": "Centrifugal Pump",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2024-09-01",
    "source_file": "EH_P201_Operating_And_Integrity_History.json",
    "page_number": 1,
    "section": "2.0 Comprehensive Multi-Year Operating & Overhaul Chronology",
    "metadata": {
        "commissioning_date": "2019-04-10",
        "cumulative_run_hours": "38,450 hrs",
        "total_start_stops": "142 cycles",
        "initial_wall_thickness": "6.0 mm",
        "baseline_inspection_date": "2019-06-01",
        "latest_measured_thickness": "4.5 mm",
        "latest_inspection_date": "2024-06-01",
        "elapsed_inspection_interval": "5.0 years"
    },
    "content": (
        "MRPL EQUIPMENT OPERATING & INTEGRITY HISTORY — P-201\n"
        "Equipment Tag: P-201 | Service: CDU-II Crude Feed Booster Pump.\n"
        "Historical Summary:\n"
        "- 2019-04-10: Commissioned following refinery modernization project. Initial baseline casing thickness verified at 6.0 mm.\n"
        "- 2020-08-14: Routine vibration monitoring showed normal baseline 1.8 mm/s RMS.\n"
        "- 2021-11-05: Minor mechanical seal gland leak reported. Plan 53B bladder recharged and seal flushed during planned window.\n"
        "- 2022-03-12: High-TAN opportunity crude test run increased total acid number from 0.8 to 2.4 mg KOH/g.\n"
        "- 2023-07-19: Impeller wear ring clearance inspected during turn: clearance measured at 0.42 mm (within API 610 limit 0.50 mm).\n"
        "- 2024-06-01: Formal 5-Year NDT Ultrasonic Thickness Survey executed. Casing wall thickness measured at 4.5 mm.\n"
        "Cumulative Thickness Degradation:\n"
        "- Previous/Baseline Wall Thickness = 6.0 mm (Measured 2019)\n"
        "- Current Wall Thickness = 4.5 mm (Measured 2024)\n"
        "- Inspection Interval = 5.0 years\n"
        "- Historical Metal Loss = 1.5 mm\n"
        "- Long-Term Corrosion Rate = 0.30 mm/year\n"
        "- Minimum Allowable Retirement Thickness (t_min) = 3.5 mm\n"
        "- Current Thickness Margin = 4.5 mm - 3.5 mm = +1.0 mm (ABOVE retirement limit)\n"
        "- Estimated Remaining Life = 1.0 mm / 0.30 mm/year = 3.33 years.\n"
        "Conclusion: Equipment P-201 is in acceptable structural condition for continued continuous operation subject to scheduled inspection in 2026."
    )
})

docs.append({
    "category": "02_Equipment_History",
    "filename": "EH_P101_Operating_History.json",
    "document_id": "MRPL-EH-P101",
    "document_type": "Equipment History",
    "title": "Equipment Operating & Degradation History: P-101",
    "equipment_tag": "P-101",
    "equipment_type": "Centrifugal Pump",
    "plant_area": "Crude Distillation Unit (CDU-I)",
    "date": "2024-08-15",
    "source_file": "EH_P101_Operating_History.json",
    "page_number": 1,
    "section": "2.0 Operating Timeline & Vibration History",
    "metadata": {
        "commissioning_date": "2018-02-10",
        "initial_thickness": "5.0 mm",
        "current_thickness": "3.8 mm",
        "t_min": "3.2 mm"
    },
    "content": (
        "MRPL EQUIPMENT HISTORY — P-101\n"
        "Equipment Tag: P-101 (Atmospheric Residue Booster Pump)\n"
        "Operating History: Commissioned 2018. Nominal casing thickness: 5.0 mm. Inspection in 2022 measured 3.8 mm casing thickness (elapsed 4.0 years, corrosion rate 0.30 mm/yr). Current margin above t_min (3.2 mm) is +0.6 mm. In 2024 NDE vibration reached 7.4 mm/s RMS triggering switchover to P-101B."
    )
})

docs.append({
    "category": "02_Equipment_History",
    "filename": "EH_V201_Separator_Integrity_History.json",
    "document_id": "MRPL-EH-V201",
    "document_type": "Equipment History",
    "title": "Equipment Operating & Inspection History: Vessel V-201",
    "equipment_tag": "V-201",
    "equipment_type": "Pressure Vessel",
    "plant_area": "CDU-II Light Ends Unit",
    "date": "2023-10-11",
    "source_file": "EH_V201_Separator_Integrity_History.json",
    "page_number": 1,
    "section": "2.0 Vessel Internal Corrosion History",
    "metadata": {
        "commissioning_date": "2017-09-01",
        "baseline_shell_thickness": "18.0 mm",
        "measured_thickness_2023": "16.4 mm",
        "t_min": "12.5 mm"
    },
    "content": (
        "MRPL EQUIPMENT HISTORY — V-201\n"
        "Vessel V-201 High Pressure Separator operating since 2017.\n"
        "Internal NDT ultrasonic thickness surveys:\n"
        "- 2017: Baseline 18.0 mm\n"
        "- 2020: 17.2 mm\n"
        "- 2023: 16.4 mm (Corrosion rate 0.267 mm/yr). Current margin above t_min (12.5 mm) is 3.9 mm. Demister pad replaced during 2023 turnaround."
    )
})

docs.append({
    "category": "02_Equipment_History",
    "filename": "EH_TK201_Tank_Settlement_History.json",
    "document_id": "MRPL-EH-TK201",
    "document_type": "Equipment History",
    "title": "Equipment Operating & Settlement History: Tank TK-201",
    "equipment_tag": "TK-201",
    "equipment_type": "Atmospheric Storage Tank",
    "plant_area": "Tank Farm Area 3",
    "date": "2024-03-20",
    "source_file": "EH_TK201_Tank_Settlement_History.json",
    "page_number": 1,
    "section": "2.0 Tank Bottom Plate & Edge Settlement Chronology",
    "metadata": {
        "commissioning_date": "2018-11-15",
        "nominal_bottom_plate": "12.0 mm",
        "measured_bottom_plate": "10.2 mm"
    },
    "content": (
        "MRPL EQUIPMENT HISTORY — TK-201\n"
        "Tank TK-201 Crude Oil Storage. Commissioned 2018. Annual geodetic settlement survey confirms uniform edge settlement < 12 mm across all 16 survey benchmark points (well within API 653 allowable limit 45 mm). Annular bottom plate thickness measured 10.2 mm in 2024 (nominal 12.0 mm, retirement 6.0 mm)."
    )
})

docs.append({
    "category": "02_Equipment_History",
    "filename": "EH_C101_Column_Fouling_History.json",
    "document_id": "MRPL-EH-C101",
    "document_type": "Equipment History",
    "title": "Equipment History: Distillation Column C-101",
    "equipment_tag": "C-101",
    "equipment_type": "Distillation Column",
    "plant_area": "CDU-I Process Train",
    "date": "2023-12-05",
    "source_file": "EH_C101_Column_Fouling_History.json",
    "page_number": 1,
    "section": "2.0 Tray Differential Pressure & Salt Deposition",
    "metadata": {
        "commissioning_date": "2016-05-10",
        "flash_zone_thickness": "24.8 mm",
        "t_min": "18.0 mm"
    },
    "content": (
        "MRPL EQUIPMENT HISTORY — C-101\n"
        "Main Atmospheric Column C-101. Historical tray differential pressure increased across trays 14-22 due to ammonium chloride salting in 2021. Online water wash procedure executed successfully restoring column pressure drop from 180 mbar to 95 mbar. Flash zone casing thickness verified at 24.8 mm in 2023."
    )
})

docs.append({
    "category": "02_Equipment_History",
    "filename": "EH_E101_Exchanger_Fouling_History.json",
    "document_id": "MRPL-EH-E101",
    "document_type": "Equipment History",
    "title": "Equipment History: Exchangers E-101A-D",
    "equipment_tag": "E-101",
    "equipment_type": "Shell and Tube Heat Exchanger",
    "plant_area": "CDU-I Preheat Train",
    "date": "2024-04-18",
    "source_file": "EH_E101_Exchanger_Fouling_History.json",
    "page_number": 1,
    "section": "2.0 Thermal Duty & Tube Leak Log",
    "metadata": {
        "commissioning_date": "2018-08-01",
        "fouling_factor_design": "0.0007 m2-K/W"
    },
    "content": (
        "MRPL EQUIPMENT HISTORY — E-101\n"
        "Crude Preheat Exchanger Train E-101. Tube bundle hydrojetting performed at 18-month intervals during scheduled maintenance windows. In 2022, 2 leaking tubes were plugged in E-101B bundle (total plugged 2 of 840 tubes = 0.24%, well below 10% thermal re-rating threshold)."
    )
})

docs.append({
    "category": "02_Equipment_History",
    "filename": "EH_PSV201_Pop_Test_History.json",
    "document_id": "MRPL-EH-PSV201",
    "document_type": "Equipment History",
    "title": "Safety Relief Valve Certification History: PSV-201",
    "equipment_tag": "PSV-201",
    "equipment_type": "Safety Relief Valve",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2024-02-10",
    "source_file": "EH_PSV201_Pop_Test_History.json",
    "page_number": 1,
    "section": "2.0 Pop Test & Seat Tightness History",
    "metadata": {
        "last_calibration": "2024-01-15",
        "set_pressure_verified": "12.0 barg",
        "as_found_pop_pressure": "12.05 barg"
    },
    "content": (
        "MRPL EQUIPMENT HISTORY — PSV-201\n"
        "Pop test records for P-201 discharge safety valve PSV-201:\n"
        "- 2020-02-18: Initial workshop calibration: Pop at 12.0 barg.\n"
        "- 2022-01-20: 24-month bench test: As found pop pressure 12.1 barg. Seat lapped and re-certified.\n"
        "- 2024-01-15: 48-month bench test: As found pop pressure 12.05 barg (+0.4% deviation, API 527 pass). Valve re-tagged and certified for 24 months."
    )
})

docs.append({
    "category": "02_Equipment_History",
    "filename": "EH_XV203_Stroke_Test_History.json",
    "document_id": "MRPL-EH-XV203",
    "document_type": "Equipment History",
    "title": "Emergency Shutdown Valve Partial Stroke History: XV-203",
    "equipment_tag": "XV-203",
    "equipment_type": "Emergency Shutdown Valve",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2024-07-02",
    "source_file": "EH_XV203_Stroke_Test_History.json",
    "page_number": 1,
    "section": "2.0 PST Quarterly Test Results",
    "metadata": {
        "pst_device": "Smart Valve Positioner DVC6200",
        "average_stroke_time": "5.8 sec"
    },
    "content": (
        "MRPL EQUIPMENT HISTORY — XV-203\n"
        "Automated Partial Stroke Testing (PST) log for P-201 suction ESD valve XV-203. Quarterly 15% stroke test conducted automatically by DCS. All 8 quarterly tests from 2022-2024 passed without pneumatic sticking. Full stroke closure test on 2024 turnaround demonstrated full isolation in 5.8 seconds."
    )
})

# ==========================================
# 03. Inspection Reports (8 documents)
# ==========================================
docs.append({
    "category": "03_Inspection_Reports",
    "filename": "INSP_2024_P201_UT_Survey_Report.json",
    "document_id": "MRPL-INSP-2024-P201",
    "document_type": "Inspection Reports",
    "title": "NDT Ultrasonic Thickness Survey Report: P-201 Casing (2024)",
    "equipment_tag": "P-201",
    "equipment_type": "Centrifugal Pump",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2024-06-01",
    "source_file": "INSP_2024_P201_UT_Survey_Report.json",
    "page_number": 1,
    "section": "3.0 NDT Ultrasonic Survey & Corrosion Rate Assessment",
    "metadata": {
        "report_id": "MRPL/NDT/UT/2024/P201-01",
        "lead_inspector": "A. K. Sharma (Level III NDT / API 570 Certified)",
        "instrument": "Olympus 38DL Plus Ultrasonic Thickness Gage",
        "previous_thickness": "6.0 mm",
        "current_thickness": "4.5 mm",
        "inspection_interval": "5.0 years",
        "minimum_allowable_thickness": "3.5 mm",
        "corrosion_rate": "0.30 mm/year"
    },
    "content": (
        "MRPL STATUTORY INSPECTION REPORT — P-201\n"
        "Report ID: MRPL/NDT/UT/2024/P201-01\n"
        "Inspection Date: 2024-06-01\n"
        "Equipment: Crude Distillation Feed Pump P-201\n"
        "Plant Area: CDU-II Processing Area\n"
        "Method: High-Temperature Ultrasonic Pulse-Echo Thickness Gauging (ASTM E797 / API 570 Section 5.6).\n"
        "Measurement Locations & Findings (CML 1 to CML 4):\n"
        "- CML-01 (Suction Nozzle Neck): 4.8 mm\n"
        "- CML-02 (Pump Casing Inboard Belly): 4.5 mm (Minimum Measured Thickness)\n"
        "- CML-03 (Pump Casing Outboard Volute): 4.6 mm\n"
        "- CML-04 (Discharge Nozzle Neck): 4.9 mm\n"
        "Key Engineering Evidence:\n"
        "• Previous Wall Thickness (measured 2019 baseline): 6.0 mm (verified from Baseline Inspection Report)\n"
        "• Current Wall Thickness (measured 2024 survey): 4.5 mm (verified from CML-02)\n"
        "• Inspection Interval: 5.0 years (2019-06-01 to 2024-06-01)\n"
        "• Minimum Allowable Retirement Thickness (t_min): 3.5 mm\n"
        "Integrity Analysis:\n"
        "- Wall Thickness Reduction: 6.0 mm - 4.5 mm = 1.5 mm\n"
        "- Corrosion Rate: (6.0 - 4.5) / 5.0 = 0.30 mm/year\n"
        "- Current Thickness Margin: 4.5 mm - 3.5 mm = +1.0 mm (Current thickness is ABOVE retirement minimum by 1.0 mm)\n"
        "- Remaining Safe Operating Life: 1.0 mm / 0.30 mm/year = 3.33 years\n"
        "Inspection Conclusion:\n"
        "Pump casing P-201 satisfies API 570 / API 610 structural integrity criteria. No localized pitting or cracking observed. Fit for continued continuous service until next scheduled survey in 2026."
    )
})

docs.append({
    "category": "03_Inspection_Reports",
    "filename": "INSP_2019_P201_Baseline_Inspection_Report.json",
    "document_id": "MRPL-INSP-2019-P201",
    "document_type": "Inspection Reports",
    "title": "Baseline Commissioning NDT Inspection Report: P-201",
    "equipment_tag": "P-201",
    "equipment_type": "Centrifugal Pump",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2019-06-01",
    "source_file": "INSP_2019_P201_Baseline_Inspection_Report.json",
    "page_number": 1,
    "section": "3.0 Commissioning Baseline NDT Inspection",
    "metadata": {
        "report_id": "MRPL/NDT/BASE/2019/P201",
        "baseline_thickness": "6.0 mm",
        "casing_condition": "Pristine Uncorroded"
    },
    "content": (
        "MRPL COMMISSIONING INSPECTION REPORT — P-201\n"
        "Report ID: MRPL/NDT/BASE/2019/P201 | Date: 2019-06-01\n"
        "Equipment: Crude Feed Pump P-201 | Area: CDU-II\n"
        "Baseline ultrasonic measurement across 12 grid points on Sulzer OH2 casing recorded nominal thickness of 6.0 mm (tolerance +0.3/-0.0 mm). Established CML monitoring points for subsequent API 570 surveillance."
    )
})

docs.append({
    "category": "03_Inspection_Reports",
    "filename": "INSP_2024_P101_Vibration_And_UT_Report.json",
    "document_id": "MRPL-INSP-2024-P101",
    "document_type": "Inspection Reports",
    "title": "Condition Monitoring & Vibration Report: P-101A",
    "equipment_tag": "P-101",
    "equipment_type": "Centrifugal Pump",
    "plant_area": "Crude Distillation Unit (CDU-I)",
    "date": "2024-07-28",
    "source_file": "INSP_2024_P101_Vibration_And_UT_Report.json",
    "page_number": 1,
    "section": "3.0 ISO 10816 Vibration & Mechanical Seal Evaluation",
    "metadata": {
        "report_id": "MRPL/CM/2024/P101-07",
        "vibration_nde": "7.4 mm/s RMS (Zone D - Unacceptable)",
        "measured_casing_thickness": "3.8 mm",
        "t_min": "3.2 mm"
    },
    "content": (
        "MRPL CONDITION MONITORING REPORT — P-101A\n"
        "Report ID: MRPL/CM/2024/P101-07 | Date: 2024-07-28\n"
        "Equipment: Atmospheric Residue Pump P-101A | CDU-I\n"
        "Vibration Analysis: NDE bearing axial vibration reached 7.4 mm/s RMS, exceeding ISO 10816-3 Zone D trip limit (7.1 mm/s). Severe shaft misalignment indicated by high 2X FFT harmonics. Wall thickness at suction nozzle measured 3.8 mm (t_min 3.2 mm, margin +0.6 mm). Recommendation: Immediate switchover to standby pump P-101B and workshop overhaul."
    )
})

docs.append({
    "category": "03_Inspection_Reports",
    "filename": "INSP_2023_V201_Internal_Vessel_Inspection.json",
    "document_id": "MRPL-INSP-2023-V201",
    "document_type": "Inspection Reports",
    "title": "Turnaround Internal Vessel Inspection Report: V-201",
    "equipment_tag": "V-201",
    "equipment_type": "Pressure Vessel",
    "plant_area": "CDU-II Light Ends Unit",
    "date": "2023-09-18",
    "source_file": "INSP_2023_V201_Internal_Vessel_Inspection.json",
    "page_number": 1,
    "section": "3.0 Internal Visual & NDT Ultrasonic Examination",
    "metadata": {
        "report_id": "MRPL/INSP/TA23/V201-01",
        "shell_thickness": "16.4 mm",
        "t_min": "12.5 mm",
        "internal_condition": "Satisfactory"
    },
    "content": (
        "MRPL TURNAROUND INSPECTION REPORT — V-201\n"
        "Report ID: MRPL/INSP/TA23/V201-01 | Date: 2023-09-18\n"
        "Equipment: High Pressure Separator V-201 | CDU-II\n"
        "Internal visual inspection per API 510. Shell plate thickness measured at 16.4 mm (t_min 12.5 mm). Vortex breaker and wire mesh demister in good condition. Magnetic particle testing of nozzle-to-shell welds showed zero indications."
    )
})

docs.append({
    "category": "03_Inspection_Reports",
    "filename": "INSP_2024_TK201_Floor_MFL_Inspection.json",
    "document_id": "MRPL-INSP-2024-TK201",
    "document_type": "Inspection Reports",
    "title": "Tank Bottom Floor MFL & Ultrasonic Inspection: TK-201",
    "equipment_tag": "TK-201",
    "equipment_type": "Atmospheric Storage Tank",
    "plant_area": "Tank Farm Area 3",
    "date": "2024-02-28",
    "source_file": "INSP_2024_TK201_Floor_MFL_Inspection.json",
    "page_number": 1,
    "section": "3.0 Magnetic Flux Leakage (MFL) Floor Scan",
    "metadata": {
        "report_id": "MRPL/TANK/2024/TK201",
        "floor_plates_scanned": "144 plates",
        "min_bottom_plate_thickness": "10.2 mm"
    },
    "content": (
        "MRPL TANK INTEGRITY REPORT — TK-201\n"
        "Report ID: MRPL/TANK/2024/TK201 | Date: 2024-02-28\n"
        "API 653 In-Service Acoustic Emission and Bottom Plate MFL scanning. Minimum remaining floor plate thickness 10.2 mm (nominal 12.0 mm, retirement 6.0 mm). Calculated bottom plate corrosion rate 0.30 mm/year. Tank certified for continued service until 2030."
    )
})

docs.append({
    "category": "03_Inspection_Reports",
    "filename": "INSP_2023_C101_Gamma_Scan_Report.json",
    "document_id": "MRPL-INSP-2023-C101",
    "document_type": "Inspection Reports",
    "title": "Online Gamma Ray Column Scan Report: C-101",
    "equipment_tag": "C-101",
    "equipment_type": "Distillation Column",
    "plant_area": "CDU-I Process Train",
    "date": "2023-11-14",
    "source_file": "INSP_2023_C101_Gamma_Scan_Report.json",
    "page_number": 1,
    "section": "3.0 Online Radiometric Density Profile",
    "metadata": {
        "report_id": "MRPL/RAD/2023/C101",
        "scan_technique": "Dual Source Cobalt-60 Gamma Scanning",
        "findings": "Trays 18-22 Froth Height Normal"
    },
    "content": (
        "MRPL RADIOMETRIC INSPECTION REPORT — C-101\n"
        "Report ID: MRPL/RAD/2023/C101 | Date: 2023-11-14\n"
        "Online Gamma Density profile across all 48 valve trays of C-101. Confirmed uniform liquid aeration and froth height across wash zone (trays 18-22). No weeping or tray flooding observed at 105% crude throughput."
    )
})

docs.append({
    "category": "03_Inspection_Reports",
    "filename": "INSP_2024_E101_IRIS_Tube_Inspection.json",
    "document_id": "MRPL-INSP-2024-E101",
    "document_type": "Inspection Reports",
    "title": "Internal Rotary Inspection System (IRIS) Tube Report: E-101B",
    "equipment_tag": "E-101",
    "equipment_type": "Shell and Tube Heat Exchanger",
    "plant_area": "CDU-I Preheat Train",
    "date": "2024-05-12",
    "source_file": "INSP_2024_E101_IRIS_Tube_Inspection.json",
    "page_number": 1,
    "section": "3.0 IRIS Ultrasonic Tube Thickness Survey",
    "metadata": {
        "report_id": "MRPL/NDT/IRIS/2024/E101B",
        "total_tubes_tested": "840 tubes",
        "max_wall_loss": "18%"
    },
    "content": (
        "MRPL HEAT EXCHANGER INSPECTION REPORT — E-101B\n"
        "Report ID: MRPL/NDT/IRIS/2024/E101B | Date: 2024-05-12\n"
        "IRIS NDT inspection on 100% of 840 carbon steel tubes. Maximum wall loss observed was 18% near baffle support plates (allowable limit 40%). Zero tubes recommended for plugging. Cleanliness index 94% post hydrojetting."
    )
})

docs.append({
    "category": "03_Inspection_Reports",
    "filename": "INSP_2024_PSV201_Pop_Test_Certificate.json",
    "document_id": "MRPL-INSP-2024-PSV201",
    "document_type": "Inspection Reports",
    "title": "Relief Valve Calibration & Seat Tightness Certificate: PSV-201",
    "equipment_tag": "PSV-201",
    "equipment_type": "Safety Relief Valve",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2024-01-15",
    "source_file": "INSP_2024_PSV201_Pop_Test_Certificate.json",
    "page_number": 1,
    "section": "3.0 API 527 Nitrogen Bubble Leak Test",
    "metadata": {
        "certificate_no": "MRPL/VALVE/CERT/2024/PSV201",
        "set_pressure": "12.0 barg",
        "leak_test_bubbles": "0 bubbles/min @ 90% set pressure"
    },
    "content": (
        "MRPL SAFETY VALVE CERTIFICATE — PSV-201\n"
        "Certificate No: MRPL/VALVE/CERT/2024/PSV201 | Date: 2024-01-15\n"
        "Tag: PSV-201 | Service: P-201 Discharge Protection\n"
        "Bench test per API 526 / API 527. Set Pressure verified at 12.0 barg using calibrated digital master gauge. Nitrogen bubble test at 10.8 barg (90% of set) showed 0 bubbles per minute (Tight Shutoff Pass). Next inspection due: January 2026."
    )
})

# ==========================================
# 04. Maintenance Records (8 documents)
# ==========================================
docs.append({
    "category": "04_Maintenance_Records",
    "filename": "MAINT_WO_9021_P201_Mechanical_Seal_Replacement.json",
    "document_id": "MRPL-WO-9021-P201",
    "document_type": "Maintenance Records",
    "title": "Maintenance Work Order WO-9021: P-201 Mechanical Seal Overhaul",
    "equipment_tag": "P-201",
    "equipment_type": "Centrifugal Pump",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2023-11-20",
    "source_file": "MAINT_WO_9021_P201_Mechanical_Seal_Replacement.json",
    "page_number": 1,
    "section": "4.0 Corrective Maintenance & Component Replacement Log",
    "metadata": {
        "work_order_id": "WO-9021-CDU2",
        "maintenance_type": "Preventive & Corrective Overhaul",
        "technician_in_charge": "M. R. Fernandes (Senior Mechanical Supervisor)",
        "replaced_parts": "Plan 53B Dual Seal Cartridge (Burgmann MFLWT80), Tungsten Carbide vs Silicon Carbide faces",
        "shaft_runout_as_left": "0.025 mm (Within API 610 limit 0.038 mm)",
        "coupling_alignment_offset": "0.03 mm radial / 0.02 mm axial"
    },
    "content": (
        "MRPL MAINTENANCE RECORD — WORK ORDER WO-9021\n"
        "Work Order: WO-9021-CDU2 | Completion Date: 2023-11-20\n"
        "Equipment: Crude Feed Pump P-201 | Area: CDU-II\n"
        "Job Description: Overhaul of dual pressurized mechanical seal assembly and laser shaft alignment.\n"
        "Work Carried Out:\n"
        "1. Isolated pump P-201 electrically (LOTO) and hydraulically using suction gate XV-203 and discharge check/gate valves.\n"
        "2. Drained crude oil and decontaminated casing with nitrogen purge.\n"
        "3. Dismantled old mechanical seal. Observed slight thermal blistering on atmospheric silicon carbide face.\n"
        "4. Installed new EagleBurgmann API Plan 53B cartridge seal assembly with premium Kalrez O-rings.\n"
        "5. Refilled Plan 53B barrier fluid reservoir with synthetic Mobil SHC 524 oil and pressurized to 4.5 barg with dry nitrogen.\n"
        "6. Conducted Rotalign laser shaft alignment with 110 kW driver motor. Final alignment: 0.03 mm radial, 0.02 mm axial offset.\n"
        "7. Hydrostatic leak test conducted at 14.5 barg for 30 minutes with zero leakage.\n"
        "8. Test run: 4-hour trial run on crude feed. Bearing temperature stabilized at 58 C, vibration at 1.9 mm/s RMS. Handed over to Operations."
    )
})

docs.append({
    "category": "04_Maintenance_Records",
    "filename": "MAINT_WO_9045_P201_Bearing_Replacement_And_Lube.json",
    "document_id": "MRPL-WO-9045-P201",
    "document_type": "Maintenance Records",
    "title": "Maintenance Work Order WO-9045: P-201 Bearing Housing Service",
    "equipment_tag": "P-201",
    "equipment_type": "Centrifugal Pump",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2024-03-15",
    "source_file": "MAINT_WO_9045_P201_Bearing_Replacement_And_Lube.json",
    "page_number": 1,
    "section": "4.0 Bearing Replacement & Lube Oil Analysis",
    "metadata": {
        "work_order_id": "WO-9045-CDU2",
        "bearings_installed": "SKF 7312 BECBM Paired Angular Contact & 6312 Deep Groove",
        "lube_oil_type": "ISO VG 68 Synthetic Mineral Oil"
    },
    "content": (
        "MRPL MAINTENANCE RECORD — WORK ORDER WO-9045\n"
        "Work Order: WO-9045-CDU2 | Completion Date: 2024-03-15\n"
        "Equipment: Crude Feed Pump P-201 | CDU-II\n"
        "Routine bearing inspection and replacement. Removed drive end and non-drive end bearings. Fitted new matched pair SKF 7312 angular contact thrust bearings and SKF 6312 radial bearing with induction heating to 110 C. Replaced Inpro/Seal bearing isolator labyrinths. Vibration post-replacement: 1.6 mm/s RMS."
    )
})

docs.append({
    "category": "04_Maintenance_Records",
    "filename": "MAINT_WO_8812_P101_Laser_Alignment.json",
    "document_id": "MRPL-WO-8812-P101",
    "document_type": "Maintenance Records",
    "title": "Maintenance Work Order WO-8812: P-101A Laser Realignment",
    "equipment_tag": "P-101",
    "equipment_type": "Centrifugal Pump",
    "plant_area": "Crude Distillation Unit (CDU-I)",
    "date": "2024-08-05",
    "source_file": "MAINT_WO_8812_P101_Laser_Alignment.json",
    "page_number": 1,
    "section": "4.0 Shaft Alignment & Coupling Overhaul",
    "metadata": {
        "work_order_id": "WO-8812-CDU1",
        "alignment_tool": "Prueftechnik Rotalign Ultra"
    },
    "content": (
        "MRPL MAINTENANCE RECORD — WORK ORDER WO-8812\n"
        "Equipment: P-101A Residue Pump. Action: Corrected angular soft foot on motor baseplate. Realigned pump-to-motor spacer coupling following high vibration alarm. Replaced worn flexible disc pack coupling."
    )
})

docs.append({
    "category": "04_Maintenance_Records",
    "filename": "MAINT_WO_8901_V201_Demister_Pad_Replacement.json",
    "document_id": "MRPL-WO-8901-V201",
    "document_type": "Maintenance Records",
    "title": "Maintenance Record: Vessel V-201 Demister Replacement",
    "equipment_tag": "V-201",
    "equipment_type": "Pressure Vessel",
    "plant_area": "CDU-II Light Ends Unit",
    "date": "2023-09-22",
    "source_file": "MAINT_WO_8901_V201_Demister_Pad_Replacement.json",
    "page_number": 1,
    "section": "4.0 Vessel Internals Maintenance",
    "metadata": {
        "work_order_id": "WO-8901-V201",
        "demister_material": "SS316L Knitted Wire Mesh 150 mm thick"
    },
    "content": (
        "MRPL MAINTENANCE RECORD — WORK ORDER WO-8901\n"
        "Equipment: Separator V-201. Replaced fouled knitted wire mesh demister pad with new 316L SS structured mesh. Inspected inlet vane diffuser and oil weir. All hold-down J-bolts torque verified."
    )
})

docs.append({
    "category": "04_Maintenance_Records",
    "filename": "MAINT_WO_8750_TK201_Rim_Seal_Service.json",
    "document_id": "MRPL-WO-8750-TK201",
    "document_type": "Maintenance Records",
    "title": "Maintenance Record: Tank TK-201 Floating Roof Rim Seal",
    "equipment_tag": "TK-201",
    "equipment_type": "Atmospheric Storage Tank",
    "plant_area": "Tank Farm Area 3",
    "date": "2024-01-18",
    "source_file": "MAINT_WO_8750_TK201_Rim_Seal_Service.json",
    "page_number": 1,
    "section": "4.0 Floating Roof Secondary Seal Maintenance",
    "metadata": {
        "work_order_id": "WO-8750-TK201",
        "seal_type": "Mechanical Shoe Primary + Wiper Secondary"
    },
    "content": (
        "MRPL MAINTENANCE RECORD — WORK ORDER WO-8750\n"
        "Equipment: TK-201 Crude Tank. Replaced 12 damaged secondary wiper seal segments on floating roof perimeter per OISD-117 VOC containment rules. Checked pontoon vapour spaces for hydrocarbons (0% LEL)."
    )
})

docs.append({
    "category": "04_Maintenance_Records",
    "filename": "MAINT_WO_9120_C101_Wash_Water_Nozzle_Unchoke.json",
    "document_id": "MRPL-WO-9120-C101",
    "document_type": "Maintenance Records",
    "title": "Maintenance Record: Column C-101 Wash Water Spray Header",
    "equipment_tag": "C-101",
    "equipment_type": "Distillation Column",
    "plant_area": "CDU-I Process Train",
    "date": "2023-04-14",
    "source_file": "MAINT_WO_9120_C101_Wash_Water_Nozzle_Unchoke.json",
    "page_number": 1,
    "section": "4.0 Spray Nozzle Cleanout & Filter Service",
    "metadata": {
        "work_order_id": "WO-9120-C101"
    },
    "content": (
        "MRPL MAINTENANCE RECORD — WORK ORDER WO-9120\n"
        "Equipment: Column C-101. Cleaned and flushed wash water spray nozzles at Tray 18. Removed iron sulfide and salt scale buildup. Post-cleaning spray pattern verified with clean condensate."
    )
})

docs.append({
    "category": "04_Maintenance_Records",
    "filename": "MAINT_WO_9088_E101_High_Pressure_Hydrojetting.json",
    "document_id": "MRPL-WO-9088-E101",
    "document_type": "Maintenance Records",
    "title": "Maintenance Record: Exchanger E-101 Tube Hydrojetting",
    "equipment_tag": "E-101",
    "equipment_type": "Shell and Tube Heat Exchanger",
    "plant_area": "CDU-I Preheat Train",
    "date": "2024-05-10",
    "source_file": "MAINT_WO_9088_E101_High_Pressure_Hydrojetting.json",
    "page_number": 1,
    "section": "4.0 Tube Bundle Cleaning",
    "metadata": {
        "work_order_id": "WO-9088-E101",
        "jetting_pressure": "1000 bar"
    },
    "content": (
        "MRPL MAINTENANCE RECORD — WORK ORDER WO-9088\n"
        "Equipment: Preheat Exchanger E-101B. Hydrojetting of tube ID with 1000 bar automated rotary lance. Removed crude asphaltene and coke deposits. Shell side flushed with aromatic solvent."
    )
})

docs.append({
    "category": "04_Maintenance_Records",
    "filename": "MAINT_WO_9200_PSV201_Bench_Recalibration.json",
    "document_id": "MRPL-WO-9200-PSV201",
    "document_type": "Maintenance Records",
    "title": "Maintenance Record: Safety Valve PSV-201 Workshop Overhaul",
    "equipment_tag": "PSV-201",
    "equipment_type": "Safety Relief Valve",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2024-01-14",
    "source_file": "MAINT_WO_9200_PSV201_Bench_Recalibration.json",
    "page_number": 1,
    "section": "4.0 Workshop Disassembly & Lapping",
    "metadata": {
        "work_order_id": "WO-9200-PSV201"
    },
    "content": (
        "MRPL MAINTENANCE RECORD — WORK ORDER WO-9200\n"
        "Equipment: PSV-201. Complete workshop overhaul: dismantled valve body, polished 316SS disc and nozzle seats using 3-micron diamond lapping compound. Replaced pilot soft seals and re-assembled. Passed pop and leak test at 12.0 barg."
    )
})

# ==========================================
# 05. P&IDs / Engineering Drawings (5 docs)
# ==========================================
docs.append({
    "category": "05_PIDs_Drawings",
    "filename": "PID_CDU_200_P201_Crude_Booster_Loop.json",
    "document_id": "MRPL-PID-CDU-200",
    "document_type": "P&IDs / Engineering Drawings",
    "title": "P&ID Drawing CDU-200: Crude Feed Pump P-201 Piping & Instrumentation",
    "equipment_tag": "P-201",
    "equipment_type": "P&ID Drawing",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2022-08-10",
    "source_file": "PID_CDU_200_P201_Crude_Booster_Loop.json",
    "page_number": 1,
    "section": "5.0 P&ID Connectivity & Safety Instrumentation Scheme",
    "metadata": {
        "drawing_number": "MRPL-DWG-PID-CDU-200-REV3",
        "revision": "Rev 3 (As-Built)",
        "inlet_line": "12-CDU-CRD-201-300-CS",
        "discharge_line": "10-CDU-CRD-202-300-CS",
        "connected_equipment": ["TK-201", "P-201", "XV-203", "Y-201", "PSV-201", "PCV-201", "E-101", "C-101"]
    },
    "content": (
        "MRPL PROCESS & INSTRUMENTATION DIAGRAM (P&ID) — CDU-200\n"
        "Drawing Number: MRPL-DWG-PID-CDU-200 Rev 3\n"
        "Title: Crude Feed Pump P-201 Suction, Discharge, and Relief Interlocks\n"
        "Flow Path & Connectivity Architecture:\n"
        "1. Suction Line: Crude oil feed is routed from Crude Storage Tank TK-201 via 14-inch header line 14-CDU-CRD-200 into suction isolation ESD valve XV-203.\n"
        "2. Suction Filtration: Downstream of XV-203, crude flows through 12-inch duplex basket strainer Y-201 with differential pressure transmitter PDI-201 (Alarm @ 0.5 bar DP).\n"
        "3. Pump Inlet: Connects to pump P-201 suction flange (12-inch 300# RF). Suction pressure transmitter PT-201 provides low suction trip signal to ESD interlock 200-I-01 (< 0.8 barg).\n"
        "4. Discharge Line: Pump P-201 discharge routes via 10-inch line 10-CDU-CRD-202 through swing check valve CV-201 and motor-operated discharge gate MOV-204.\n"
        "5. Overpressure Protection: Safety relief valve PSV-201 is tapped on 10-CDU-CRD-202 upstream of MOV-204. PSV-201 is set at 12.0 barg with 3-inch discharge routed to Refinery Flare Header.\n"
        "6. Process Control: Flow control valve FCV-201 modulates flow to CDU-I/II preheat exchangers E-101 under DCS cascade control with FIC-201.\n"
        "7. Recirculation / Minimum Flow: Automatic spillback loop containing PCV-201 (fail open) recirculates 45 m3/hr back to tank TK-201 during startup to prevent pump cavitation."
    )
})

docs.append({
    "category": "05_PIDs_Drawings",
    "filename": "PID_CDU_100_P101_Atmospheric_Residue_Loop.json",
    "document_id": "MRPL-PID-CDU-100",
    "document_type": "P&IDs / Engineering Drawings",
    "title": "P&ID Drawing CDU-100: Atmospheric Residue Pump P-101 Loop",
    "equipment_tag": "P-101",
    "equipment_type": "P&ID Drawing",
    "plant_area": "Crude Distillation Unit (CDU-I)",
    "date": "2021-04-12",
    "source_file": "PID_CDU_100_P101_Atmospheric_Residue_Loop.json",
    "page_number": 1,
    "section": "5.0 P&ID Connectivity Scheme",
    "metadata": {
        "drawing_number": "MRPL-DWG-PID-CDU-100-REV4",
        "connected_equipment": ["C-101", "P-101A", "P-101B", "PSV-101", "PCV-101"]
    },
    "content": (
        "MRPL P&ID DRAWING — CDU-100 Rev 4\n"
        "Shows Column C-101 bottoms boot routing residue via line 10-CDU-BOT-101 to parallel pumps P-101A and P-101B. Suction isolation via gate valves XV-103A/B, discharge check valves CV-101A/B, and relief valve PSV-101 set at 9.0 barg to flare."
    )
})

docs.append({
    "category": "05_PIDs_Drawings",
    "filename": "PID_V201_Separator_Vessel_Piping.json",
    "document_id": "MRPL-PID-V201",
    "document_type": "P&IDs / Engineering Drawings",
    "title": "P&ID Drawing CDU-250: High Pressure Separator V-201 Piping",
    "equipment_tag": "V-201",
    "equipment_type": "P&ID Drawing",
    "plant_area": "CDU-II Light Ends Unit",
    "date": "2020-09-15",
    "source_file": "PID_V201_Separator_Vessel_Piping.json",
    "page_number": 1,
    "section": "5.0 Vessel Controls & Relief Routing",
    "metadata": {
        "drawing_number": "MRPL-DWG-PID-CDU-250-REV2"
    },
    "content": (
        "MRPL P&ID DRAWING — CDU-250 Rev 2\n"
        "Vessel V-201 3-phase separation loop. Gas overhead to fuel gas header via PCV-251; hydrocarbon liquid to debutanizer column; water boot interface level control via LIC-252 to sour water stripper. Relief valve PSV-201B set at 28.0 barg."
    )
})

docs.append({
    "category": "05_PIDs_Drawings",
    "filename": "PID_TK201_Tank_Farm_Transfer_Piping.json",
    "document_id": "MRPL-PID-TK201",
    "document_type": "P&IDs / Engineering Drawings",
    "title": "P&ID Drawing TF-301: Crude Tank TK-201 Inlet/Outlet Manifold",
    "equipment_tag": "TK-201",
    "equipment_type": "P&ID Drawing",
    "plant_area": "Tank Farm Area 3",
    "date": "2019-12-10",
    "source_file": "PID_TK201_Tank_Farm_Transfer_Piping.json",
    "page_number": 1,
    "section": "5.0 Tank Farm Manifold & Overfill Protection",
    "metadata": {
        "drawing_number": "MRPL-DWG-PID-TF-301-REV3"
    },
    "content": (
        "MRPL P&ID DRAWING — TF-301 Rev 3\n"
        "Crude Tank TK-201 piping connections. Jetty marine receipt header 24-CRD-JET-01 enters through motor-operated inlet valve MOV-301. Suction withdrawal to CDU-II pump P-201 via 14-inch header 14-CDU-CRD-200. High-high level switch LSHH-301 triggers MOV-301 emergency closure."
    )
})

docs.append({
    "category": "05_PIDs_Drawings",
    "filename": "PID_C101_Distillation_Column_Overhead_System.json",
    "document_id": "MRPL-PID-C101",
    "document_type": "P&IDs / Engineering Drawings",
    "title": "P&ID Drawing CDU-120: Distillation Column C-101 Overhead Circuit",
    "equipment_tag": "C-101",
    "equipment_type": "P&ID Drawing",
    "plant_area": "Crude Distillation Unit (CDU-I)",
    "date": "2020-03-20",
    "source_file": "PID_C101_Distillation_Column_Overhead_System.json",
    "page_number": 1,
    "section": "5.0 Overhead Vapor & Reflux Loop",
    "metadata": {
        "drawing_number": "MRPL-DWG-PID-CDU-120-REV2"
    },
    "content": (
        "MRPL P&ID DRAWING — CDU-120 Rev 2\n"
        "Column C-101 overhead vapor line 24-CDU-VAP-101 routes to overhead air fin condensers E-102. Naphtha reflux drum V-102 liquid pumped back as top reflux by P-102A/B. Overhead corrosion inhibitor injection quill located upstream of condensers."
    )
})

# ==========================================
# 06. SOPs (5 documents)
# ==========================================
docs.append({
    "category": "06_SOPs",
    "filename": "SOP_OPS_014_P201_Startup_Shutdown_Procedure.json",
    "document_id": "MRPL-SOP-OPS-014",
    "document_type": "SOPs",
    "title": "Standard Operating Procedure SOP-OPS-014: P-201 Startup, Operation & Shutdown",
    "equipment_tag": "P-201",
    "equipment_type": "Centrifugal Pump",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2023-05-10",
    "source_file": "SOP_OPS_014_P201_Startup_Shutdown_Procedure.json",
    "page_number": 1,
    "section": "6.0 Mandatory Operating Sequence & Safety Interlocks",
    "metadata": {
        "sop_number": "MRPL-SOP-CDU2-P201-014",
        "revision": "Rev 4",
        "author": "Operations Discipline Committee",
        "approval_authority": "Chief General Manager (Refinery Production)"
    },
    "content": (
        "MRPL STANDARD OPERATING PROCEDURE — SOP-OPS-014\n"
        "Title: Startup, Normal Monitoring, and Emergency Shutdown Procedure for Crude Feed Pump P-201.\n"
        "Pre-Startup Checklist:\n"
        "1. Confirm Work Permits are closed and LOTO locks removed.\n"
        "2. Check Plan 53B seal barrier fluid level in sight glass (normal level 60-80%) and pressure at 4.5 barg.\n"
        "3. Ensure suction ESD valve XV-203 is fully open and basket strainer Y-201 DP is < 0.2 bar.\n"
        "4. Open pump casing vent valve until liquid crude oil flows continuously without gas bubbles, then tightly close vent.\n"
        "5. Verify minimum flow recirculation valve PCV-201 is in AUTO mode (open).\n"
        "Startup Sequence:\n"
        "6. Start lube oil / seal cooling circulation.\n"
        "7. Press Local/DCS Motor Start button for 110 kW driver.\n"
        "8. Check discharge pressure builds promptly to ~9.8 barg. If discharge pressure fails to rise within 5 seconds, trip motor immediately.\n"
        "9. Slowly open discharge motor operated valve MOV-204 to establish crude flow to preheat train E-101.\n"
        "10. Verify vibration is < 2.8 mm/s RMS and bearing temperature is < 70 C.\n"
        "Emergency Shutdown Actions:\n"
        "- High Vibration Alarm (> 4.5 mm/s RMS): Notify Panel Officer; inspect for cavitation.\n"
        "- High Vibration Trip (> 7.1 mm/s RMS) or Low Suction (< 0.8 barg): Automated trip initiated by DCS. Close XV-203 immediately."
    )
})

docs.append({
    "category": "06_SOPs",
    "filename": "SOP_OPS_010_P101_Pump_Switchover_Procedure.json",
    "document_id": "MRPL-SOP-OPS-010",
    "document_type": "SOPs",
    "title": "Standard Operating Procedure SOP-OPS-010: P-101A/B Duty Switchover",
    "equipment_tag": "P-101",
    "equipment_type": "Centrifugal Pump",
    "plant_area": "Crude Distillation Unit (CDU-I)",
    "date": "2022-11-15",
    "source_file": "SOP_OPS_010_P101_Pump_Switchover_Procedure.json",
    "page_number": 1,
    "section": "6.0 Hot Pump Warm-Up & Online Transfer Sequence",
    "metadata": {
        "sop_number": "MRPL-SOP-CDU1-P101-010"
    },
    "content": (
        "MRPL STANDARD OPERATING PROCEDURE — SOP-OPS-010\n"
        "Hot Residue Pump P-101A/B Switchover Procedure. Warm up standby pump casing at max 50 C/hr using warm-up bypass line before starting driver motor. Equalize discharge pressure before transitioning control loop."
    )
})

docs.append({
    "category": "06_SOPs",
    "filename": "SOP_MAINT_005_Centrifugal_Pump_Isolation_LOTO.json",
    "document_id": "MRPL-SOP-MAINT-005",
    "document_type": "SOPs",
    "title": "Standard Operating Procedure SOP-MAINT-005: Rotating Equipment Isolation & LOTO",
    "equipment_tag": "P-201",
    "equipment_type": "SOP / Safety Rule",
    "plant_area": "Refinery-Wide",
    "date": "2023-01-10",
    "source_file": "SOP_MAINT_005_Centrifugal_Pump_Isolation_LOTO.json",
    "page_number": 1,
    "section": "6.0 Positive Electrical & Mechanical Isolation",
    "metadata": {
        "sop_number": "MRPL-SOP-SAFE-LOTO-005"
    },
    "content": (
        "MRPL STANDARD OPERATING PROCEDURE — SOP-MAINT-005\n"
        "Refinery Standard for Positive Mechanical Isolation & Electrical Lockout/Tagout (LOTO). Mandatory installation of slip blinds / spades on suction and discharge flanges for hydrocarbon services > 60 C before confined space or pump teardown."
    )
})

docs.append({
    "category": "06_SOPs",
    "filename": "SOP_SAFETY_021_PSV_Online_Testing_And_Isolation.json",
    "document_id": "MRPL-SOP-SAFETY-021",
    "document_type": "SOPs",
    "title": "Standard Operating Procedure SOP-SAFETY-021: PSV Isolation with Car-Seal Rules",
    "equipment_tag": "PSV-201",
    "equipment_type": "Safety Relief Valve",
    "plant_area": "Refinery-Wide",
    "date": "2022-06-18",
    "source_file": "SOP_SAFETY_021_PSV_Online_Testing_And_Isolation.json",
    "page_number": 1,
    "section": "6.0 Car-Seal Open/Closed (CSO/CSC) Management",
    "metadata": {
        "sop_number": "MRPL-SOP-SAFE-PSV-021"
    },
    "content": (
        "MRPL STANDARD OPERATING PROCEDURE — SOP-SAFETY-021\n"
        "Relief Valve Isolation & Car-Seal Governance per OISD-106. Upstream and downstream isolation block valves on PSV installations must remain locked Car-Seal Open (CSO). Any seal breakage requires Level-2 Shift In-Charge signed authorization."
    )
})

docs.append({
    "category": "06_SOPs",
    "filename": "SOP_EMERG_002_Hydrocarbon_Loss_Containment.json",
    "document_id": "MRPL-SOP-EMERG-002",
    "document_type": "SOPs",
    "title": "Emergency Response Procedure SOP-EMERG-002: Major Hydrocarbon Loss of Containment",
    "equipment_tag": "P-201",
    "equipment_type": "Emergency Procedure",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2023-08-01",
    "source_file": "SOP_EMERG_002_Hydrocarbon_Loss_Containment.json",
    "page_number": 1,
    "section": "6.0 Unit Emergency Depressuring & ESD Activation",
    "metadata": {
        "sop_number": "MRPL-SOP-EMERG-002"
    },
    "content": (
        "MRPL EMERGENCY RESPONSE PROCEDURE — SOP-EMERG-002\n"
        "Major Hydrocarbon Loss of Containment Protocol. Immediate actuation of Unit ESD button: trips feed pumps P-201/P-101, closes suction ESD valves XV-203/XV-103, and activates deluge fire water spray system across pump manifolds."
    )
})

# ==========================================
# 07. Engineering Manuals (5 documents)
# ==========================================
docs.append({
    "category": "07_Engineering_Manuals",
    "filename": "MAN_API_610_Centrifugal_Pumps_Standard.json",
    "document_id": "MRPL-MAN-API-610",
    "document_type": "Engineering Manuals",
    "title": "Engineering Standard Manual: API 610 / ISO 13709 Centrifugal Pumps for Petroleum Industries",
    "equipment_tag": "P-201",
    "equipment_type": "Engineering Standard",
    "plant_area": "Refinery Engineering Standards",
    "date": "2021-12-01",
    "source_file": "MAN_API_610_Centrifugal_Pumps_Standard.json",
    "page_number": 1,
    "section": "7.0 Mechanical & Integrity Design Standards",
    "metadata": {
        "standard_code": "API Standard 610 12th Edition",
        "governing_body": "American Petroleum Institute"
    },
    "content": (
        "MRPL ENGINEERING DESIGN MANUAL — API 610 12TH EDITION\n"
        "Centrifugal Pumps for Petroleum, Petrochemical and Natural Gas Industries.\n"
        "Key Engineering Rules & Limits:\n"
        "1. Casing Design: Casings must be designed for maximum allowable working pressure (MAWP) with a minimum corrosion allowance of 3.0 mm for carbon steel.\n"
        "2. Minimum Retirement Wall Thickness (t_min): Calculated using membrane hoop stress formula: t_min = (P * D) / (2 * S * E - 1.2 * P). Casings below t_min cannot operate without formal re-rating.\n"
        "3. Vibration Limits (ISO 10816-3 / API 610 Table 8):\n"
        "   - Zone A/B (< 3.0 mm/s RMS): Acceptable newly commissioned condition.\n"
        "   - Zone C (3.0 to 4.5 mm/s RMS): Warning threshold — mandatory monitoring.\n"
        "   - Zone D (> 7.1 mm/s RMS): Unacceptable condition — mandatory trip/shutdown.\n"
        "4. Impeller Wear Ring Clearances: Diametral clearance must not exceed 2.0x API 610 baseline table values (e.g. 0.50 mm max for 150 mm ring diameter)."
    )
})

docs.append({
    "category": "07_Engineering_Manuals",
    "filename": "MAN_API_570_Piping_And_Casing_Inspection.json",
    "document_id": "MRPL-MAN-API-570",
    "document_type": "Engineering Manuals",
    "title": "Engineering Standard Manual: API 570 In-Service Piping & Equipment Inspection Code",
    "equipment_tag": "P-201",
    "equipment_type": "Engineering Standard",
    "plant_area": "Refinery Inspection Department",
    "date": "2022-03-15",
    "source_file": "MAN_API_570_Piping_And_Casing_Inspection.json",
    "page_number": 1,
    "section": "7.0 Inspection Intervals & Remaining Life Calculation Formulae",
    "metadata": {
        "standard_code": "API 570 4th Edition",
        "governing_body": "American Petroleum Institute"
    },
    "content": (
        "MRPL ENGINEERING INSPECTION MANUAL — API 570 4TH EDITION\n"
        "Section 7: Evaluation of Inspection Data & Degradation Rates.\n"
        "1. Long-Term Corrosion Rate Formula: CR = (t_previous - t_current) / inspection_interval (mm/year).\n"
        "2. Remaining Life Formula: RL = (t_current - t_minimum) / CR (years).\n"
        "3. Thickness Margin Formula: Margin = t_current - t_minimum (mm). When Margin > 0, current thickness is ABOVE minimum retirement limit.\n"
        "4. Safety Governance Policy: If remaining life is < 2.0 years or if t_current <= t_minimum, automated approval is prohibited. Mandatory Chief Inspector review required."
    )
})

docs.append({
    "category": "07_Engineering_Manuals",
    "filename": "MAN_OISD_118_Refinery_Layout_And_Safety.json",
    "document_id": "MRPL-MAN-OISD-118",
    "document_type": "Engineering Manuals",
    "title": "Engineering Standard Manual: OISD-STD-118 Layouts & Safety in Refineries",
    "equipment_tag": "P-201",
    "equipment_type": "Statutory Safety Standard",
    "plant_area": "Refinery-Wide",
    "date": "2020-07-20",
    "source_file": "MAN_OISD_118_Refinery_Layout_And_Safety.json",
    "page_number": 1,
    "section": "7.0 Spacing & Hazardous Area Classification",
    "metadata": {
        "standard_code": "OISD-STD-118",
        "governing_body": "Oil Industry Safety Directorate (India)"
    },
    "content": (
        "MRPL SAFETY MANUAL — OISD-STD-118\n"
        "Mandatory minimum safety distances between pump houses and crude storage tanks (> 30 meters). Class-A hydrocarbon pumps must have dedicated containment dykes and remote emergency ESD actuation buttons."
    )
})

docs.append({
    "category": "07_Engineering_Manuals",
    "filename": "MAN_ASME_SEC_VIII_Pressure_Vessel_Design.json",
    "document_id": "MRPL-MAN-ASME-VIII",
    "document_type": "Engineering Manuals",
    "title": "Engineering Manual: ASME Boiler & Pressure Vessel Code Section VIII Div 1",
    "equipment_tag": "V-201",
    "equipment_type": "Engineering Standard",
    "plant_area": "Static Equipment Engineering",
    "date": "2021-08-10",
    "source_file": "MAN_ASME_SEC_VIII_Pressure_Vessel_Design.json",
    "page_number": 1,
    "section": "7.0 Pressure Vessel Shell Thickness Formulae",
    "metadata": {
        "standard_code": "ASME BPVC Section VIII Division 1",
        "governing_body": "ASME"
    },
    "content": (
        "MRPL ENGINEERING MANUAL — ASME SECTION VIII DIV 1\n"
        "UG-27 Thickness of Cylindrical Shells under Internal Pressure: t = (P * R) / (S * E - 0.6 * P). Joint efficiency E = 1.0 for 100% radiographic examination."
    )
})

docs.append({
    "category": "07_Engineering_Manuals",
    "filename": "MAN_MRPL_CORR_GUIDE_Refinery_Corrosion_Management.json",
    "document_id": "MRPL-MAN-CORR-001",
    "document_type": "Engineering Manuals",
    "title": "Technical Guidance Manual: MRPL Refinery Corrosion Management & Naphthenic Acid Control",
    "equipment_tag": "P-201",
    "equipment_type": "Internal Technical Manual",
    "plant_area": "Corrosion & Metallurgy Group",
    "date": "2023-02-14",
    "source_file": "MAN_MRPL_CORR_GUIDE_Refinery_Corrosion_Management.json",
    "page_number": 1,
    "section": "7.0 High TAN Opportunity Crude Management",
    "metadata": {
        "manual_code": "MRPL-ENG-CORR-MGT-2023"
    },
    "content": (
        "MRPL REFINERY CORROSION MANAGEMENT MANUAL\n"
        "Guidelines for processing high TAN crudes (> 1.5 mg KOH/g). Naphthenic acid corrosion attacks carbon steel components at 220-400 C with shear velocities > 3 m/s. Feed pumps P-201 and transfer piping require 317L SS / 9Cr clad upgrades when TAN exceeds 2.0."
    )
})

# ==========================================
# 08. Previous Decisions (5 documents)
# ==========================================
docs.append({
    "category": "08_Previous_Engineering_Decisions",
    "filename": "DEC_ENG_2023_08_P201_Impeller_Material_Upgrade.json",
    "document_id": "MRPL-DEC-2023-08",
    "document_type": "Previous Engineering Decisions",
    "title": "Engineering Decision MOC-2023-08: Material Upgrade for P-201 Impeller & Wear Rings",
    "equipment_tag": "P-201",
    "equipment_type": "Management of Change (MOC) Decision",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2023-08-14",
    "source_file": "DEC_ENG_2023_08_P201_Impeller_Material_Upgrade.json",
    "page_number": 1,
    "section": "8.0 Management of Change Technical Evaluation & Approval Record",
    "metadata": {
        "moc_number": "MOC/MRPL/CDU2/2023/08",
        "change_type": "Material of Construction (MOC) Upgrade",
        "initiator": "Reliability Engineering Group",
        "approver": "Technical Director / Chief General Manager (Technical)",
        "approved_material": "Duplex Stainless Steel (UNS S31803 / ASTM A890 Gr 4A)"
    },
    "content": (
        "MRPL PREVIOUS ENGINEERING DECISION RECORD — MOC-2023-08\n"
        "MOC Reference: MOC/MRPL/CDU2/2023/08 | Approval Date: 2023-08-14\n"
        "Subject: Approval of Duplex Stainless Steel Impeller Upgrade for Crude Feed Pump P-201.\n"
        "Background & Technical Justification:\n"
        "- Processing of opportunity high-acid sour crude parcels led to accelerated erosive wear on the original 12% Cr CA6NM impeller vanes.\n"
        "- Technical Review Committee evaluated 3 metallurgy alternatives: 316L SS, Duplex 2205 (UNS S31803), and Alloy 20.\n"
        "Decision & Ruling:\n"
        "1. APPROVED replacement of P-201 impeller and casing wear rings with 2205 Duplex Stainless Steel (ASTM A890 Gr 4A) during the next major turnaround.\n"
        "2. APPROVED retention of ASTM A216 WCB casing with requirement for ultrasonic wall thickness monitoring at 24-month intervals (per API 570).\n"
        "3. Verified that casing corrosion rate of 0.30 mm/year provides > 3.3 years remaining life above t_min (3.5 mm), confirming no immediate casing shell replacement is required.\n"
        "Status: IMPLEMENTED during November 2023 scheduled overhaul window."
    )
})

docs.append({
    "category": "08_Previous_Engineering_Decisions",
    "filename": "DEC_ENG_2022_03_P201_Minimum_Flow_Spillback_Modification.json",
    "document_id": "MRPL-DEC-2022-03",
    "document_type": "Previous Engineering Decisions",
    "title": "Engineering Decision MOC-2022-03: P-201 Minimum Flow Line Resizing",
    "equipment_tag": "P-201",
    "equipment_type": "Management of Change Decision",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2022-03-22",
    "source_file": "DEC_ENG_2022_03_P201_Minimum_Flow_Spillback_Modification.json",
    "page_number": 1,
    "section": "8.0 Hydraulic Assessment & Orifice Sizing",
    "metadata": {
        "moc_number": "MOC/MRPL/CDU2/2022/03",
        "approved_recirculation_rate": "45 m3/hr"
    },
    "content": (
        "MRPL ENGINEERING DECISION — MOC-2022-03\n"
        "Subject: P-201 Minimum Continuous Stable Flow (MCSF) Line Upgrade.\n"
        "Approved increasing spillback restriction orifice diameter from 32 mm to 40 mm to ensure 45 m3/hr minimum flow back to TK-201 during startup throttling, preventing low-flow thermal cavitation."
    )
})

docs.append({
    "category": "08_Previous_Engineering_Decisions",
    "filename": "DEC_ENG_2024_01_P101A_Run_To_Turnaround_Approval.json",
    "document_id": "MRPL-DEC-2024-01",
    "document_type": "Previous Engineering Decisions",
    "title": "Engineering Decision: P-101A Operational Risk Mitigation & Switchover",
    "equipment_tag": "P-101",
    "equipment_type": "Operational Risk Decision",
    "plant_area": "Crude Distillation Unit (CDU-I)",
    "date": "2024-08-02",
    "source_file": "DEC_ENG_2024_01_P101A_Run_To_Turnaround_Approval.json",
    "page_number": 1,
    "section": "8.0 High-Risk Operational Governance Review",
    "metadata": {
        "decision_id": "DEC-ENG-2024-01",
        "ruling": "REJECTED unmonitored run. ORDERED immediate switchover to P-101B."
    },
    "content": (
        "MRPL HIGH-RISK ENGINEERING DECISION — DEC-ENG-2024-01\n"
        "Subject: P-101A High Vibration Continued Operation Review.\n"
        "Chief Engineer Ruling: Automated continued operation REJECTED due to ISO 10816 Zone D trip exceedance (7.4 mm/s RMS). Mandated immediate load transfer to standby pump P-101B."
    )
})

docs.append({
    "category": "08_Previous_Engineering_Decisions",
    "filename": "DEC_ENG_2023_11_V201_Corrosion_Allowance_Rerating.json",
    "document_id": "MRPL-DEC-2023-11",
    "document_type": "Previous Engineering Decisions",
    "title": "Engineering Decision: Vessel V-201 Design Margin Assessment",
    "equipment_tag": "V-201",
    "equipment_type": "Fitness For Service Decision",
    "plant_area": "CDU-II Light Ends Unit",
    "date": "2023-11-05",
    "source_file": "DEC_ENG_2023_11_V201_Corrosion_Allowance_Rerating.json",
    "page_number": 1,
    "section": "8.0 API 579 Fitness for Service Evaluation",
    "metadata": {
        "decision_id": "DEC-ENG-2023-11"
    },
    "content": (
        "MRPL ENGINEERING DECISION — DEC-ENG-2023-11\n"
        "Subject: V-201 High Pressure Separator Remaining Life Certification.\n"
        "API 579 Level 2 Fitness-For-Service analysis approved continued operation at 22.0 barg MAWP based on measured 16.4 mm thickness versus 12.5 mm t_min (remaining corrosion allowance 3.9 mm)."
    )
})

docs.append({
    "category": "08_Previous_Engineering_Decisions",
    "filename": "DEC_ENG_2024_04_TK201_Cathodic_Protection_Upgrade.json",
    "document_id": "MRPL-DEC-2024-04",
    "document_type": "Previous Engineering Decisions",
    "title": "Engineering Decision: TK-201 Impressed Current Cathodic Protection (ICCP)",
    "equipment_tag": "TK-201",
    "equipment_type": "Corrosion Mitigation Decision",
    "plant_area": "Tank Farm Area 3",
    "date": "2024-04-12",
    "source_file": "DEC_ENG_2024_04_TK201_Cathodic_Protection_Upgrade.json",
    "page_number": 1,
    "section": "8.0 ICCP Anode Grid Expansion",
    "metadata": {
        "decision_id": "DEC-ENG-2024-04"
    },
    "content": (
        "MRPL ENGINEERING DECISION — DEC-ENG-2024-04\n"
        "Subject: TK-201 Tank Bottom Underside Cathodic Protection Upgrade.\n"
        "Approved installation of MMO titanium ribbon anode mesh beneath tank floor replacement to suppress external soil-side corrosion to < 0.05 mm/year."
    )
})

# ==========================================
# 09. Technical Datasheets (5 documents)
# ==========================================
docs.append({
    "category": "09_Technical_Datasheets",
    "filename": "DS_P201_Sulzer_OH2_Pump_Datasheet.json",
    "document_id": "MRPL-DS-P201",
    "document_type": "Technical Datasheets",
    "title": "Technical Datasheet: Crude Feed Pump P-201 (API 610 OH2)",
    "equipment_tag": "P-201",
    "equipment_type": "Centrifugal Pump",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2021-02-10",
    "source_file": "DS_P201_Sulzer_OH2_Pump_Datasheet.json",
    "page_number": 1,
    "section": "9.0 Manufacturer Engineering Datasheet",
    "metadata": {
        "datasheet_number": "MRPL-DS-CDU2-P201-REV2",
        "pump_model": "Sulzer API 610 OH2 8x10x15",
        "impeller_diameter_rated": "365 mm",
        "impeller_diameter_max": "385 mm",
        "rated_efficiency": "78.5%",
        "npsh_required": "3.8 m",
        "npsh_available": "6.2 m",
        "casing_nominal_thickness": "6.0 mm",
        "casing_minimum_thickness": "3.5 mm",
        "hydrostatic_test_pressure": "21.75 barg"
    },
    "content": (
        "MRPL TECHNICAL DATASHEET — P-201\n"
        "Datasheet No: MRPL-DS-CDU2-P201 Rev 2\n"
        "Item Tag: P-201 | Service: Crude Distillation Feed Booster\n"
        "Hydraulic Performance Data:\n"
        "- Rated Flow: 320 m3/hr (Normal 290 m3/hr, Minimum Continuous Stable Flow 45 m3/hr)\n"
        "- Total Dynamic Head (TDH): 75 m at rated flow\n"
        "- Suction Pressure: 2.1 barg | Discharge Pressure: 9.8 barg\n"
        "- NPSHr: 3.8 m (NPSHa: 6.2 m — Margin 2.4 m)\n"
        "- Power at Rated Point: 88.5 kW | Motor Rating: 110 kW (415V / 50 Hz / 2950 RPM)\n"
        "Mechanical Design & Thickness Limits:\n"
        "- Casing Type: Radially Split End-Suction Top-Discharge API 610 OH2 with center-line support.\n"
        "- Original Nominal Casing Thickness: 6.0 mm\n"
        "- Minimum Allowable Retirement Thickness (t_min): 3.5 mm\n"
        "- Corrosion Allowance: 2.5 mm\n"
        "- Casing Hydrotest Pressure: 21.75 barg (1.5x MAWP)\n"
        "- Mechanical Seal: Plan 53B pressurized dual cartridge seal."
    )
})

docs.append({
    "category": "09_Technical_Datasheets",
    "filename": "DS_P101_Flowserve_BB2_Datasheet.json",
    "document_id": "MRPL-DS-P101",
    "document_type": "Technical Datasheets",
    "title": "Technical Datasheet: Atmospheric Residue Pump P-101 (API 610 BB2)",
    "equipment_tag": "P-101",
    "equipment_type": "Centrifugal Pump",
    "plant_area": "Crude Distillation Unit (CDU-I)",
    "date": "2020-03-12",
    "source_file": "DS_P101_Flowserve_BB2_Datasheet.json",
    "page_number": 1,
    "section": "9.0 Manufacturer Engineering Datasheet",
    "metadata": {
        "datasheet_number": "MRPL-DS-CDU1-P101-REV3",
        "casing_nominal_thickness": "5.0 mm",
        "casing_minimum_thickness": "3.2 mm"
    },
    "content": (
        "MRPL TECHNICAL DATASHEET — P-101\n"
        "Flowserve BB2 Between-Bearings Pump Datasheet. Rated Flow: 280 m3/hr, Head: 68 m, Casing Nominal Thickness: 5.0 mm, Minimum Allowable Retirement Thickness t_min: 3.2 mm. Material: 5Cr-0.5Mo Alloy Steel."
    )
})

docs.append({
    "category": "09_Technical_Datasheets",
    "filename": "DS_V201_Separator_Vessel_Datasheet.json",
    "document_id": "MRPL-DS-V201",
    "document_type": "Technical Datasheets",
    "title": "Technical Datasheet: High Pressure Separator Vessel V-201",
    "equipment_tag": "V-201",
    "equipment_type": "Pressure Vessel",
    "plant_area": "CDU-II Light Ends Unit",
    "date": "2019-10-15",
    "source_file": "DS_V201_Separator_Vessel_Datasheet.json",
    "page_number": 1,
    "section": "9.0 Vessel Engineering Datasheet",
    "metadata": {
        "datasheet_number": "MRPL-DS-CDU2-V201-REV1",
        "shell_nominal_thickness": "18.0 mm",
        "shell_minimum_thickness": "12.5 mm"
    },
    "content": (
        "MRPL TECHNICAL DATASHEET — V-201\n"
        "High Pressure 3-Phase Separator Vessel Datasheet. ID: 2200 mm, T/T Length: 6800 mm. Shell Nominal Thickness: 18.0 mm, t_min: 12.5 mm. Design Pressure: 28.0 barg @ 120 C. Design Code: ASME Sec VIII Div 1."
    )
})

docs.append({
    "category": "09_Technical_Datasheets",
    "filename": "DS_PSV201_Relief_Valve_Datasheet.json",
    "document_id": "MRPL-DS-PSV201",
    "document_type": "Technical Datasheets",
    "title": "Technical Datasheet: Pilot Relief Valve PSV-201",
    "equipment_tag": "PSV-201",
    "equipment_type": "Safety Relief Valve",
    "plant_area": "Crude Distillation Unit (CDU-II)",
    "date": "2020-01-20",
    "source_file": "DS_PSV201_Relief_Valve_Datasheet.json",
    "page_number": 1,
    "section": "9.0 Valve Sizing Datasheet",
    "metadata": {
        "datasheet_number": "MRPL-DS-PSV-201-REV2",
        "set_pressure": "12.0 barg",
        "orifice_area": "8.30 cm2"
    },
    "content": (
        "MRPL TECHNICAL DATASHEET — PSV-201\n"
        "Anderson Greenwood Series 81 Pilot Operated Safety Relief Valve. Orifice 2J3, Inlet 2-inch 300#, Outlet 3-inch 150#. Set Pressure: 12.0 barg. Relieving Capacity: 75,000 kg/hr crude oil."
    )
})

docs.append({
    "category": "09_Technical_Datasheets",
    "filename": "DS_C101_Column_Internals_Datasheet.json",
    "document_id": "MRPL-DS-C101",
    "document_type": "Technical Datasheets",
    "title": "Technical Datasheet: Column C-101 Fractionation Internals",
    "equipment_tag": "C-101",
    "equipment_type": "Distillation Column",
    "plant_area": "Crude Distillation Unit (CDU-I)",
    "date": "2018-04-18",
    "source_file": "DS_C101_Column_Internals_Datasheet.json",
    "page_number": 1,
    "section": "9.0 Tray & Packed Bed Datasheet",
    "metadata": {
        "datasheet_number": "MRPL-DS-C101-TRAYS-REV1"
    },
    "content": (
        "MRPL TECHNICAL DATASHEET — C-101 TRAYS\n"
        "Koch-Glitsch BD Type Moving Valve Trays (48 Trays). Material: 410S Stainless Steel. Tray Spacing: 600 mm. Max Downcomer Liquid Velocity: 0.18 m/s."
    )
})

# Write all 57 JSON documents
written_count = 0
for d in docs:
    cat_path = KB_DIR / d["category"]
    file_path = cat_path / d["filename"]
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
    written_count += 1

print(f"Successfully written {written_count} documents to MRPL_KNOWLEDGE_BASE across 9 categories.")
