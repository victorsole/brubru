# Funding template JSON schema

Each `*.json` in this directory describes ONE (programme × sub_instrument × stage) template. Shipped in git, loaded by `api/tender_templates.py` and served via `GET /api/tender-templates/{id}`. The frontend uses them to drive the section outline + AI co-writer.

## Required top-level keys

| Key | Type | Purpose |
|---|---|---|
| `id` | string | Stable identifier — used as `template_id` on `tender_files`. e.g. `eic-accelerator-stage-1` |
| `name` | string | Human-readable title |
| `programme` | string | `EIC`, `HE`, `CEF`, `LIFE`, `EDF`, etc. |
| `sub_instrument` | string \| null | `accelerator`, `pathfinder-open`, `pathfinder-challenges`, `transition`, `step`, `aic`, `pre-accelerator`, `prize` |
| `stage` | string \| null | `stage-1`, `stage-2`, `single-stage`, `interview` |
| `scaffold_version` | string | EU template version e.g. `2.0-22.10.2025` |
| `official_template_url` | string | Canonical EU URL the user could also download |
| `kb_guide` | string | Filename (without `.md`) of the related Brubru KB guide |
| `documents` | array | Documents the user must produce — each with section structure |
| `comply_targets` | array | Default `policy_area` names to surface in the right-rail Comply panel |
| `hand_offs` | object | Chat/Comply/next-stage CTAs |

## Document object

```jsonc
{
  "kind": "tender_application_short",            // matches FUNDING_DOC_KINDS in document_kinds.ts
  "title": "Part B — Short Proposal",
  "page_limit": 12,                              // null if no limit
  "formatting": {
    "font": "Times New Roman 11pt min",
    "page_size": "A4",
    "margins_mm": 15
  },
  "render": "ai-narrative",                      // 'ai-narrative' | 'external-upload-or-link' | 'scaffold-only' | 'cv-list' | 'table-driven'
  "constraints": { ... },                        // free-form per render
  "sections": [
    {
      "id": "1-technology",
      "label": "1. Technology",
      "page_budget": 4,
      "criterion": "Excellence",                 // 'Excellence' | 'Impact' | 'Implementation' | null
      "sub": [
        {
          "id": "1.1",
          "label": "1.1 Novelty and breakthrough nature",
          "prompts": [
            "Is your innovation deep tech in nature?",
            "Does it represent a significant improvement in cost or performance vs existing solutions?"
          ],
          "conditional": null                    // or {"funding_mode": ["blended", "equity-only"]}
        }
      ]
    }
  ],
  "ai_disclosure_required": true                 // appends the mandatory generative-AI disclosure on export
}
```

## comply_targets

Each item is a `policy_area` string that matches the `policy_area` column on `law_clusters` in EU Law Comply. The endpoint `/api/eu-law-comply/clusters/by-topic` returns the clusters whose `policy_area IN comply_targets`, plus optionally any extras driven by `ethics_flags` in the user's draft.

Recommended starter sets:

| Programme/sub | Default policy_areas |
|---|---|
| EIC Accelerator (AI/Robotics) | "AI", "GDPR", "Cybersecurity", "Product Safety" |
| EIC Pathfinder (Health) | "Medical Devices", "Clinical Trials", "GDPR" |
| LIFE / Innovation Fund | "Environment", "Energy", "CSRD" |
| EDF / dual-use | "Defence", "Dual-Use", "Cybersecurity" |
| Erasmus+ / CERV | "Education", "Fundamental Rights" |

## hand_offs

```jsonc
{
  "next_stage": "eic-accelerator-stage-2",    // template_id for the next stage; null if terminal
  "chat_cta": "Ask Brubru for help with the Excellence section",
  "comply_cta": "Run EU Law Comply on this proposal"
}
```

## Versioning

When the EU template updates annually:
1. Bump `scaffold_version`.
2. Existing `tender_files` rows keep their original `scaffold_version` until the user manually re-pins.
3. The frontend shows a green disclaimer chip when `tender_file.scaffold_version` != latest JSON.
