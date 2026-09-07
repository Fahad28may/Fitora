# Privacy Policy (Draft)

> **Draft — requires professional legal review before production use.** This document must describe what Fitora actually does; update it whenever data handling changes, and never state a claim here that isn't true of the running system.

## 1. Who we are

Fitora is a personal fitness and nutrition application. This policy explains what data we collect, why, and what your rights are.

## 2. Data we collect

See [`data-flow.md`](data-flow.md) for the authoritative, kept-current data inventory. In summary:

- Account data: email, password (hashed — we never see or store your plaintext password).
- Profile data you provide: age, height, sex, activity level, goals — used only to calculate calorie/macro estimates.
- Data you log: food diary entries, workouts, weight, measurements, water intake, and — if you choose — progress photos.
- Optional content: natural-language food descriptions and food photos, used to help log food.
- Technical data: session/device information needed for authentication and security (see `data-flow.md`).

## 3. Why we collect it

Data minimization is a core rule: if a piece of data isn't needed for a specific feature you use, we don't collect it. Every data type in `data-flow.md` has a stated purpose.

## 4. AI processing

Some features (natural-language food logging, the AI coach, optional photo food recognition) send a minimum-necessary subset of your data to an AI provider to generate a response. We never send your email, full name, password, authentication tokens, or payment information to an AI provider. Full detail: [`ai-safety.md`](ai-safety.md).

## 4a. Camera and barcode scanning

If you use barcode scanning, the app asks for camera permission. The camera is used only to read the barcode: frames are decoded on your device, no image is recorded, and no image is ever uploaded. The only thing that leaves your phone is the barcode number itself, which the server sends to the food database provider to look up the product. That request carries no account identifier — see [`third-party-services.md`](third-party-services.md).

Barcode lookup is optional. If the server operator has not configured a food database provider, scanning is unavailable and no barcode is ever sent anywhere.

## 5. Third-party providers

Listed, with what they receive and why, in [`third-party-services.md`](third-party-services.md). We review each provider's data-processing terms before integrating them.

## 6. Data retention

Data is retained while your account is active. On account deletion, your data is deleted or anonymized per the process in [`data-flow.md`](data-flow.md#account-deletion-flow). Backups persist for a defined rotation window after deletion — see the same document.

## 7. Data deletion & export

`Settings → Privacy` lets you export your data (machine-readable) or delete your account. See [`data-flow.md`](data-flow.md) for exactly what happens.

## 8. Security

See [`SECURITY.md`](../SECURITY.md) and [`security-threat-model.md`](security-threat-model.md).

## 9. Cookies / tracking

Fitora's mobile client does not use browser cookies. If/when a web client or analytics provider is added, this section will be updated to reflect exactly what's used and why, before it ships.

## 10. Children's privacy

Fitora is designed for adult users (18+) in its initial version and is not knowingly directed at children. We do not knowingly collect data from users under 18.

## 11. International data transfers

Depending on where our infrastructure and providers are located, your data may be processed outside your country of residence. This section will name specific countries/mechanisms once infrastructure and providers are finalized — see [`compliance-checklist.md`](compliance-checklist.md).

## 12. Your rights

Depending on your jurisdiction, you may have rights to access, correct, export, delete, or restrict processing of your data, and to withdraw consent. See [`compliance-checklist.md`](compliance-checklist.md) for jurisdiction-specific tracking. To exercise these rights, use in-app settings or contact us (see §13).

## 13. Contact

[Contact information to be added before production launch.]

## 14. Changes to this policy

We'll update this document as Fitora's data practices change, and note the effective date of the current version. Material changes affecting how we use your data will be communicated in-app.

---

*Effective date: not yet published — pre-launch draft.*
