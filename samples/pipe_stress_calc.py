"""
MRPL Mechanical Integrity — Pipeline Minimum Required Thickness Calculator
Compliant with ASME B31.3 (Process Piping Code) Section 304.1.2
"""

def calculate_min_thickness_asme_b313(
    design_pressure_bar: float,
    outside_diameter_mm: float,
    allowable_stress_mpa: float,
    joint_efficiency: float = 1.0,
    weld_factor_w: float = 1.0,
    corrosion_allowance_mm: float = 3.0,
) -> dict:
    """
    t_req = (P * D) / (2 * (S * E * W + P * Y)) + c
    For ferritic steel at T <= 482 C, Y = 0.4
    """
    P_mpa = design_pressure_bar * 0.1
    D = outside_diameter_mm
    S = allowable_stress_mpa
    E = joint_efficiency
    W = weld_factor_w
    Y = 0.4
    c = corrosion_allowance_mm

    numerator = P_mpa * D
    denominator = 2 * (S * E * W + P_mpa * Y)
    pressure_design_thickness = numerator / denominator
    min_required_thickness = pressure_design_thickness + c

    return {
        "pressure_mpa": round(P_mpa, 2),
        "pressure_design_thickness_mm": round(pressure_design_thickness, 3),
        "corrosion_allowance_mm": c,
        "min_required_thickness_mm": round(min_required_thickness, 3),
        "code": "ASME B31.3 Section 304.1.2",
    }

if __name__ == "__main__":
    # Example: P-101 10-inch Crude Line (OD 273.0 mm) at 45 bar, ASTM A106 Gr B (S = 138 MPa)
    result = calculate_min_thickness_asme_b313(
        design_pressure_bar=45.0,
        outside_diameter_mm=273.0,
        allowable_stress_mpa=138.0,
        joint_efficiency=1.0,
        corrosion_allowance_mm=3.0,
    )
    print("ASME B31.3 Calculation Result:")
    for k, v in result.items():
        print(f"  {k}: {v}")
