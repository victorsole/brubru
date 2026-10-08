"""Which Commission follow-up answers which EP adopted text.

ONE definition, used by the enrichment job that stores
`ep_resolutions.has_commission_followup` and by the API that lists the follow-ups
in `key_events`, so the flag and the events cannot disagree.

Source: `ep_external_documents` (EP Open Data, work type ACT_FOLLOWUP). Its
`answers_to` is EP's metadata link, and it is wrong for about 1 in 10 recent
documents (measured 8 Oct 2026: 38 of 367 since July 2024): it holds the committee
REPORT's number typed as an adopted-text id. SP-2026-05-26-TA-10-2026-0270 says it
answers TA-10-2026-0270 (the 28th tax regime resolution, adopted 9 July 2026, six
weeks AFTER the follow-up); its own text answers the drones resolution,
"References: 2025/2088(INI) / A10-0270/2025 / P10_TA(2026)0020".

So the document's own reference line ("References:" / "Reference numbers:") wins:
it names the procedure and the adopted text (stored as ref_ta / ref_procedure,
migration 280). `answers_to` is used only for a document whose text carries no
such line.
"""

# True when follow-up `f` (an ep_external_documents row) answers adopted text `t`
# (a texts_adopted row holding a P*_TA reference). ref_ta / ref_procedure are the
# document's own reference line, as generated columns (migration 280); answers_to is
# used only when the document's text carries no such line.
FOLLOWUP_MATCH = r"""(
    f.ref_ta = t.ta_reference
    OR f.ref_procedure = t.procedure_ref
    OR (f.ref_ta IS NULL AND f.ref_procedure IS NULL
        AND f.answers_to @> ARRAY[regexp_replace(t.ta_reference,
                '^P([0-9]+)_TA\(([0-9]{4})\)([0-9]{4})$', 'eli/dl/doc/TA-\1-\2-\3')])
)"""
