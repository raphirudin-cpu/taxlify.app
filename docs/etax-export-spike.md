# eTax Export — Research Spike

_Status: research complete · Date: 2026-08-13 · Owner: Taxlify_

**Question:** Can Taxlify export a client's tax data so it can be filed with / imported
into official Swiss cantonal tax software — and what would it take?

---

## TL;DR / Recommendation

Switzerland has **no single federal e-filing portal**. Each of the 26 cantons runs its
own tax software and submission channel. But two **national standards** matter:

- **eCH-0196 — `E-Steuerauszug`** (bank securities statement). A PDF with embedded
  structured data + 2D barcode. **Accepted by all cantons since 2023.** This is an
  *input* to a return (pre-fills the Wertschriftenverzeichnis).
- **eCH-0119 — `E-Tax Filing`** (v4.0.0, 2021). The XML exchange format for a *complete*
  natural-person return (cantonal + direct federal tax). This is what professional
  software (Dr. Tax, Abacus) uses to move/submit returns.

**Recommendation — do the cheap, high-value half first, defer the expensive half:**

1. **Phase E1 — Import `eCH-0196` (recommended, small):** let advisors/clients drop the
   bank's `eSteuerauszug` PDF; Taxlify parses the embedded XML to auto-fill securities and
   investment income. Standards-based, well-specified, immediately useful, and a natural
   sibling to the Phase D3 AI intake. **This is the spike's concrete "yes, build this".**
2. **Phase E2 — Export for professional software (medium):** emit a structured file the
   advisor's existing tool (Dr. Tax / Abacus) can import, so Taxlify feeds the filing tool
   rather than replacing it. Positions Taxlify as the intake/prep layer.
3. **Phase E3 — Generate `eCH-0119` and/or submit to cantons (large, defer):** a real,
   multi-canton engineering + compliance project. Scope to **one pilot canton** if pursued.

Full cantonal e-submission (E3, the "file it for the client" dream) is **not spike-sized**
and is realistically the domain of established vendors. E1 delivers most of the practical
value for a fraction of the cost.

---

## The landscape

- **26 cantons, 26 systems.** Filing is cantonal. Each canton ships its own software —
  e.g. Zürich `ZHprivateTax`, Zug `eTax`, and the commercial multi-canton `eTax`/`Dr. Tax`
  family. There is no uniform national submission API.
- **Fully-digital filing exists** (no paper, no signature) in supporting cantons — but the
  *how* is per-canton (online portal, upload, or the 2D-barcode print workflow).
- **Market reality:** ~40% of all Swiss returns run through the `eTax` + `Dr. Tax` systems,
  used by 5,000+ Treuhand firms. Professional filing tools already own this pipe.
- **The 2D barcode** (Datamatrix on the return PDF) is the lowest-common-denominator
  mechanism: cantonal software prints the full return into a barcode the canton scans, and
  it's also how prior-year data is carried over between tools.

## The standards that matter

### eCH-0196 — `E-Steuerauszug` (securities statement) — **INPUT**
- Jointly developed by cantonal tax administrations, the federal tax administration (ESTV),
  and the banks. Current version 2.2.0.
- Delivered as a **PDF carrying structured data + a 2D barcode**; the taxpayer uploads it
  into cantonal software and the positions/income land in the Wertschriftenverzeichnis
  automatically — no manual entry, fewer errors.
- **Issued by banks/brokers** (Swissquote, PostFinance, Saxo, Yuh, …), often for a fee.
  Taxlify **cannot issue** one (that requires being a registered data provider), but
  **parsing one is unrestricted** — the standard is public.
- **Relevance to Taxlify:** this is the single highest-leverage, lowest-risk integration.
  Clients already receive these from their bank; parsing them auto-populates the most
  tedious part of the return.

### eCH-0119 — `E-Tax Filing` (full return) — **OUTPUT**
- The XML **exchange format for the declaration data of a natural person**, for cantonal
  *and* direct federal tax, based on the Swiss Tax Conference (SSK) model forms. v4.0.0
  (approved 2021-03-08).
- Defines packaging (**XML + attachments + a visualization of the XML**), transport, and
  encryption — i.e. a whole submission envelope, not just field data.
- Championed by **`allianz e-tax schweiz`** (a cross-industry alliance incl. EXPERTsuisse)
  pushing to unify interfaces/formats across cantons; standard is maintained by the eCH
  association.
- **Relevance to Taxlify:** this is the "export a fileable return" path — but generating a
  *canton-accepted* eCH-0119 package requires complete per-canton form-field mapping, the
  XML-visualization requirement, and a submission channel the canton actually accepts. It's
  the expensive half.

---

## Options for Taxlify (effort × value)

| # | Option | What we build | Effort | Value | Verdict |
|---|--------|---------------|--------|-------|---------|
| **E1** | **Import eCH-0196** | Parse the bank `eSteuerauszug` PDF/XML → prefill securities & income | **Low–Med** | **High** | **Do first** |
| E2 | Export for pro software | Emit a file Dr. Tax / Abacus can import | High* | Med–High | Merges into E3 (see below) |
| E3 | Generate eCH-0119 | Build a valid v4 package for ≥1 canton | High | Med | Pilot-only, defer |
| E4 | Direct e-submission to cantons | Per-canton portal/Sedex onboarding + legal | Very High | High | Out of scope now |

**Why E1 wins the spike:** it's a bounded parsing task against a **public, versioned,
nationally-accepted** standard; the input already exists in every client's mailbox; and it
compounds with the AI intake (structured extraction where a barcode exists, AI where it
doesn't). E3/E4 are where "reimplement cantonal filing" costs live, with acceptance gated
canton-by-canton — that's a company-scale bet, not a feature.

### *E2 caveat — "a file that feeds Dr. Tax" is really eCH-0119

There is **no public third-party import API for Dr. Tax** (made by Ringler Informatik AG).
Its documented import/export is a *round-trip* (export a return to a file, re-import it into
Dr. Tax) plus import from **cantonal solutions** and prior-year **barcode PDFs**; DMS
interfaces (Kendox, Therefore) and third-party submission are "in preparation." The only
machine-readable format a professional tool or canton actually ingests from outside is the
national **eCH-0119** XML.

**Consequence:** "export a file that feeds Dr. Tax" ≈ "produce valid eCH-0119" ≈ the E3
build. There is **no cheap proprietary shortcut** to target today. Two real paths to feed
Dr. Tax specifically:
1. **Produce eCH-0119** (= E3 effort), then rely on Dr. Tax importing it; or
2. **Partner directly with Ringler** for a bespoke interface — a business-development move,
   not something we can build against unilaterally.

So E2, as "a small mapping job," does **not** exist independently. Fold it into E3 and treat
"feed Dr. Tax" as a partnership question.

---

## Proposed phased plan (if we proceed)

- **E1a — eCH-0196 reader (MVP).** Detect an `eSteuerauszug` on upload, extract the embedded
  XML, map positions → a `SecuritiesStatement` model, show a review table on the client/
  advisor side. Reuse the Phase D3 document surface.
- **E1b — Wertschriften prefill.** Feed parsed positions into the checklist / return-prep
  data so the advisor starts from a filled securities list.
- **E2 — Pro-software export.** Reframed: there's no cheap proprietary import into Dr. Tax
  (see the E2 caveat) — the interchange file *is* eCH-0119, so E2 collapses into E3. If
  feeding Dr. Tax specifically is a goal, open a conversation with **Ringler Informatik AG**
  about an interface rather than building blind.
- **E3 (optional, later) — eCH-0119 pilot.** Choose **one** canton, map its SSK forms,
  produce a validating v4 package, and test the real acceptance channel end-to-end before
  generalizing.

---

## Open questions to resolve before E2/E3

1. **Which filing tool do our advisors use** — Dr. Tax, Abacus, cantonal-native? (Decides E2
   format; ask the design-partner firms.)
2. **eCH-0196 embedding mechanics** — confirm whether the structured payload is a PDF/A-3
   embedded XML file vs. barcode-only, and get the exact v2.2.0 schema from ech.ch before
   estimating E1 precisely.
3. **eCH-0119 acceptance per canton** — for a pilot, which canton offers a documented
   third-party submission channel (upload/portal/Sedex) vs. barcode-only?
4. **Legal/registration** — issuing (not parsing) eCH-0196, or submitting eCH-0119, may
   require SSK/canton registration; confirm before any E3/E4 commitment.

---

## Sources

- [eCH-0119 E-Tax Filing v4.0.0 (standard page)](https://www.ech.ch/de/ech/ech-0119/4.0.0)
- [eCH-0119 E-Tax Filing v4.0.0 (PDF)](https://www.ech.ch/sites/default/files/dosvers/hauptdokument/STAN_d_DEF_2021-03-08_eCH-0119_V4.0.0_E-Tax%20Filing_1.pdf)
- [eCH-0196 E-Steuerauszug v2.2.0 (standard page)](https://www.ech.ch/de/ech/ech-0196/2.2.0)
- [eCH-0196 E-Steuerauszug — Technische Wegleitung 2.0 (PDF)](https://www.ech.ch/sites/default/files/imce/eCH-Dossier/0181-0210/eCH-0196/2.0/Beilagen/eCH-0196%20E-Steuerauszug_Technische%20Wegleitung%202.0.pdf)
- [SSK / Schweizerische Steuerkonferenz — eSteuerauszug](https://www.ssk-csi.ch/de/links/esteuerauszug)
- [allianz e-tax schweiz — Hintergrund](https://allianz-e-tax-schweiz.ch/hintergrund/)
- [allianz e-tax schweiz — EXPERTsuisse](https://expertsuisse.ch/de/verband/partner-und-netzwerke/initiativen/allianz-e-tax-schweiz)
- [Kanton Zürich — auf die Online-Steuererklärung umsteigen (ZHprivateTax)](https://www.zh.ch/de/steuern-finanzen/steuern/steuern-natuerliche-personen/steuererklaerung-natuerliche-personen/auf-online-steuererklaerung-umsteigen.html)
- [Dr. Tax — Import aus kantonalen Deklarationslösungen (helpdesk)](https://helpdesk.drtax.ch/hc/de/articles/20082824383772)
- [Dr. Tax — Import und Export (helpdesk)](https://helpdesk.drtax.ch/hc/de/articles/115005046905-Import-und-Export)
- [Ringler Informatik AG (maker of Dr. Tax)](https://www.ringler.ch/)
- [investblog.ch — eSteuerauszug erklärt](https://investblog.ch/esteuerauszug-steuererklaerung-wertschriften/)
