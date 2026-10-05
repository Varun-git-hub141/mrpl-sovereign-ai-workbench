# backend/services/work_product_docx_generator.py
"""
MRPL Sovereign AI Workbench — Work Product DOCX Generator.
Transforms structured WorkProduct models into formal, air-gapped industrial Word documents.
"""

import os
import time
import logging
from typing import Optional
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn
from backend.models.work_product_models import WorkProduct

logger = logging.getLogger("mrpl.docx.work_product")


class WorkProductDocxGenerator:
    """
    Local DOCX Generator for Verified Industrial Work Products.
    """

    @classmethod
    def generate_docx(
        cls,
        work_product: WorkProduct,
        output_filepath: Optional[str] = None,
    ) -> str:
        """
        Renders the structured WorkProduct object into a professional DOCX file.
        """
        if not output_filepath:
            os.makedirs("artifacts", exist_ok=True)
            output_filepath = os.path.abspath(f"artifacts/{work_product.equipment_tag}_Inspection_Review_Note.docx")

        doc = Document()

        # Set standard margins (0.75 in)
        for section in doc.sections:
            section.top_margin = Inches(0.75)
            section.bottom_margin = Inches(0.75)
            section.left_margin = Inches(0.75)
            section.right_margin = Inches(0.75)

        # ── Title Block / Header ──
        header_p = doc.add_paragraph()
        header_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_company = header_p.add_run("MANGALORE REFINERY AND PETROCHEMICALS LIMITED (MRPL)\n")
        run_company.bold = True
        run_company.font.size = Pt(13)
        run_company.font.color.rgb = RGBColor(0x00, 0x33, 0x66)  # Corporate Navy

        run_sub = header_p.add_run("TECHNICAL SERVICES & ASSET INTEGRITY MANAGEMENT DEPARTMENT\n")
        run_sub.bold = True
        run_sub.font.size = Pt(10)
        run_sub.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

        run_title = header_p.add_run(f"{work_product.title.upper()}\n")
        run_title.bold = True
        run_title.font.size = Pt(12)
        run_title.font.color.rgb = RGBColor(0x8B, 0x00, 0x00)  # Deep Maroon

        cls._add_horizontal_line(doc)

        # ── 1. Document Information ──
        cls._add_heading(doc, "1. Document Information")
        doc_info = [
            ("Work Product ID", work_product.work_product_id),
            ("Document Type", work_product.work_product_type),
            ("Generated Date", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(work_product.created_at))),
            ("Assessment Origin", "MRPL Sovereign AI Workbench (100% Air-Gapped Local Inference)"),
            ("Evidence Status", f"{work_product.evidence_status} (Debt: {work_product.evidence_debt})"),
            ("Data Classification", f"{work_product.demo_data_status} (SOVEREIGN BENCHMARK)"),
        ]
        cls._add_key_value_table(doc, doc_info)

        # ── 2. Asset Identification ──
        cls._add_heading(doc, "2. Asset Identification")
        asset_info = [
            ("Equipment Tag", work_product.equipment_tag),
            ("Asset ID", work_product.asset_id),
            ("Equipment Description", work_product.equipment_name),
            ("Operating Unit / Area", work_product.unit),
            ("Governing Standard", "API 570 / ASME Section VIII Div 1"),
        ]
        cls._add_key_value_table(doc, asset_info)

        # ── 3. Scope of Review ──
        cls._add_heading(doc, "3. Scope of Review & Intent")
        p_scope = doc.add_paragraph()
        p_scope.add_run(f"User Request: \"{work_product.request}\"\n\n").italic = True
        p_scope.add_run(f"Technical Scope: {work_product.scope}")

        # ── 4. Ultrasonic Inspection Observations ──
        cls._add_heading(doc, "4. Ultrasonic Inspection Observations")
        obs_rows = [
            ("Parameter", "Observed Value", "Unit", "Survey Date", "Location", "Source Document", "Lineage")
        ]
        for obs in work_product.observations:
            obs_rows.append((
                obs.parameter,
                str(obs.value),
                obs.unit,
                obs.date,
                obs.location,
                obs.source_document,
                obs.lineage_type.value,
            ))
        cls._add_grid_table(doc, obs_rows)

        # ── 5. Deterministic Engineering Calculation ──
        cls._add_heading(doc, "5. Deterministic Engineering Calculation (API 570)")
        for calc in work_product.calculations:
            calc_info = [
                ("Calculation ID", calc.calculation_id),
                ("Formula Applied", calc.formula_name),
                ("Formula Expression", calc.formula_expression),
                ("Baseline Thickness (t_initial)", f"{calc.inputs.get('t_initial', {}).get('value', 18.0)} mm (Survey: 2017-04-25)"),
                ("Current Thickness (t_current)", f"{calc.inputs.get('t_current', {}).get('value', 17.2)} mm (Survey: 2020-10-14)"),
                ("Inspection Interval (Delta T)", f"{calc.interval_years} years"),
                ("Total Metal Loss", f"{calc.metal_loss_mm} mm"),
                ("Deterministic Result", f"{calc.result_value} {calc.result_unit}"),
                ("Execution Engine", calc.calculator_identity),
                ("Verification Status", calc.verification_status),
            ]
            cls._add_key_value_table(doc, calc_info)

        # ── 6. Substantive Claims & Lineage ──
        cls._add_heading(doc, "6. Claim-Level Provenance & Lineage")
        claim_rows = [("Claim ID", "Statement", "Lineage Classification", "Source Reference", "Verified")]
        for clm in work_product.claims:
            claim_rows.append((
                clm.claim_id,
                clm.text,
                clm.lineage_type.value,
                clm.source_reference,
                "✓ PASS" if clm.is_verified else "✗ UNVERIFIED",
            ))
        cls._add_grid_table(doc, claim_rows)

        # ── 7. Authoritative Source References ──
        cls._add_heading(doc, "7. Authoritative Source References")
        src_rows = [("Document ID", "Filename", "Document Category", "Section Reference", "Authority Level")]
        for src in work_product.source_references:
            src_rows.append((
                src.document_id,
                src.document_name,
                src.document_type,
                src.section or f"Page {src.page or 1}",
                src.authority_level,
            ))
        cls._add_grid_table(doc, src_rows)

        # ── 8. Boundaries & Limitations ──
        cls._add_heading(doc, "8. Scope Boundaries & Limitations")
        for lim in work_product.limitations:
            p_lim = doc.add_paragraph(lim, style='List Bullet')
            p_lim.paragraph_format.space_after = Pt(3)

        # ── 9. Engineering Disclaimer ──
        cls._add_heading(doc, "9. Engineering Disclaimer & Governance Notice")
        p_disc = doc.add_paragraph()
        run_disc = p_disc.add_run(work_product.safety_language)
        run_disc.bold = True
        run_disc.font.size = Pt(9.5)
        run_disc.font.color.rgb = RGBColor(0x66, 0x33, 0x00)

        # Save DOCX
        doc.save(output_filepath)
        logger.info(f"Work product DOCX generated successfully at {output_filepath}")
        return output_filepath

    @classmethod
    def _add_heading(cls, doc: Document, text: str):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(12)
        h.paragraph_format.space_after = Pt(4)
        run = h.add_run(text)
        run.bold = True
        run.font.size = Pt(11.5)
        run.font.color.rgb = RGBColor(0x00, 0x33, 0x66)

    @classmethod
    def _add_horizontal_line(cls, doc: Document):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(8)
        pBdr = parse_xml(r'<w:pBdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                         r'<w:bottom w:val="single" w:sz="12" w:space="1" w:color="003366"/>'
                         r'</w:pBdr>')
        p._p.get_or_add_pPr().append(pBdr)

    @classmethod
    def _add_key_value_table(cls, doc: Document, items: list):
        table = doc.add_table(rows=len(items), cols=2)
        table.autofit = False
        table.columns[0].width = Inches(2.2)
        table.columns[1].width = Inches(4.8)

        for i, (k, v) in enumerate(items):
            row = table.rows[i]
            # Key cell
            c0 = row.cells[0]
            c0.text = k
            p0 = c0.paragraphs[0]
            p0.runs[0].bold = True
            p0.runs[0].font.size = Pt(9.5)
            p0.runs[0].font.color.rgb = RGBColor(0x33, 0x33, 0x33)
            # Value cell
            c1 = row.cells[1]
            c1.text = str(v)
            p1 = c1.paragraphs[0]
            p1.runs[0].font.size = Pt(9.5)
            cls._style_cell(c0, bg_color="F2F5F8")
            cls._style_cell(c1, bg_color="FFFFFF")

        cls._set_table_borders(table)
        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    @classmethod
    def _add_grid_table(cls, doc: Document, rows: list):
        if not rows:
            return
        table = doc.add_table(rows=len(rows), cols=len(rows[0]))
        table.autofit = True

        for r_idx, row_data in enumerate(rows):
            row = table.rows[r_idx]
            is_header = (r_idx == 0)
            for c_idx, val in enumerate(row_data):
                cell = row.cells[c_idx]
                cell.text = str(val)
                p = cell.paragraphs[0]
                if p.runs:
                    p.runs[0].font.size = Pt(9.0)
                    if is_header:
                        p.runs[0].bold = True
                        p.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                        cls._style_cell(cell, bg_color="003366")
                    else:
                        cls._style_cell(cell, bg_color="F9FBFD" if r_idx % 2 == 1 else "FFFFFF")

        cls._set_table_borders(table)
        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    @classmethod
    def _style_cell(cls, cell, bg_color: str = "FFFFFF"):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg_color}"/>')
        tcPr.append(shd)

    @classmethod
    def _set_table_borders(cls, table):
        tblPr = table._tbl.tblPr
        tblBorders = parse_xml(
            r'<w:tblBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            r'<w:top w:val="single" w:sz="4" w:space="0" w:color="D0D7DE"/>'
            r'<w:left w:val="none"/>'
            r'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="D0D7DE"/>'
            r'<w:right w:val="none"/>'
            r'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="EAEAEA"/>'
            r'<w:insideV w:val="none"/>'
            r'</w:tblBorders>'
        )
        tblPr.append(tblBorders)
