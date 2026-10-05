"""
Generates a valid synthetic 5-page PDF test pack for MRPL Sovereign AI Workbench:
- Page 1: Ultrasonic Thickness Inspection Report (P-101, Date: 2026-03-15, 5.0mm -> 3.8mm, 4 yrs, Min allowable 3.2mm, Line 10-CDU-PL-101)
- Page 2: Primary P&ID Diagram CDU-101-01 (P-101, T-101, V-101, V-102, V-103, Flow LEFT -> RIGHT, Connections: P-101 -> V-101 -> V-102 -> V-103 -> T-101)
- Page 3: Auxiliary P&ID Diagram CDU-101-02 (T-101 Storage Vessel, PSV-101, V-104, Flow TOP -> BOTTOM)
- Page 4: Maintenance Procedure & Standard Operating Rules (SOP-MRPL-MNT-2026, 7.1 mm/s vibration trip, mandatory review within 0.6mm)
- Page 5: Inspection Sign-Off, Material Traceability & Summary QA Sheet (ASTM A106 Gr B, 12.5 bar, UT Pulse-Echo)

Uses pure Python standard library to construct a compliant PDF 1.4 document.
"""

import os
from pathlib import Path


def create_pdf(output_path: str):
    # PDF Content definitions for each of the 5 pages
    page1_text = (
        "BT\n"
        "/F1 16 Tf\n"
        "50 750 Td\n"
        "(MRPL REFINERY - EQUIPMENT ULTRASONIC THICKNESS INSPECTION REPORT) Tj\n"
        "/F1 12 Tf\n"
        "0 -30 Td\n"
        "(Report ID: IR-2026-P101-04) Tj\n"
        "0 -20 Td\n"
        "(Equipment Tag: P-101 Transfer Pump) Tj\n"
        "0 -20 Td\n"
        "(Location: Crude Distillation Unit CDU-101) Tj\n"
        "0 -20 Td\n"
        "(Inspection Date: 2026-03-15) Tj\n"
        "0 -20 Td\n"
        "(Connected Process Line: 10-CDU-PL-101) Tj\n"
        "0 -20 Td\n"
        "(Original wall thickness = 5.0 mm) Tj\n"
        "0 -20 Td\n"
        "(Current wall thickness = 3.8 mm) Tj\n"
        "0 -20 Td\n"
        "(Inspection interval = 4 years) Tj\n"
        "0 -20 Td\n"
        "(Minimum allowable thickness = 3.2 mm) Tj\n"
        "0 -20 Td\n"
        "(Inspector: Senior PSU NDT Specialist) Tj\n"
        "0 -20 Td\n"
        "(Status: In Service - Ultrasonic Thickness Survey Complete) Tj\n"
        "ET\n"
    )

    page2_text = (
        "BT\n"
        "/F1 16 Tf\n"
        "50 750 Td\n"
        "(PROCESS & INSTRUMENTATION DIAGRAM - CDU-101-01) Tj\n"
        "/F1 12 Tf\n"
        "0 -30 Td\n"
        "(System: Crude Feed Boost & Transfer Section) Tj\n"
        "0 -20 Td\n"
        "(Equipment Identified: P-101, T-101) Tj\n"
        "0 -20 Td\n"
        "(Valves Identified: V-101, V-102, V-103) Tj\n"
        "0 -20 Td\n"
        "(Connected Process Line: 10-CDU-PL-101) Tj\n"
        "0 -20 Td\n"
        "(Flow direction = LEFT -> RIGHT) Tj\n"
        "0 -20 Td\n"
        "(Flow Path Connections: P-101 -> V-101 -> V-102 -> V-103 -> T-101) Tj\n"
        "0 -20 Td\n"
        "(Isolation Spec: V-101 Suction Gate, V-102 Check Valve, V-103 Discharge Globe) Tj\n"
        "0 -20 Td\n"
        "(Line Size: 10 inch Sch 40 Carbon Steel) Tj\n"
        "ET\n"
    )

    page3_text = (
        "BT\n"
        "/F1 16 Tf\n"
        "50 750 Td\n"
        "(PROCESS & INSTRUMENTATION DIAGRAM - CDU-101-02 AUXILIARY) Tj\n"
        "/F1 12 Tf\n"
        "0 -30 Td\n"
        "(System: Intermediate Storage & Rundown Section) Tj\n"
        "0 -20 Td\n"
        "(Equipment Identified: T-101 Storage Vessel) Tj\n"
        "0 -20 Td\n"
        "(Valves Identified: PSV-101, V-104) Tj\n"
        "0 -20 Td\n"
        "(Flow direction = TOP -> BOTTOM) Tj\n"
        "0 -20 Td\n"
        "(Flow Path Connections: T-101 -> V-104 -> Rundown Header) Tj\n"
        "0 -20 Td\n"
        "(Safety Relief: PSV-101 Set Point 14.5 bar) Tj\n"
        "ET\n"
    )

    page4_text = (
        "BT\n"
        "/F1 16 Tf\n"
        "50 750 Td\n"
        "(MRPL STANDARD OPERATING PROCEDURE & MAINTENANCE RULES) Tj\n"
        "/F1 12 Tf\n"
        "0 -30 Td\n"
        "(Document Ref: SOP-MRPL-MNT-2026) Tj\n"
        "0 -20 Td\n"
        "(1. Verify latest inspection record and wall thickness prior to overhaul.) Tj\n"
        "0 -20 Td\n"
        "(2. If current wall thickness is within 0.6 mm of minimum allowable limit, mandatory engineering review required.) Tj\n"
        "0 -20 Td\n"
        "(3. Verify isolation of V-101, V-102, and V-103 before line entry.) Tj\n"
        "0 -20 Td\n"
        "(4. Unresolved vibration findings exceeding 7.1 mm/s RMS require immediate trip assessment and maintenance closure.) Tj\n"
        "0 -20 Td\n"
        "(5. Confirm flow direction alignment from P-101 discharge to T-101 storage vessel.) Tj\n"
        "ET\n"
    )

    page5_text = (
        "BT\n"
        "/F1 16 Tf\n"
        "50 750 Td\n"
        "(MRPL INSPECTION SIGN-OFF & MATERIAL QA SHEET) Tj\n"
        "/F1 12 Tf\n"
        "0 -30 Td\n"
        "(Material Specification: ASTM A106 Grade B Carbon Steel) Tj\n"
        "0 -20 Td\n"
        "(Operating Pressure: 12.5 bar | Design Pressure: 15.0 bar) Tj\n"
        "0 -20 Td\n"
        "(Operating Temperature: 140 C) Tj\n"
        "0 -20 Td\n"
        "(Non-Destructive Testing Method: Pulse-Echo Ultrasonic Survey UT) Tj\n"
        "0 -20 Td\n"
        "(Review Gate: Human Engineering Review Mandatory for Critical High-Risk Operations) Tj\n"
        "0 -20 Td\n"
        "(Quality Sign-off: Approved by Chief Refinery Integrity Specialist) Tj\n"
        "ET\n"
    )

    # Encode streams
    s1 = page1_text.encode('latin1')
    s2 = page2_text.encode('latin1')
    s3 = page3_text.encode('latin1')
    s4 = page4_text.encode('latin1')
    s5 = page5_text.encode('latin1')

    objects = []
    
    # 1: Catalog
    objects.append("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n".encode('latin1'))
    # 2: Pages (5 Kids)
    objects.append("2 0 obj\n<< /Type /Pages /Kids [3 0 R 5 0 R 7 0 R 9 0 R 11 0 R] /Count 5 >>\nendobj\n".encode('latin1'))
    
    # Page 1
    objects.append(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 13 0 R >> >> >>\nendobj\n")
    objects.append(f"4 0 obj\n<< /Length {len(s1)} >>\nstream\n".encode('latin1') + s1 + b"\nendstream\nendobj\n")

    # Page 2
    objects.append(b"5 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 6 0 R /Resources << /Font << /F1 13 0 R >> >> >>\nendobj\n")
    objects.append(f"6 0 obj\n<< /Length {len(s2)} >>\nstream\n".encode('latin1') + s2 + b"\nendstream\nendobj\n")

    # Page 3
    objects.append(b"7 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 8 0 R /Resources << /Font << /F1 13 0 R >> >> >>\nendobj\n")
    objects.append(f"8 0 obj\n<< /Length {len(s3)} >>\nstream\n".encode('latin1') + s3 + b"\nendstream\nendobj\n")

    # Page 4
    objects.append(b"9 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 10 0 R /Resources << /Font << /F1 13 0 R >> >> >>\nendobj\n")
    objects.append(f"10 0 obj\n<< /Length {len(s4)} >>\nstream\n".encode('latin1') + s4 + b"\nendstream\nendobj\n")

    # Page 5
    objects.append(b"11 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 12 0 R /Resources << /Font << /F1 13 0 R >> >> >>\nendobj\n")
    objects.append(f"12 0 obj\n<< /Length {len(s5)} >>\nstream\n".encode('latin1') + s5 + b"\nendstream\nendobj\n")

    # 13: Font
    objects.append(b"13 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    # Construct complete PDF
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    body = bytearray(header)
    offsets = []

    for obj in objects:
        offsets.append(len(body))
        body.extend(obj)

    xref_offset = len(body)
    xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode('latin1')
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode('latin1')

    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode('latin1')

    body.extend(xref)
    body.extend(trailer)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(body)

    print(f"[OK] Generated 5-page test PDF at: {output_path} ({len(body)} bytes)")


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "MRPL_Sovereign_Multimodal_Test_Pack.pdf")
    create_pdf(out)
