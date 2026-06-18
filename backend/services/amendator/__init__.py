"""
Amendator Services

AI-powered amendment generation and analysis on the shared free open-model
chain (MultiProviderService). The former Anthropic-only AIAmendmentGenerator
was removed on 18 June 2026; its justify/analyse capabilities live on as the
/api/amendments/justify and /api/amendments/analyse-article endpoints, and its
suggestion logic is implemented inline in api/amendments.py.

Components:
- amendment_validation: deterministic fidelity checks on AI output
- drafting_context: definitions / cross-references / recitals injected into prompts
- alignment_scorer: score MEP amendments against a user's policy position
- comparison_analyzer: ally / coverage-gap analysis (heuristic, no AI)
- amendment_export_service: DOCX export
- amendment_linker: auto-link amendments to tracked carriages
"""
