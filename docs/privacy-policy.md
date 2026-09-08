# Privacy Policy (Draft)

> **Draft — requires professional legal review before production use.** This document must describe what Fitora actually does; update it whenever data handling changes, and never state a claim here that isn't true of the running system.

## 1. Who we are

Fitora is a personal fitness and nutrition application. This policy explains what data we collect, why, and what your rights are.

## 2. Data we collect

See [`data-flow.md`](data-flow.md) for the authoritative, kept-current data inventory. In summary:

- Account data: email, password (hashed — we never see or store your plaintext password).
- Profile data you provide: age, height, sex, activity level, goals — used only to calculate calorie/macro estimates.
- Data you log: food diary entries, workouts, weight, measurements, water intake, activity, and — if you choose — progress photos.
- Optional content: natural-language food descriptions and food photos, used to help log food.
- Technical data: session/device information needed for authentication and security (see `data-flow.md`).

## 3. Why we collect it

Data minimization is a core rule: if a piece of data isn't needed for a specific feature you use, we don't collect it. Every data type in `data-flow.md` has a stated purpose.

## 4. AI processing

Some features (natural-language food logging, the AI coach, optional photo food recognition) send a minimum-necessary subset of your data to an AI provider to generate a response. We never send your email, full name, password, authentication tokens, or payment information to an AI provider. Full detail: [`ai-safety.md`](ai-safety.md).

## 4a. Camera and barcode scanning

If you use barcode scanning, the app asks for camera permission. The camera is used only to read the barcode: frames are decoded on your device, no image is recorded, and no image is ever uploaded. The only thing that leaves your phone is the barcode number itself, which the server sends to the food database provider to look up the product. That request carries no account identifier — see [`third-party-services.md`](third-party-services.md).

Barcode lookup is optional. If the server operator has not configured a food database provider, scanning is unavailable and no barcode is ever sent anywhere.

## 4b. Food photos

If you use photo food recognition, the photo you choose is uploaded, sent to the AI provider for identification, and then discarded. It is **not** saved on our servers, not attached to your account, and not used to train anything. Nothing identifying you is sent with it — the request carries the image and a fixed instruction, nothing else.

The result is an estimate, and always a range rather than an exact number. Nothing is added to your diary until you pick a food and confirm it.

Photo recognition is optional and off unless the server operator has configured a vision model. Progress photos are a separate feature with different handling — those *are* stored, in a private bucket, until you delete them (see §2).

## 4c. Activity from your phone or watch

Fitora can store activity — steps, distance, workouts, active energy — that a health app on your device reports to it. What that involves:

- **It is off unless you turn it on twice.** Once in Fitora ("Read data from wearables", in Settings → Privacy), which is you allowing us to store the data, and once in your phone's own permission dialog, which is your device agreeing to hand it over. We ask for ours first, so nobody meets a system prompt before reading what it is for. Turning the Fitora switch off stops future syncs immediately.
- **We read, we never write.** Fitora does not add anything to Apple Health or Health Connect, and does not ask for permission to.
- **Only four kinds of data.** Steps, distance, workouts and active energy. Not sleep, not heart rate, not clinical records — Fitora has no feature that uses them, so it does not ask for them.
- **It stays with us.** Device activity is stored in your account and is never sent to the AI provider, the food database, or anyone else. It is included in your data export and deleted with your account.
- **The data does not leave your device unaided.** Reading a health app requires a build of Fitora that includes the necessary components. If your build does not have them, Settings says so plainly and no activity is read from any device.

Activity you type in yourself is ordinary logged data and always has been; entries record whether they were typed or reported by a device, and the app shows which is which.

## 5. Third-party providers

Listed, with what they receive and why, in [`third-party-services.md`](third-party-services.md). We review each provider's data-processing terms before integrating them.

## 6. Data retention

Data is retained while your account is active. On account deletion, your data is deleted or anonymized per the process in [`data-flow.md`](data-flow.md#account-deletion-flow).

Backups: Fitora does not currently run automated backups. The intended design — including how long backups would retain data after you delete your account — is in [`backups-and-recovery.md`](backups-and-recovery.md). When backups are implemented, deleted data will persist in them for the retention window stated there, and this section will be updated to say so. We would rather tell you this than imply a safety net that does not exist.

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
