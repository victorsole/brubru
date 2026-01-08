"""
Knowledge Base Module

Internal knowledge base for Brubru:
- Calendars (EP 2025/2026)
- Institutions (Commissioners, DGs, Committees, PermReps)
- Templates (Briefing notes, position papers, etc.)
- Guides (EU jargon, resources, working with APAs, monitoring tips, etc.)
- EC Organigrammes (Commission personnel by DG)
- Analytics (EU law snapshots)
"""

from .knowledge_loader import KnowledgeLoader, get_knowledge_loader

__all__ = ['KnowledgeLoader', 'get_knowledge_loader']
