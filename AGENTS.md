# Yeedem Books - Agent Standing Orders

## Core Philosophy (Data-Lite approach)
1. **Always optimize for 3G speeds.** The primary users are MSMEs in Nigeria where mobile internet can be intermittent and slow.
2. **Never use heavy JavaScript libraries.** Avoid React, Vue, or Angular unless strictly necessary. Rely exclusively on HTMX and HTML fragments to update the UI without full page reloads.
3. **Prioritize Fluid Compute.** PDF generation (e.g. `fpdf2`) can be memory-heavy. Since we've migrated to Railway, memory limits are less restrictive, but still monitor resource usage for heavy PDF tasks.
4. **Railway First.** This project is optimized for Railway.app. Ensure the `Procfile` is maintained with necessary migration and collectstatic commands for automated deployments.
5. **Zero-Touch Compliance.** Ensure FIRS 2026 data standards (TIN, 7.5% VAT, sequential INV-2026-XXXX numbering, NRS clearance status) are meticulously tracked in the database and surfaced correctly in PDF/Web UI.
