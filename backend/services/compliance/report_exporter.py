"""
Report Exporter Service

Generates professional DOCX compliance reports with Brubru branding.
"""

import logging
from typing import Optional
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session

try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

from ...models.compliance import ComplianceAnalysis, GapFinding
from ...models.eu_law import LawRequirement, LawCluster, EULaw

logger = logging.getLogger(__name__)


class ReportExporter:
    """
    Generates DOCX compliance reports with Brubru branding.
    
    Features:
    - Professional formatting with Brubru colors
    - Compliance score summary
    - Gap findings organized by priority
    - Action plan with deadlines
    - Watermark for Yellow tier users
    """
    
    # Brubru brand colors
    BRUBRU_PURPLE = RGBColor(102, 126, 234)  # #667eea
    BRUBRU_DARK = RGBColor(45, 55, 72)       # #2d3748
    
    STATUS_COLORS = {
        'met': RGBColor(72, 187, 120),       # Green #48bb78
        'partial': RGBColor(221, 107, 32),   # Orange #dd6b20
        'gap': RGBColor(197, 48, 48),        # Red #c53030
    }
    
    def __init__(self, db: Session):
        if not DOCX_AVAILABLE:
            raise RuntimeError("python-docx not installed. Install with: pip install python-docx")
        
        self.db = db
    
    def export_analysis(
        self,
        analysis_id: int,
        output_path: str,
        include_watermark: bool = False
    ) -> str:
        """
        Export compliance analysis to DOCX.
        
        Args:
            analysis_id: ID of the compliance analysis
            output_path: Path to save the DOCX file
            include_watermark: Add watermark for Yellow tier users
            
        Returns:
            Path to the generated file
        """
        logger.info(f"Generating DOCX report for analysis {analysis_id}")
        
        # Get analysis with related data
        analysis = self.db.query(ComplianceAnalysis).filter(
            ComplianceAnalysis.id == analysis_id
        ).first()
        
        if not analysis:
            raise ValueError(f"Analysis {analysis_id} not found")
        
        # Get cluster
        cluster = self.db.query(LawCluster).filter(
            LawCluster.id == analysis.cluster_id
        ).first()
        
        # Get gap findings with requirements
        findings = self.db.query(GapFinding, LawRequirement, EULaw).join(
            LawRequirement, GapFinding.requirement_id == LawRequirement.id
        ).join(
            EULaw, LawRequirement.law_id == EULaw.id
        ).filter(
            GapFinding.analysis_id == analysis_id
        ).order_by(
            GapFinding.priority,
            LawRequirement.criticality.desc()
        ).all()
        
        # Create document
        doc = Document()
        
        # Add watermark if needed
        if include_watermark:
            self._add_watermark(doc)
        
        # Build report
        self._add_header(doc, cluster, analysis)
        self._add_executive_summary(doc, analysis)
        self._add_compliance_score(doc, analysis)
        self._add_gap_findings(doc, findings)
        self._add_action_plan(doc, findings)
        self._add_footer(doc)
        
        # Save document
        doc.save(output_path)
        logger.info(f"Report saved to {output_path}")
        
        return output_path
    
    def _add_watermark(self, doc: Document):
        """Add 'BRUBRU - YELLOW TIER' watermark."""
        section = doc.sections[0]
        header = section.header
        
        paragraph = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        run = paragraph.add_run('BRUBRU - YELLOW TIER')
        run.font.size = Pt(48)
        run.font.color.rgb = RGBColor(200, 200, 200)
        run.font.bold = True
        
        # Make semi-transparent (requires additional XML manipulation)
        # This is a simplified version - full watermark requires more complex XML
    
    def _add_header(self, doc: Document, cluster: LawCluster, analysis: ComplianceAnalysis):
        """Add report header with title and metadata."""
        # Title
        title = doc.add_heading('Brubru - EU Law Comply', level=1)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title.runs[0]
        title_run.font.color.rgb = self.BRUBRU_PURPLE
        
        # Subtitle
        subtitle = doc.add_heading('Your EU Law Compliance Report', level=2)
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle_run = subtitle.runs[0]
        subtitle_run.font.color.rgb = self.BRUBRU_DARK
        
        # Metadata
        doc.add_paragraph()
        meta_table = doc.add_table(rows=4, cols=2)
        meta_table.style = 'Light Grid Accent 1'
        
        meta_table.rows[0].cells[0].text = 'Analysis Name:'
        meta_table.rows[0].cells[1].text = analysis.analysis_name or 'Unnamed Analysis'
        
        meta_table.rows[1].cells[0].text = 'Law Cluster:'
        meta_table.rows[1].cells[1].text = cluster.name
        
        meta_table.rows[2].cells[0].text = 'Policy Area:'
        meta_table.rows[2].cells[1].text = cluster.policy_area or 'N/A'
        
        meta_table.rows[3].cells[0].text = 'Report Date:'
        meta_table.rows[3].cells[1].text = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        
        doc.add_page_break()
    
    def _add_executive_summary(self, doc: Document, analysis: ComplianceAnalysis):
        """Add executive summary section."""
        doc.add_heading('Executive Summary', level=1)
        
        summary_text = f"""This report provides a comprehensive compliance analysis against the {analysis.cluster_id} 
regulatory package. A total of {analysis.total_requirements or 0} requirements were analyzed 
against your organization's documentation."""
        
        doc.add_paragraph(summary_text)
        doc.add_paragraph()
    
    def _add_compliance_score(self, doc: Document, analysis: ComplianceAnalysis):
        """Add overall compliance score with breakdown."""
        doc.add_heading('Compliance Score', level=1)
        
        # Overall score
        score_para = doc.add_paragraph()
        score_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        score_run = score_para.add_run(f'{analysis.compliance_score:.1f}%' if analysis.compliance_score else 'N/A')
        score_run.font.size = Pt(48)
        score_run.font.bold = True
        
        # Determine color based on score
        if analysis.compliance_score:
            if analysis.compliance_score >= 90:
                score_run.font.color.rgb = self.STATUS_COLORS['met']
            elif analysis.compliance_score >= 70:
                score_run.font.color.rgb = self.STATUS_COLORS['partial']
            else:
                score_run.font.color.rgb = self.STATUS_COLORS['gap']
        
        doc.add_paragraph()
        
        # Breakdown table
        breakdown_table = doc.add_table(rows=4, cols=2)
        breakdown_table.style = 'Light Grid Accent 1'
        
        breakdown_table.rows[0].cells[0].text = '✓ Requirements Met'
        breakdown_table.rows[0].cells[1].text = str(analysis.requirements_met or 0)
        
        breakdown_table.rows[1].cells[0].text = '⚠ Partial Compliance'
        breakdown_table.rows[1].cells[1].text = str(analysis.requirements_partial or 0)
        
        breakdown_table.rows[2].cells[0].text = '✗ Critical Gaps'
        breakdown_table.rows[2].cells[1].text = str(analysis.requirements_gap or 0)
        
        breakdown_table.rows[3].cells[0].text = 'Total Requirements'
        breakdown_table.rows[3].cells[1].text = str(analysis.total_requirements or 0)
        
        doc.add_page_break()
    
    def _add_gap_findings(self, doc: Document, findings):
        """Add detailed gap findings section."""
        doc.add_heading('Gap Findings', level=1)
        
        # Group by status
        gaps = [f for f, req, law in findings if f[0].status == 'gap']
        partials = [f for f, req, law in findings if f[0].status == 'partial']
        
        # Critical gaps
        if gaps:
            doc.add_heading('Critical Gaps', level=2)
            for finding, requirement, law in gaps:
                self._add_finding_detail(doc, finding, requirement, law)
        
        # Partial compliance
        if partials:
            doc.add_heading('Partial Compliance', level=2)
            for finding, requirement, law in partials:
                self._add_finding_detail(doc, finding, requirement, law)
        
        if not gaps and not partials:
            doc.add_paragraph('✓ Excellent! No critical gaps or partial compliance issues identified.')
    
    def _add_finding_detail(self, doc: Document, finding, requirement, law):
        """Add details for a single finding."""
        # Article and requirement
        heading = doc.add_heading(f'{requirement.article} - {law.title[:100]}', level=3)
        
        # Priority badge
        priority_para = doc.add_paragraph()
        priority_run = priority_para.add_run(f'Priority: {finding.priority}/5')
        priority_run.bold = True
        
        if finding.priority <= 2:
            priority_run.font.color.rgb = self.STATUS_COLORS['gap']
        elif finding.priority <= 3:
            priority_run.font.color.rgb = self.STATUS_COLORS['partial']
        
        # Requirement text
        doc.add_paragraph(f'Requirement: {requirement.requirement_text}')
        
        # Gap description
        if finding.gap_description:
            gap_para = doc.add_paragraph()
            gap_run = gap_para.add_run(f'Gap: {finding.gap_description}')
            gap_run.italic = True
        
        # Recommendation
        if finding.recommendation:
            rec_para = doc.add_paragraph()
            rec_run = rec_para.add_run(f'Recommendation: {finding.recommendation}')
            rec_run.bold = True
        
        # Effort estimate
        if finding.estimated_effort:
            doc.add_paragraph(f'Estimated Effort: {finding.estimated_effort.title()}')
        
        doc.add_paragraph()  # Spacing
    
    def _add_action_plan(self, doc: Document, findings):
        """Add action plan timeline."""
        doc.add_page_break()
        doc.add_heading('Action Plan', level=1)
        
        # Filter gaps and partials, sort by priority
        action_items = [
            (finding, requirement, law)
            for finding, requirement, law in findings
            if finding.status in ['gap', 'partial']
        ]
        
        if not action_items:
            doc.add_paragraph('✓ No action items required. All requirements are met!')
            return
        
        # Group by priority
        for priority in range(1, 6):
            priority_items = [
                (f, r, l) for f, r, l in action_items if f.priority == priority
            ]
            
            if priority_items:
                priority_labels = {1: 'Critical', 2: 'High', 3: 'Medium', 4: 'Low', 5: 'Optional'}
                doc.add_heading(f'{priority_labels[priority]} Priority Actions', level=2)
                
                for finding, requirement, law in priority_items:
                    # Action item
                    para = doc.add_paragraph(style='List Bullet')
                    para.add_run(f'{requirement.article}: ').bold = True
                    para.add_run(finding.recommendation or 'Address compliance gap')
                    
                    # Deadline if available
                    if requirement.deadline:
                        deadline_para = doc.add_paragraph(style='List Bullet 2')
                        deadline_para.add_run(f'  Deadline: {requirement.deadline.strftime("%Y-%m-%d")}')
    
    def _add_footer(self, doc: Document):
        """Add report footer."""
        doc.add_page_break()
        
        footer_para = doc.add_paragraph()
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        footer_run = footer_para.add_run('Generated by Brubru - EU Law Comply')
        footer_run.italic = True
        footer_run.font.size = Pt(10)
        footer_run.font.color.rgb = RGBColor(100, 100, 100)
        
        date_para = doc.add_paragraph()
        date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        date_run = date_para.add_run(datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'))
        date_run.font.size = Pt(9)
        date_run.font.color.rgb = RGBColor(150, 150, 150)
