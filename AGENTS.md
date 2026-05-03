# Yeedem Books - Agent Standing Orders

## Core Philosophy (Data-Lite approach)
1. **Always optimize for 3G speeds.** The primary users are MSMEs in Nigeria where mobile internet can be intermittent and slow.
2. **Never use heavy JavaScript libraries.** Avoid React, Vue, or Angular unless strictly necessary. Rely exclusively on HTMX and HTML fragments to update the UI without full page reloads.
3. **Prioritize Fluid Compute.** PDF generation (e.g. `fpdf2`) can be memory-heavy. Always ensure `vercel.json` configurations allocate enough processing time/memory for these endpoints.
4. **Vercel Zero-Config.** Maintain a standard Django project structure. Vercel natively supports this, so do not create `/api` folder structures unless explicitly required by a standalone function.
5. **Zero-Touch Compliance.** Ensure FIRS 2026 data standards (TIN, 7.5% VAT, sequential INV-2026-XXXX numbering, NRS clearance status) are meticulously tracked in the database and surfaced correctly in PDF/Web UI.
