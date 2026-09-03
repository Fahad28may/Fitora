# Compliance Checklist

> **This document does not establish legal compliance.** It tracks what has and hasn't been considered, for a qualified legal reviewer to verify before production launch. Do not represent Fitora as compliant with any of the frameworks below based on this document alone.

| Jurisdiction | Applicable regulation | Requirements (non-exhaustive) | Current implementation | Remaining gaps | Legal review required? |
|---|---|---|---|---|---|
| EU/EEA | GDPR | Lawful basis, data minimization, right to access/export/delete/rectify, DPA with processors, breach notification | Data export & account deletion designed (`data-flow.md`); data minimization applied in schema design | No DPO/DPA process yet, no processor agreements signed (no processors selected yet), no formal lawful-basis documentation | Yes |
| UK | UK GDPR | Materially similar to GDPR | Same as above | Same as above | Yes |
| US — California | CCPA/CPRA | Right to know/delete/opt-out of sale, sensitive personal information (health data) protections | Export/delete designed; no data is sold | No CCPA-specific notice yet, no "Do Not Sell/Share" flow (not currently applicable — no data sale), formal SPI handling review pending | Yes |
| US — general | FTC health-data guidance (incl. Health Breach Notification Rule considerations) | Truthful claims about data practices, breach notification for health-adjacent apps | Health disclaimer drafted (`health-disclaimer.md`); no false claims made in docs | Breach-notification process not yet formalized | Yes |
| Global | App store health-data policies (Apple/Google) | Additional disclosure/consent requirements for health-adjacent data | Not yet reviewed against current store policies | Full app-store policy review pending | Yes, before store submission |
| Other jurisdictions | Local privacy/data-protection laws | Varies | Not assessed | Not assessed | Yes, per target market |

## How this is used

- Every new feature that collects, processes, or shares personal data should be checked against this table, not just against the security threat model.
- "Current implementation" reflects what's actually built, not what's planned — keep it honest as features ship.
- Before production launch, every row needs a legal reviewer's sign-off, not just an engineering self-assessment.
