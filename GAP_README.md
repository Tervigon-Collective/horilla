# Horilla HRMS — Gap Analysis vs Industry (Keka, greytHR, Zoho People)

**Deployment:** Tervigon / Seleric — `hrms.seleric.com`  
**Source:** `/var/jenkins_apps/horilla-src/`  
**Last updated:** 24 August 2026  
**Purpose:** Track what Horilla has today, what is partial, and what is missing compared to leading Indian HRMS products.

---

## Executive summary

Horilla is a capable **open-source HRMS foundation** with solid web UI across core modules (employee, attendance, leave, payroll, recruitment, onboarding/offboarding, PMS, assets, helpdesk, projects, reports). It covers roughly **65–75% of a basic HRMS** after the Aug 2026 Tervigon compliance sprint.

The largest **remaining** gaps vs Keka / greytHR / Zoho People:

| Gap area | Severity | Status (Aug 2026) |
|----------|----------|-------------------|
| Indian statutory payroll (PF, ESI, PT, TDS, Form 16) | Critical | **Partial — engine, challans, Form 24Q CSV, TRACES text files live** |
| Attendance → payroll LOP | Critical | **Done** |
| Leave accrual, sandwich, balance hold | High | **Done — FIFO + reservation + accrual + sandwich** |
| Unified approvals + mobile API parity | High | **Done — web inbox + mobile inbox/actions** |
| Expense / travel, F&F settlement, LMS | Medium | **Partial — travel expense + F&F workflow; LMS not started** |

---

## Aug 2026 delivery log (Tervigon / Seleric)

### Indian statutory payroll — **partial, enabled in prod**

| Component | Status | Path |
|-----------|--------|------|
| PF / ESI / PT / TDS calculation engine | ✅ Live | `payroll/methods/india_statutory.py` |
| Company settings + employee statutory profile | ✅ Live | `payroll/models/india_statutory.py`, `payroll/views/india_statutory_views.py` |
| Payslip integration (pretax + TDS + employer lines) | ✅ Live | `payroll/views/component_views.py` |
| Form 16 Part B summary + PDF + list UI | ✅ Live | `payroll/templates/payroll/india_statutory/` |
| Statutory challan CSV export (PF/ESI/PT/TDS) | ✅ Live Aug 22 | `/payroll/india-statutory/challans/` |
| PF EPS/EDLI split + PF/ESI/PT registers | ✅ Live Aug 24 | `calculate_pf()`, `/payroll/india-statutory/registers/` |
| Form 24Q quarterly TDS CSV export | ✅ Live Aug 22 | `/payroll/india-statutory/form24q/` |
| Excel import/export hub (profiles, CTC, Form 16 bulk save) | ✅ Live Aug 22 | `/payroll/india-statutory/excel/` |
| Approval inbox + F&F Excel/CSV export | ✅ Live Aug 22 | `/approvals/inbox/export/`, Excel hub |
| Per-employee PT state from work location | ✅ Live Aug 22 | `resolve_pt_state()` in `india_statutory.py` |
| Sidebar, dashboard panel, employee contract links | ✅ Live | `payroll/sidebar.py`, `payroll/dashboard.py`, `employee/templates/tabs/contract-tab.html` |
| Migrations + Tervigon enable (PT = Delhi) | ✅ Applied | `payroll/migrations/0008`–`0011` |
| TRACES 24Q + OLTAS challan text files | ✅ Live Aug 24 | `/payroll/india-statutory/traces/` |
| WhatsApp payslip/leave notifications | ✅ Live Aug 24 | `whatsapp/views.py` receiver on `notify.send(...)` |
| LWF + Bonus Act + Gratuity | ✅ Live Aug 24 | Registers + F&F; LWF/Bonus opt-in on Settings |
| Salary revision increment letters | ✅ Live Aug 24 | `/payroll/salary-revisions/`, CTC wizard PDF |
| Arrears pay-out + salary hold/release | ✅ Live Aug 24 | `/payroll/salary-holds/`; one-time allowance from revision letter |
| Full & Final settlement workflow | ✅ Live Aug 24 | `/offboarding/fnf-settlements/` draft → confirm (salary hold) → paid + PDF |
| Grade / position leave accrual rules | ✅ Live Aug 24 | `job_grade` on work info + leave type accrual rules; service-duration eligibility |
| Unit tests (calc only) | ✅ | `payroll/tests/test_india_statutory.py` |

**Not yet compliance-grade:**

- EPS/EDLI split, employer registers → **EPS/EDLI live; PF/ESI/PT registers live**
- ~~TRACES e-filing~~ ✅ TRACES 24Q text + OLTAS challan text `/payroll/india-statutory/traces/`
- ~~LWF, gratuity, bonus act~~ ✅ LWF on payslip (opt-in) + Bonus Act provision + Gratuity register / F&F
- ~~Statutory compliance registers (beyond CSV exports)~~ ✅ PF/ESI/PT registers + CSV/Excel
- **Regenerate existing payslips** after enable to populate PF/TDS in Form 16 — use `python manage.py regenerate_payslips_statutory --company 1`

**URLs:**

- Settings: `/payroll/india-statutory/settings/`
- Form 16 list: `/payroll/india-statutory/form16/`
- Challan CSV: `/payroll/india-statutory/challans/`
- Statutory registers: `/payroll/india-statutory/registers/`
- Form 24Q: `/payroll/india-statutory/form24q/`
- Accounting export: `/payroll/india-statutory/accounting-export/`
- Excel hub (import/export): `/payroll/india-statutory/excel/`
- Approval inbox export: `/approvals/inbox/export/`

### Leave — FIFO + balance reservation

| Component | Status | Path |
|-----------|--------|------|
| Central FIFO deduction / restore | ✅ | `leave/services.py` |
| `reserved_*` fields on submit | ✅ | `leave/migrations/0008`, `leave/models.py` |
| Web approve + API bulk approve | ✅ | `leave/views.py`, `horilla_api/api_views/leave/views.py` |
| Compensatory leave deduction | ✅ FIFO Aug 22 | `leave/models.py` |
| Monthly accrual + sandwich policy | ✅ Live Aug 22 | `leave/services.py`, `leave/migrations/0009` |
| Allocation reject paths | ✅ Aug 22 | `leave/views.py`, API leave views |

### Attendance + payroll wiring

| Fix | Status | Path |
|-----|--------|------|
| Attendance-linked LOP in payslip | ✅ | `payroll/methods/methods.py`, contract flag `deduct_attendance_absence_from_pay` |
| Hour balance gated on `attendance_validated` | ✅ | `attendance/models.py` |
| Clock-out targets open punch | ✅ | `attendance/views/clock_in_out.py` |
| OT order: minimum hours before OT | ✅ | `attendance/models.py` |

### Payroll scoping + UI

| Fix | Status | Path |
|-----|--------|------|
| Modern dashboard JSON APIs scoped | ✅ | `payroll/dashboard.py`, `payroll/cbv/accessibility.py` |
| Legacy chart/export endpoints scoped | ✅ Aug 22 | `payroll/views/views.py` |
| Company filter on payslip queryset | ✅ Aug 22 | `payroll/cbv/accessibility.py` |
| India statutory UI (theme-compatible tables) | ✅ Aug 22 | `payroll/templates/payroll/india_statutory/` |
| Skip US tax when India TDS enabled | ✅ Aug 22 | `payroll/views/component_views.py` |

---

## What Horilla has today

### Installed apps (production)

Core: `employee`, `attendance`, `leave`, `payroll`, `recruitment`, `onboarding`, `offboarding`, `pms`, `asset`, `helpdesk`, `project`, `report`, `biometric`, `horilla_api`, `horilla_automations`, `whatsapp`, `horilla_ldap`, `horilla_meet`, `horilla_backup`, and platform apps (`base`, `horilla_views`, `horilla_theme`, etc.).

**Runtime add-ons** (via `horilla_api`): `geofencing`, `facedetection`.

### Module capability snapshot (updated)

| Module | Present (web) | Partial | Absent |
|--------|---------------|---------|--------|
| **Employee** | CRUD, org chart, import/export, documents, disciplinary, statutory profile link | Field masking, probation workflow | Skills matrix, workforce planning |
| **Attendance** | Punch in/out, shifts, roster, monthly summary, missing punch flags, OT, hour balance, biometric hooks | Geo/face (API-first), regularization pipeline | OT approval before payroll |
| **Leave** | Types, half-day, CF, multi-approval, comp-off, restrictions, **FIFO + reservation + accrual + sandwich**, encashment pipeline | Grade-based accrual rules | Advanced policy engine |
| **Payroll** | Contracts, allowances/deductions, payslip PDF, loans, reimbursement, **India statutory (PF/ESI/PT/TDS/Form16/challans/24Q/TRACES)**, **CTC wizard**, **accounting export**, **WhatsApp payslip notifications** | US-style tax coexists | Salary revision letters |
| **Recruitment** | Pipeline, stages, LinkedIn, offer status, surveys | — | Naukri/Indeed, resume AI, career portal, e-sign |
| **Onboarding / Offboarding** | Stages, tasks, resignation flow, **F&F workflow** | IT/asset return still manual | — |
| **PMS** | OKRs, key results, feedback, meetings | 360° not full cycle | Calibration, LMS, comp-linked increments |
| **Expense** | Reimbursement, encashment, **travel expense type** | Policy limits, mileage | OCR, full travel module |
| **Reports** | Pivot reports (attendance, leave, payroll, etc.) | No API | Statutory registers, scheduled delivery |
| **Mobile / API** | JWT API, monthly summary, payslip scoping, **pending approvals inbox + actions (web + mobile)** | — | LMS |

---

## Gaps by module (vs Keka / greytHR / Zoho)

### 1. Indian payroll & compliance

| Feature | Keka / greytHR / Zoho | Horilla (Aug 2026) |
|---------|----------------------|---------------------|
| PF (EPF/EPS/EDLI) + challan | ✅ | ✅ Calc + EPS/EDLI split + challan/register CSV + OLTAS text |
| ESI + challan | ✅ | ⚠️ ESI calc + challan CSV |
| Professional Tax (state-wise) | ✅ | ✅ Per-employee PT via `resolve_pt_state()` |
| TDS (old + new regime), Form 16, 24Q | ✅ | ✅ TDS + Form 16 Part B + 24Q CSV + **TRACES text file** |
| LWF, gratuity, bonus act | ✅ | ✅ LWF (state table, opt-in) + Bonus Act provision + Gratuity Act F&F/register |
| Full & Final settlement | ✅ | ✅ Draft → confirm (holds salary) → paid + PDF `/offboarding/fnf-settlements/` |
| CTC structure (Basic/HRA/Special) | ✅ | ✅ CTC wizard on contract |
| Salary revision / increment letters | ✅ | ✅ CTC wizard + PDF letter `/payroll/salary-revisions/` |
| Arrears, hold/release salary | ✅ | ✅ Hold blocks payslip gen `/payroll/salary-holds/`; arrears → one-time allowance |
| Tally / Zoho Books integration | ✅ | ⚠️ Accounting journal CSV export |
| Multi-entity payroll | ✅ | ⚠️ Company scoping improved; not everywhere |

### 2. Attendance & time

| Feature | Industry | Horilla |
|---------|----------|---------|
| Attendance-linked LOP in payroll | ✅ | ✅ Validated absent working days |
| Sandwich leave | ✅ | ✅ `sandwich_policy` on leave type |
| Effective shift at punch (rotation) | ✅ | ⚠️ Static `shift_id` on employee |
| OT approval → payroll | ✅ | ⚠️ OT allowance on approved OT; no separate approval queue |
| Break / multi-punch rules | ✅ | ❌ |
| Facial recognition | ✅ (Keka) | ⚠️ Optional API app |
| Missing punch → regularization workflow | ✅ | ⚠️ Flags only |
| Web = mobile punch rules | ✅ | ⚠️ API gaps |
| Monthly summary on mobile | ✅ | ✅ `/api/attendance/monthly-summary/` |

### 3. Leave management

| Feature | Industry | Horilla |
|---------|----------|---------|
| Monthly accrual by DOJ/grade | ✅ | ✅ Monthly accrual + DOJ pro-rata + **grade/position accrual rules** |
| Balance hold while pending | ✅ | ✅ `reserved_*` on submit |
| Unified FIFO deduction | ✅ | All main paths including comp-off + allocation reject |
| Carry forward expiry | ✅ | ✅ Fixed Aug 24 — CF-only expiry; available_days preserved |
| Leave encashment in payroll run | ✅ | ✅ Reimbursement type + FIFO deduct/restore on approve/reject |
| Half-day consistent | ✅ | ⚠️ Partially fixed Aug 2026 |

### 4–10. Other modules

*(Employee lifecycle, ATS, PMS, expense, approvals, reports, integrations — unchanged from prior audit; see git history for full tables.)*

---

## Bugs & fixes log

### Fixed and deployed (Aug 2026)

| Area | Fix |
|------|-----|
| Payroll | `find_half_day_leaves()`; double LOP removed; `paid_days` for daily wage |
| Payroll | `get_attendance()` conflict_dates set comparison |
| Payroll | Indian statutory engine + UI + payslip PDF integration |
| Payroll | US tax skipped when India TDS enabled (no double tax rows) |
| Payroll | Legacy dashboard charts/export + company-scoped payslip queryset |
| Payroll | Form 16 PDF template i18n; list uses HTML table (horilla_theme compatible) |
| Payroll | Settings 404 (`company_id` KeyError); PT crash on missing work state |
| Leave | Cancel restores balance; forecast date format; unlimited CF validation |
| Leave | FIFO services + balance reservation on submit |
| Leave | FIFO comp-off + allocation reject reversal | ✅ Aug 22 |
| Leave | **`leave_bulk_reject` fixed** | ✅ Aug 22 |
| API | Payslip list uses scoped + company filter | ✅ Aug 22 |
| API | Attendance monthly summary endpoint | ✅ Aug 22 `/api/attendance/monthly-summary/` |
| API | Unified pending approvals counts | ✅ Aug 22 `/api/base/pending-approvals/` |
| API | Unified pending approvals inbox + actions | ✅ Aug 22 `/api/base/pending-approvals/inbox/`, `/action/` |
| API | Tax bracket RBAC + PUT bug fix | ✅ Aug 22 |
| API | Swagger gated in production (auth required) | ✅ Aug 22 |
| Payroll | Reimbursement comment IDOR fix | ✅ Aug 22 |
| Payroll | Form 16 list bulk aggregation (no N+1) | ✅ Aug 22 |
| Payroll | `regenerate_payslips_statutory` management command | ✅ Aug 22 |
| Payroll | Legacy `view_payslip` uses company-scoped queryset | ✅ Aug 22 |
| Security | `@permission_required` restored on project export + PMS KR filter | ✅ Aug 22 |
| Attendance | Auto-validation direction; open-punch datetime; API scoping |
| Attendance | Hour balance gated on validation; OT/min-hour order; clock-out open punch |
| API | Reimbursement approve permission; payslip bulk-status; summary IDOR guard |
| API | Leave reject employee fix; geofence fail-closed |
| API | Reimbursement approve/reject uses model.save() (encashment pipeline) | ✅ Aug 22 |
| API | Unified inbox reimbursement action uses model.save() | ✅ Aug 22 |
| Leave | Approval Inbox in Leave sidebar | ✅ Aug 22 |
| Payroll | Accounting Export in payroll sidebar; CTC wizard link on contract view | ✅ Aug 22 |
| Payroll | Statutory Excel hub (profiles, CTC, Form 16 bulk, reports export) | ✅ Aug 22 |
| Payroll | Accounting / Form 24Q toolbar HTML layout fix | ✅ Aug 22 |
| Base | Approval inbox badge ID uses Employee.badge_id | ✅ Aug 22 |

### Remaining P0 (recommended next)

1. ~~Attendance → LOP~~ ✅
2. ~~Unified leave FIFO~~ ✅
3. ~~Balance reservation on submit~~ ✅
4. ~~Hour balance gated on validation~~ ✅
5. ~~Payroll export/chart scoping~~ ✅ (legacy + modern)
6. ~~Clock-out open punch~~ ✅
7. ~~OT order in Attendance.save()~~ ✅
8. **Regenerate Tervigon payslips** — `python manage.py regenerate_payslips_statutory --company 1` (ops)
9. ~~**PF/ESI challan CSV export**~~ ✅ Aug 22
10. ~~**Per-employee PT state**~~ ✅ Aug 22
11. ~~**Mobile API:** unified approvals counts~~ ✅ Aug 22 `/api/base/pending-approvals/`
12. ~~**Mobile API:** unified approval inbox (list + approve/reject actions)~~ ✅ Aug 22

### Known limitations (not bugs, design gaps)

- PF wages = contract `basic_pay`, not full CTC breakdown
- Payslips generated **before** statutory enable show PF ₹0 until regenerated
- Horilla theme does not load legacy `oh-sticky-table` CSS — use HTML `<table>` in new UIs

---

## Priority roadmap (Tervigon)

### Phase 1 — Must-have (3–6 months)

| # | Item | Status |
|---|------|--------|
| 1 | Indian statutory engine (PF, ESI, PT, TDS, Form 16) | ⚠️ **Partial — engine live** |
| 2 | Attendance-linked LOP | ✅ **Done** |
| 3 | Leave accrual + pending balance hold | ✅ **Done Aug 22** |
| 4 | Mobile API: monthly summary, approvals, payslip | ✅ **Done Aug 22** |
| 5 | Unified approval inbox + multi-level | ⚠️ **Inbox done; multi-level partial** |

**Phase 1 next engineering:**

- ~~PF/ESI challan export CSV~~ ✅
- ~~Per-employee PT state from work info~~ ✅
- ~~Route comp-off + allocation reject through `leave/services.py`~~ ✅
- ~~Mobile API parity for payslip + pending counts~~ ✅
- ~~Mobile approval actions (approve/reject from single API)~~ ✅
- ~~Web unified approval inbox UI~~ ✅ `/approvals/inbox/`
- ~~Form 24Q CSV export~~ ✅
- ~~Leave monthly accrual + sandwich policy~~ ✅ + grade/position accrual rules + `job_grade`
- ~~F&F settlement estimate~~ ✅ `/offboarding/fnf-settlement/<pk>/` + workflow `/offboarding/fnf-settlements/`
- ~~Travel expense type on reimbursement~~ ✅
- ~~EPS/EDLI PF split + PF/ESI/PT registers~~ ✅ `/payroll/india-statutory/registers/`
- ~~TRACES e-filing integration~~ ✅ `/payroll/india-statutory/traces/`
- LMS module

### Phase 2 progress (Aug 22)

| Item | Status |
|------|--------|
| Leave encashment pipeline (FIFO + reject restore fix) | ✅ |
| CTC wizard (Basic/HRA/Special split) | ✅ `/payroll/contract/<id>/ctc-wizard/` |
| Payroll accounting journal CSV | ✅ `/payroll/india-statutory/accounting-export/` |
| F&F settlement estimate on exit process | ✅ |
| F&F confirm / pay / PDF + loan recovery | ✅ `/offboarding/fnf-settlements/` |
| Travel expense fields on reimbursement | ✅ |
| OT approval → payroll | ✅ via OT allowance on approved OT |

### Phase 2 — Professional HRMS (6–12 months)

6. ~~Sandwich leave, encashment pipeline, F&F settlement calc~~ ✅ + F&F workflow (confirm/pay/PDF)  
7. ~~CTC wizard~~ ✅ + increment letters `/payroll/salary-revisions/` + arrears payout + salary hold `/payroll/salary-holds/`  
8. ~~OT approval workflow → payroll~~ ✅ (configure OT allowance)  
9. ~~WhatsApp payslip/leave notifications~~ ✅ via existing `notify.send(...)` -> WhatsApp bridge  
10. ~~Tally / accounting export~~ ✅ journal CSV  

### Phase 3 — Keka parity (12+ months)

11. Travel & expense module  
12. 360° + calibration + LMS  
13. Resume AI, career portal, Naukri integration  
14. Advanced analytics & compliance registers  

---

## Comparison matrix

| Capability | Horilla | Keka | greytHR | Zoho People |
|------------|---------|------|---------|-------------|
| Core HR + ESS | ✅ | ✅ | ✅ | ✅ |
| Attendance (complex shifts) | ⚠️ | ✅ | ✅ | ✅ |
| Leave policies | ⚠️ | ✅ | ✅ | ✅ |
| **Indian payroll compliance** | ⚠️ Partial | ✅ | ✅ | ⚠️ (+ Zoho Payroll) |
| Recruitment ATS | ⚠️ | ✅ | ⚠️ | ⚠️ (+ Zoho Recruit) |
| OKR / PMS | ✅ | ✅ | ⚠️ | ✅ |
| Expense management | ⚠️ | ✅ | ⚠️ | ✅ |
| Mobile app depth | ⚠️ | ✅ | ⚠️ | ✅ |
| Self-hosted / no per-seat fee | ✅ | ❌ | ❌ | ❌ |

---

## Key file references

| Concern | Path |
|---------|------|
| India statutory engine | `payroll/methods/india_statutory.py` |
| India statutory views/URLs | `payroll/views/india_statutory_views.py`, `payroll/urls/india_statutory_urls.py` |
| India statutory UI | `payroll/templates/payroll/india_statutory/` |
| Payslip PDF | `payroll/templates/payroll/payslip/payslip_pdf.html` |
| Salary / LOP logic | `payroll/methods/methods.py`, `payroll/views/component_views.py` |
| Payslip RBAC + company scope | `payroll/cbv/accessibility.py` |
| Leave FIFO / reservation | `leave/services.py`, `leave/models.py` |
| Grade leave accrual | `LeaveAccrualRule`, `resolve_annual_leave_days()`, employee `job_grade` |
| Attendance punch | `attendance/views/clock_in_out.py`, `attendance/models.py` |
| Modern payroll dashboard | `payroll/dashboard.py`, `payroll/templates/payroll/dashboard.html` |
| REST API | `horilla_api/api_views/` |
| Pending approvals (mobile) | `base/pending_approvals.py`, `/api/base/pending-approvals/` |
| Approval inbox (web) | `base/approval_inbox_views.py`, `/approvals/inbox/` |
| Reimbursement approve/reject helper | `payroll/methods/reimbursement_actions.py` |
| CTC wizard | `payroll/methods/ctc_wizard.py`, `/payroll/contract/<id>/ctc-wizard/` |
| Salary revisions / arrears / holds | `payroll/models/salary_revision.py`, `/payroll/salary-revisions/`, `/payroll/salary-holds/` |
| Accounting export | `payroll/methods/accounting_export.py`, `/payroll/india-statutory/accounting-export/` |
| Statutory Excel import/export | `payroll/methods/india_statutory_excel.py`, `/payroll/india-statutory/excel/` |
| F&F settlement | `offboarding/settlement.py`, `/offboarding/fnf-settlement/<pk>/`, `/offboarding/fnf-settlements/` |
| Leave accrual / sandwich | `leave/services.py`, `LeaveType.monthly_accrual`, `sandwich_policy` |
| Installed apps | `horilla/settings/base.py` |

---

## Deployment notes

```bash
# Copy changed files into container
docker cp /var/jenkins_apps/horilla-src/<path> horilla-app-prod:/app/<path>

# Migrations (when models change)
docker exec horilla-app-prod python manage.py migrate payroll leave --noinput

# Restart
docker restart horilla-app-prod
```

**Post-statutory-enable checklist:**

1. Open `/payroll/india-statutory/settings/` — confirm **Active**, PT = Delhi  
2. Regenerate payslips: `python manage.py regenerate_payslips_statutory --company 1`  
3. Verify payslip PDF shows India statutory lines  
4. Export challans from `/payroll/india-statutory/challans/`

---

## How to use this document

- **Product / HR:** Use "Gaps by module" for expectations vs Keka-style tools. Indian statutory is **live** — use for internal payslips, Form 16 summaries, CSV exports (challans, 24Q, accounting journal), and TRACES-ready text files for portal upload.
- **Engineering:** Use "Bugs & fixes log" and "Priority roadmap" for sprint planning.
- **Compliance:** Challan and 24Q CSV exports + TRACES text files are live; statutory registers are live.

---

*Generated from codebase audit of `/var/jenkins_apps/horilla-src/` against Keka, greytHR, Zoho People, and Darwinbox feature sets. Update this file when major gaps are closed or new modules ship.*
