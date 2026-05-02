"""
Brubru discovery services — live retrieval helpers backed by the
EU Publications Office Cellar SPARQL endpoint.

Module organisation:
    cellar_helpers.py
        Feature-aware helper functions imported by:
            - api/amendator_examples.py (pre-flight discovery for example URLs)
            - api/eu_law_comply.py (sector-relevant legislation lookup)
            - api/tenderator.py (tender <-> regulation cross-reference)
            - services/ai/context_builder.py (chat on-demand block)
            - api/v1/cellar_discover.py (public REST surface)
"""
