# Horilla HRMS — Gap Analysis vs Industry (Keka, greytHR, Zoho People)

**Deployment:** Tervigon / Seleric — `hrms.seleric.com`  
**Source:** `/var/jenkins_apps/horilla-src/`  
**Last updated:** 25 August 2026  
**Purpose:** Track what Horilla has today, what is partial, and what is missing compared to leading Indian HRMS products — including the **organization-wide payroll architecture** blueprint (Aug 25).

---

## Executive summary

Horilla is a capable **open-source HRMS foundation** with solid web UI across core modules (employee, attendance, leave, payroll, recruitment, onboarding/offboarding, PMS, assets, helpdesk, projects, reports). It covers roughly **65–75% of a basic HRMS** after the Aug 2026 Tervigon compliance sprint.

The largest **remaining** gaps vs Keka / greytHR / Zoho People:

| Gap area | Severity | Status (Aug 2026) |
|----------|----------|-------------------|
| Indian statutory payroll (PF, ESI, PT, TDS, Form 16) | Critical | **Partial — engine, challans, Form 24Q, TRACES, EPF ECR live** |
| **Versioned payroll run + lock + snapshot payslips** | Critical | **Done** — `/payroll/payroll-runs/` |
| **Configurable proration + statutory wage (50% Code on Wages)** | Critical | **Done** |
| Attendance → payroll LOP | Critical | **Done** |
| Leave accrual, sandwich, balance hold | High | **Done — FIFO + reservation + accrual + sandwich** |
| Unified approvals + mobile API parity | High | **Done — web inbox + mobile inbox/actions (incl. OT)** |
| Expense / travel, F&F settlement, LMS | Medium | **Partial — travel + mileage/limits + F&F + LMS MVP + probation confirm live** |

---

## Organization-Wide Payroll Architecture (target)

**Source:** HR/Finance recommended blueprint (Aug 25 2026) — 40-section production payroll model.  
**Principle:** Payroll is a **versioned financial transaction system**, not a spreadsheet formula. Never overwrite history; never hard-code statutory ₹ amounts; never silently recalculate locked months.

### Sample CTC packs (reference — configure via CTC wizard / allowances)

| Pack | Basic | HRA | Special | Gross | EE PF | Net | ER PF | ESI EE/ER | Monthly CTC |
|------|------:|----:|--------:|------:|------:|----:|------:|----------:|------------:|
| A | 30,000 | 18,000 | 12,000 | 60,000 | 1,800 | 58,200 | 1,800 | — | 61,800 |
| B | 22,500 | 13,500 | 9,000 | 45,000 | 1,800 | 43,200 | 1,800 | — | 46,800 (+TDS notes) |
| C | 14,100 | 8,460 | 5,640 | 28,200 | 1,800 | 26,400 | 1,800 | — | 30,000 |
| D | 20,000 | 0 | 0 | 20,000 | 1,800 | 18,050 | 1,800 | 150 / 650 | 22,450 |

> PF ₹1,800 = min(PF wage, ₹15,000) × 12% — **must stay config-driven** (`pf_wage_ceiling` + rates). Never hard-code 1800 in UI or reports as a constant.

### Blueprint vs Horilla today

| # | Layer | Status | Notes / path |
|---|--------|--------|--------------|
| 1 | Config masters + effective dating | ✅ Done | Allowance effective_from/to + component flags; statutory/tax masters dated via settings |
| 2 | Employee master (statutory + bank + payroll status) | ✅ Done | `EmployeeStatutoryProfile.payroll_status` Included/On Hold/Excluded + TDS proofs |
| 3 | Salary Component Master (reusable, flags) | ✅ Done | Gross/CTC/wage/PF/ESI/excluded/proratable/payslip_visible on `Allowance` |
| 4 | Employee salary structure **versions** | ✅ Done | Version/status/effective_to; close V1 on new apply; `structure_as_of` replay |
| 5 | Payroll period + workflow statuses | ✅ Done | `/payroll/payroll-runs/` full status machine |
| 6 | Eligibility engine (DOJ/LWD/hold) | ✅ Done | Payable window + payroll_status + salary hold |
| 7 | Attendance input (locked finalized days) | ✅ Done | Must lock attendance before Calculate |
| 8 | Proration engine (calendar / working day) | ✅ Done | Policy on run + join/exit window |
| 9 | Gross earnings stack | ✅ Done | Fixed + variables + arrears + structure replay |
| 10 | Statutory wage engine (50% CoW rule) | ✅ Done | Flag-aware 50% rule → PF base |
| 11 | PF engine (rates, ceiling, VPF, EPS/EDLI) | ✅ Done | Ceiling + optional actual-wage contribution |
| 12 | ESI engine (ceiling + contribution period) | ✅ Done | Ceiling + once-covered continuity |
| 13 | PT by state + slab + month | ✅ Done | State slabs + location resolve |
| 14 | TDS annual projection engine | ✅ Done | Prev employer + other income + proofs + remaining months |
| 15–18 | Variable / reimbursement / loan / other deductions | ✅ Done | Bound into run calculate / one-time settle |
| 19–22 | Net / employer cost / CTC | ✅ Done | Net + employer lines + `annual_ctc_for_employee` |
| 23 | Validation engine (errors / warnings) | ✅ Done | Run validate + MoM variance |
| 24 | Manual override with audit | ✅ Done | `PayslipOverride` |
| 25–27 | Approval → lock → versioning | ✅ Done | Lock + reopen new version |
| 28–29 | Payslip from **locked snapshot** + publish gate | ✅ Done | `snapshot_frozen` + `PayrollRunSnapshot` archive |
| 30–32 | Reports / variance / dashboard | ✅ Done | Run variance + bank transfer CSV |
| 33–36 | Join / FnF / arrears / retro attendance | ✅ Done | FnF + revision arrears + `AttendanceArrear` |
| 37 | Org-wide rounding policy | ✅ Done | Settings + `save_payslip` |
| 38 | Calculation order (34 steps) | ✅ Done | Orchestrated via payroll run engine |
| 39 | Master / transaction / snapshot tables | ✅ Done | Run + snapshot + arrear tables |
| 40 | Never overwrite locked payroll | ✅ Done | Guards on save/delete/status + freeze |

### Phased build

| Phase | Focus | Outcome |
|-------|--------|---------|
| **P0–P6** | Full org payroll architecture | ✅ **Complete** Aug 25 2026 |
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
| EPF ECR 2.0 text export | ✅ Live Aug 26 | `/payroll/india-statutory/epf-ecr/` |
| WhatsApp payslip/leave notifications | ✅ Live Aug 24 | `whatsapp/views.py` receiver on `notify.send(...)` |
| LWF + Bonus Act + Gratuity | ✅ Live Aug 24 | Registers + F&F; LWF/Bonus opt-in on Settings |
| Salary revision increment letters | ✅ Live Aug 24 | `/payroll/salary-revisions/`, CTC wizard PDF |
| Arrears pay-out + salary hold/release | ✅ Live Aug 24 | `/payroll/salary-holds/`; one-time allowance from revision letter |
| Full & Final settlement workflow | ✅ Live Aug 24 | `/offboarding/fnf-settlements/` draft → confirm (salary hold) → paid + PDF |
| Grade / position leave accrual rules | ✅ Live Aug 24 | `job_grade` on work info + leave type accrual rules; service-duration eligibility |
| LMS (courses, enroll, lesson progress) | ✅ Live Aug 24 | `/lms/` catalog + My Learning; not a full Docebo/Keka LMS |
| OT in unified approval inbox | ✅ Live Aug 24 | `/approvals/inbox/` type `overtime` |
| Effective shift at punch (roster) | ✅ Live Aug 24 | Published roster for the date, else work-info shift |
| Missing punch → regularization | ✅ Live Aug 24 | Dashboard **Regularize** → attendance request (`request_type=missing_punch`) |
| Expense mileage + claim limits | ✅ Live Aug 24 | Encashment settings + travel km × rate; cap via `max_claim_amount` |
| Probation on employee work info | ✅ Live Aug 24 | `probation_end` + `employment_status`; copied from candidate on hire |
| Probation confirmation inbox | ✅ Live Aug 26 | `/employee/probation/` due/overdue + confirm (triggers CL) |
| Leave policy FY 2026-27 (Tervigon) | ✅ Live Aug 25 | CL/SL 12/FY monthly accrual + FY lapse; CL confirmed-only; Eid/LWP/LOA/Voting/Maternity shells; no EL/Half-day type |
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

Core: `employee`, `attendance`, `leave`, `payroll`, `recruitment`, `onboarding`, `offboarding`, `pms`, `lms`, `asset`, `helpdesk`, `project`, `report`, `biometric`, `horilla_api`, `horilla_automations`, `whatsapp`, `horilla_ldap`, `horilla_meet`, `horilla_backup`, and platform apps (`base`, `horilla_views`, `horilla_theme`, etc.).

**Runtime add-ons** (via `horilla_api`): `geofencing`, `facedetection`.

### Module capability snapshot (updated)

| Module | Present (web) | Partial | Absent |
|--------|---------------|---------|--------|
| **Employee** | CRUD, org chart, import/export, documents, disciplinary, statutory profile link, **probation end + employment status** | Field masking | Skills matrix, workforce planning |
| **Attendance** | Punch in/out, shifts, **roster shift at punch**, monthly summary, missing punch **regularize**, OT **inbox**, hour balance, biometric hooks | Geo/face (API-first) | Break / multi-punch rules |
| **Leave** | Types, half-day, CF, multi-approval, comp-off, restrictions, **FIFO + reservation + accrual + sandwich**, encashment pipeline | — | Advanced policy engine |
| **Payroll** | Contracts, allowances/deductions, payslip PDF, loans, reimbursement, **India statutory**, **CTC wizard**, **accounting export**, **WhatsApp payslip notifications**, **salary revision letters**, **holds/arrears** | US-style tax coexists | Live Tally API |
| **Recruitment** | Pipeline, stages, LinkedIn, offer status, surveys | — | Naukri/Indeed, resume AI, career portal, e-sign |
| **Onboarding / Offboarding** | Stages, tasks, resignation flow, **F&F workflow** | IT/asset return still manual | — |
| **PMS** | OKRs, key results, feedback, meetings | 360° not full cycle | Calibration, comp-linked increments |
| **LMS** | **Course catalog, enroll, lesson complete, My Learning** | No SCORM/quizzes/certificates | Full Docebo-style LMS |
| **Expense** | Reimbursement, encashment, **travel + mileage + claim cap** | — | OCR, full travel booking module |
| **Reports** | Pivot reports (attendance, leave, payroll, etc.) | No API | Scheduled delivery |
| **Mobile / API** | JWT API, monthly summary, payslip scoping, **pending approvals inbox + actions (web + mobile, incl. OT)** | — | Native LMS API |

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
| Effective shift at punch (rotation) | ✅ | ✅ Published roster for the date, else `work_info.shift_id` |
| OT approval → payroll | ✅ | ✅ OT allowance on approved OT + **unified inbox** type `overtime` |
| Break / multi-punch rules | ✅ | ❌ |
| Facial recognition | ✅ (Keka) | ⚠️ Optional API app |
| Missing punch → regularization workflow | ✅ | ✅ Dashboard Regularize → attendance request |
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
| Half-day consistent | ✅ | ✅ Fixed Aug 26 — no double half-day LOP subtract |

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
| Payroll | Half-day LOP no longer double-subtracted | ✅ Aug 26 |
| Payroll | Reimbursement.save/delete safe when request is None | ✅ Aug 26 |
| Payroll | Multi-level reimb: only superuser skips stages | ✅ Aug 26 |
| Leave | Inbox `can_act` + stage bypass for current-stage managers | ✅ Aug 26 |

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

### Still open (not shippable as MVP — industry-scale)

These remain **intentionally open** after the Aug 24 gap close. Do not treat them as done:

- Naukri / Indeed ATS integrations, resume parsing AI, public career portal, offer e-sign
- Full LMS: SCORM, quizzes, learning paths (MVP catalog/progress + **completion certificates** live)
- Expense OCR and a full travel-booking module (mileage + claim cap is live)
- Break / multi-punch attendance rules
- 360° review cycle + calibration + compensation-linked increments
- Live Tally / Zoho Books API (journal CSV export is live)
- Native mobile LMS API parity
- Skills matrix / workforce planning

Grant HR `lms.add_course` (and `lms.add_lesson`, `lms.add_courseenrollment`) to create/assign courses; employees can self-enroll and complete lessons without extra perms.


---

## Priority roadmap (Tervigon)

### Phase 0 — Organization-wide payroll architecture (next)

Aligned to the Aug 25 blueprint (see section above). Wrap existing PF/ESI/PT/TDS — do not rewrite.

| # | Item | Status |
|---|------|--------|
| P0 | Payroll run model + statuses through **LOCKED** | ✅ **Done** — `/payroll/payroll-runs/` |
| P1 | Payslip publish only from **locked snapshot** | ✅ **Done** — freeze + `PayrollRunSnapshot` archive |
| P2 | Org proration policy + DOJ/LWD eligibility service | ✅ **Done** |
| P3 | Statutory wage base (Code on Wages 50% rule) → PF/ESI | ✅ **Done** |
| P4 | Validation engine + MoM variance before Finance approve | ✅ **Done** |
| P5 | Salary structure versioning (close V1 / activate V2) | ✅ **Done** |
| P6 | Rounding policy + override audit trail | ✅ **Done** |
| — | CTC packs A–D / attendance lock / bank file / attendance arrears | ✅ **Done** |

### Phase 1 — Must-have (3–6 months)

| # | Item | Status |
|---|------|--------|
| 1 | Indian statutory engine (PF, ESI, PT, TDS, Form 16) | ⚠️ **Partial — engine live** |
| 2 | Attendance-linked LOP | ✅ **Done** |
| 3 | Leave accrual + pending balance hold | ✅ **Done Aug 22** |
| 4 | Mobile API: monthly summary, approvals, payslip | ✅ **Done Aug 22** |
| 5 | Unified approval inbox + multi-level | ✅ **Done — leave + reimbursement + OT sequential** |



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
- ~~Travel expense type on reimbursement~~ ✅ + mileage + claim cap
- ~~EPS/EDLI PF split + PF/ESI/PT registers~~ ✅ `/payroll/india-statutory/registers/`
- ~~TRACES e-filing integration~~ ✅ `/payroll/india-statutory/traces/`
- ~~LMS module~~ ✅ MVP `/lms/` (catalog, enroll, lessons + **completion certificates**)
- ~~Leave multi-level sequential approval~~ ✅ inbox/count parity + stage gate (web + API); balance deducted only on final stage
- ~~Reimbursement + OT multi-level~~ ✅ `reimbursement_amount` / `overtime_hours` on Multiple Approval Condition; stages + inbox Lx/N; allowance/OT flag only on final stage
- ~~EPF ECR 2.0 text export~~ ✅ `/payroll/india-statutory/epf-ecr/` (`#~#` UAN rows + missing-UAN validation)
- ~~Probation confirmation workflow~~ ✅ `/employee/probation/` (due/overdue tabs + confirm → CL assignment)
- ~~LMS completion certificates~~ ✅ `/lms/enrollments/<id>/certificate/` PDF (`LMS-000123`); My Learning + course enrollments
- ~~Expiring documents~~ ✅ `/employee/expiring-documents/` + fixed scheduler notify/deactivate
- ~~Dashboard HR alerts widget~~ ✅ probation + expiring-doc counts on home (`/dashboard/api/hr-alerts/`)

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

11. Travel & expense module — **partial** (travel type + mileage + limits; no OCR / booking)
12. 360° + calibration — **open**; LMS — **MVP live** `/lms/` (+ certificates)
13. Resume AI, career portal, Naukri integration — **open**
14. Advanced analytics & compliance registers — registers live; scheduled analytics **open**

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
| LMS | `lms/`, `/lms/`, `/lms/my/` |
| Leave accrual / sandwich | `leave/services.py`, `LeaveType.monthly_accrual`, `sandwich_policy` |
| Installed apps | `horilla/settings/base.py` |

---

## Deployment notes

```bash
# Copy changed files into container
docker cp /var/jenkins_apps/horilla-src/<path> horilla-app-prod:/app/<path>

# Migrations (when models change)
docker exec horilla-app-prod python manage.py migrate payroll leave employee lms --noinput

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
