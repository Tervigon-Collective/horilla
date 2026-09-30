"""
context_processor.py

This module is used to register context processor`
"""

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.urls import path
from django.utils.functional import SimpleLazyObject
from django.utils.translation import gettext_lazy as _

from base.models import (
    Company,
    CompanyLanguageSetting,
    DefaultExportPermission,
    TrackLateComeEarlyOut,
)
from base.urls import urlpatterns
from employee.models import EmployeeGeneralSetting, ProfileEditFeature
from horilla.__version__ import __version__
from horilla.decorators import hx_request_required, login_required
from horilla.http.response import HorillaRedirect
from horilla.methods import get_horilla_model_class

_CACHE_MISS = object()


def _cached(key, loader, ttl=90):
    """Remember a small settings lookup. These repeat on every page."""
    from django.core.cache import cache

    hit = cache.get(key, _CACHE_MISS)
    if hit is not _CACHE_MISS:
        return hit
    value = loader()
    try:
        cache.set(key, value, ttl)
    except Exception:
        pass
    return value


class AllCompany:
    """
    Dummy class for the "all companies" switcher entry.
    """

    class Urls:
        url = "https://ui-avatars.com/api/?name=All+Company&background=random"

    company = "All Company"
    icon = Urls()
    text = "All companies"
    id = None


class AllMyCompanies(AllCompany):
    """Non-superuser combined view over assignment companies only."""

    class Urls:
        url = "https://ui-avatars.com/api/?name=All+My+Companies&background=random"

    company = "All my companies"
    icon = Urls()
    text = "All my companies"


def get_companies(request):
    """
    Companies for the header switcher.

    With COMPANY_SCOPED_PERMISSIONS on, non-superusers see assignment companies
    plus their work-info company. "All my companies" appears when they hold
    roles in 2+ companies (combined view over those assignment IDs only).
    """
    from base.auth_backends import (
        company_scoped_active,
        get_allowed_company_ids,
        get_assigned_company_ids,
    )

    scoped = (
        company_scoped_active()
        and request.user.is_authenticated
        and not request.user.is_superuser
    )
    allowed_ids = get_allowed_company_ids(request.user) if scoped else None
    assigned_ids = get_assigned_company_ids(request.user) if scoped else None
    def _rows():
        qs = Company.objects.all()
        if scoped:
            qs = qs.filter(id__in=allowed_ids or [])
        rows = []
        for company in qs:
            try:
                icon = company.icon.url if company.icon else ""
            except Exception:
                icon = ""
            rows.append([company.id, company.company, icon, False])
        return rows

    cache_key = (
        "horilla:companies:scoped:" + ",".join(str(i) for i in sorted(allowed_ids or []))
        if scoped
        else "horilla:companies:all"
    )
    companies = [row[:] for row in _cached(cache_key, _rows)]
    if scoped and assigned_ids and len(assigned_ids) >= 2:
        companies = [
            [
                "all",
                "All my companies",
                "https://ui-avatars.com/api/?name=All+My+Companies&background=random",
                False,
            ],
        ] + companies
    elif not scoped:
        companies = [
            [
                "all",
                "All Company",
                "https://ui-avatars.com/api/?name=All+Company&background=random",
                False,
            ],
        ] + companies
    selected_company = request.session.get("selected_company")
    company_selected = False
    if selected_company and selected_company == "all":
        if companies and companies[0][0] == "all":
            companies[0][3] = True
            company_selected = True
    else:
        for company in companies:
            if str(company[0]) == selected_company:
                company[3] = True
                company_selected = True

    if not request.user.is_authenticated:
        show_switcher = False
    elif scoped:
        show_switcher = len(companies) > 1
    else:
        show_switcher = request.user.has_perm("base.change_company")
    return {
        "all_companies": companies,
        "company_selected": company_selected,
        "show_company_switcher": show_switcher,
    }


@login_required
@hx_request_required
def update_selected_company(request):
    """
    This method is used to update the selected company on the session
    """
    from base.auth_backends import (
        company_scoped_active,
        get_allowed_company_ids,
        get_assigned_company_ids,
    )

    company_id = request.GET.get("company_id")
    next_url = request.META.get("HTTP_REFERER") or "/"

    if company_scoped_active() and not request.user.is_superuser:
        allowed = get_allowed_company_ids(request.user)
        assigned = get_assigned_company_ids(request.user)
        if company_id == "all":
            # Combined view over assignment companies only (need 2+ roles)
            target_allowed = len(assigned) >= 2
        else:
            try:
                target_allowed = int(company_id) in allowed
            except (TypeError, ValueError):
                target_allowed = False
        if not target_allowed:
            messages.error(request, _("You do not have access to that company."))
            return HorillaRedirect(request, redirect_to=next_url)
    elif not request.user.has_perm("base.change_company"):
        messages.error(request, _("You do not have permission to switch the company."))
        return HorillaRedirect(request, redirect_to=next_url)
    user = request.user.employee_get
    user_company = getattr(
        getattr(user, "employee_work_info", None), "company_id", None
    )
    request.session["selected_company"] = company_id
    request.session.pop("hlv_selected_ids", None)
    request.session.pop("prev_path", None)
    scoped_all = (
        company_id == "all"
        and company_scoped_active()
        and not request.user.is_superuser
    )
    company = (
        AllMyCompanies()
        if scoped_all
        else (
            AllCompany()
            if company_id == "all"
            else (
                Company.objects.filter(id=company_id).first()
                if Company.objects.filter(id=company_id).first()
                else AllCompany()
            )
        )
    )

    if company_id == "all":
        text = "All my companies" if scoped_all else "All companies"
    elif company_id == user_company:
        text = "My Company"
    else:
        text = "Other Company"

    company = {
        "company": company.company,
        "icon": company.icon.url,
        "text": text,
        "id": company.id,
    }
    request.session["selected_company_instance"] = company
    return HorillaRedirect(request, redirect_to=next_url)


urlpatterns.append(
    path(
        "update-selected-company/",
        update_selected_company,
        name="update-selected-company",
    )
)


def white_labelling_company(request):
    product_name = getattr(settings, "WHITE_LABEL_NAME", None) or "Seleric HRMS"
    white_labelling = getattr(settings, "WHITE_LABELLING", False)
    if white_labelling:
        hq = Company.objects.filter(hq=True).last() or Company.objects.order_by("id").first()
        try:
            company = (
                request.user.employee_get.get_company()
                if request.user.employee_get.get_company()
                else hq
            )
        except Exception:
            company = hq

        return {
            "white_label_company_name": product_name,
            "white_label_company": company,
        }
    return {
        "white_label_company_name": product_name,
        "white_label_company": None,
    }


def doc_base_url(request):
    """
    Base domain for in-app help/doc links. Templates build the full link as
    "{{ DOC_BASE_URL }}<path>" so only this one setting needs to change for
    white-labelled deployments.
    """
    return {
        "DOC_BASE_URL": getattr(settings, "DOC_BASE_URL", "https://www.horilla.com")
    }


def resignation_request_enabled(request):
    """
    Check weather resignation_request enabled of not in offboarding
    """
    selected_company = request.session.get("selected_company") or "all"

    def load():
        enabled = False
        first = None
        if apps.is_installed("offboarding"):
            OffboardingGeneralSetting = get_horilla_model_class(
                app_label="offboarding", model="offboardinggeneralsetting"
            )
            if selected_company != "all":
                first = OffboardingGeneralSetting.objects.filter(
                    company_id=selected_company
                ).first()
            else:
                first = OffboardingGeneralSetting.objects.first()
        if first:
            enabled = first.resignation_request
        return enabled

    return {
        "enabled_resignation_request": _cached(
            f"horilla:resignation:{selected_company}", load
        )
    }


def timerunner_enabled(request):
    """
    Whether Time Runner (at-work tracker) is enabled for the selected company.
    Prefers the company-specific AttendanceGeneralSetting, then the global
    (company_id=None) row, then defaults to enabled.
    """
    selected_company = request.session.get("selected_company") or "all"

    def load():
        enabled = True
        if apps.is_installed("attendance"):
            AttendanceGeneralSetting = get_horilla_model_class(
                app_label="attendance", model="attendancegeneralsetting"
            )
            if selected_company != "all":
                company = Company.objects.filter(id=selected_company).first()
            else:
                company = None
            setting = AttendanceGeneralSetting.objects.filter(company_id=company).first()
            if not setting and company is not None:
                setting = AttendanceGeneralSetting.objects.filter(
                    company_id=None
                ).first()
            if setting:
                enabled = setting.time_runner
        return enabled

    return {
        "enabled_timerunner": _cached(f"horilla:timerunner:{selected_company}", load)
    }


def intial_notice_period(request):
    """
    Check weather resignation_request enabled of not in offboarding
    """
    selected_company = request.session.get("selected_company") or "all"

    def load():
        initial = 30
        first = None
        rounding = {
            "component_mode": "two_decimals",
            "net_pay_mode": "nearest_rupee",
            "statutory_mode": "two_decimals",
        }
        if apps.is_installed("payroll"):
            PayrollGeneralSetting = get_horilla_model_class(
                app_label="payroll", model="payrollgeneralsetting"
            )
            if selected_company != "all":
                first = PayrollGeneralSetting.objects.filter(
                    company_id=selected_company
                ).first()
                if not first:
                    first = PayrollGeneralSetting.objects.filter(
                        company_id=None
                    ).first()
            else:
                first = PayrollGeneralSetting.objects.first()
        if first:
            initial = first.notice_period
            rounding = {
                "component_mode": getattr(first, "component_round_mode", None)
                or "two_decimals",
                "net_pay_mode": getattr(first, "net_pay_round_mode", None)
                or "nearest_rupee",
                "statutory_mode": getattr(first, "statutory_round_mode", None)
                or "two_decimals",
            }
        return {"get_initial_notice_period": initial, "rounding": rounding}

    return _cached(f"horilla:notice:{selected_company}", load)


def check_candidate_recruitment_setting(request):
    """
    This method is used to resolve the RecruitmentGeneralSetting for the current request
    """
    if hasattr(request, "_recruitment_general_setting_cache"):
        return request._recruitment_general_setting_cache

    RecruitmentGeneralSetting = get_horilla_model_class(
        app_label="recruitment", model="recruitmentgeneralsetting"
    )
    candidate_id = request.session.get("candidate_id")
    setting = None
    # Anonymous candidate sessions never carry selected_company, so resolve via
    # the candidate's own company instead of the company_id IS NULL fallback.
    if not request.user.is_authenticated and candidate_id:
        Candidate = get_horilla_model_class(app_label="recruitment", model="candidate")
        candidate = Candidate.objects.filter(pk=candidate_id).first()
        company_id = getattr(
            getattr(candidate, "recruitment_id", None), "company_id_id", None
        )
        if company_id:
            setting = RecruitmentGeneralSetting.objects.filter(
                company_id_id=company_id
            ).first()
        if not setting:
            setting = RecruitmentGeneralSetting.objects.filter(
                company_id__isnull=True
            ).first()
    else:
        selected_company = request.session.get("selected_company")
        if selected_company and selected_company != "all":
            setting = RecruitmentGeneralSetting.objects.filter(
                company_id_id=selected_company
            ).first()
        else:
            setting = RecruitmentGeneralSetting.objects.filter(
                company_id__isnull=True
            ).first()

    request._recruitment_general_setting_cache = setting
    return setting


def check_candidate_self_tracking(request):
    """
    This method is used to get the candidate self tracking is enabled or not
    """

    def _resolve():
        if not apps.is_installed("recruitment"):
            return False
        first = check_candidate_recruitment_setting(request)
        return bool(first and first.candidate_self_tracking)

    return {"check_candidate_self_tracking": SimpleLazyObject(_resolve)}


def check_candidate_self_tracking_rating(request):
    """
    This method is used to check enabled/disabled of rating option
    """

    def _resolve():
        if not apps.is_installed("recruitment"):
            return False
        first = check_candidate_recruitment_setting(request)
        return bool(first and first.show_overall_rating)

    return {"check_candidate_self_tracking_rating": SimpleLazyObject(_resolve)}


def get_initial_prefix(request):
    """
    This method is used to get the initial prefix
    """
    def load():
        row = EmployeeGeneralSetting.objects.first()
        if not row:
            return {"get_initial_prefix": "PEP", "prefix_instance_id": None}
        return {
            "get_initial_prefix": row.badge_id_prefix,
            "prefix_instance_id": row.id,
        }

    return _cached("horilla:badge-prefix", load)


def biometric_app_exists(request):
    from django.conf import settings

    biometric_app_exists = "biometric" in settings.INSTALLED_APPS
    return {"biometric_app_exists": biometric_app_exists}


def enable_late_come_early_out_tracking(request):
    if request is None:
        tracking = TrackLateComeEarlyOut.objects.first()
        enable = tracking.is_enable if tracking else True
        return {"tracking": enable, "late_come_early_out_tracking": enable}
    selected_company = request.session.get("selected_company") or "all"

    def load():
        if selected_company == "all":
            company = None
        else:
            company = Company.objects.filter(id=selected_company).first()
        tracking = TrackLateComeEarlyOut.objects.filter(company_id=company).first()
        return tracking.is_enable if tracking else True

    enable = _cached(f"horilla:late-track:{selected_company}", load)
    return {"tracking": enable, "late_come_early_out_tracking": enable}


def enable_profile_edit(request):
    from accessibility.accessibility import ACCESSBILITY_FEATURE

    def load_profile_edit():
        profile_edit = ProfileEditFeature.objects.filter().first()
        return bool(profile_edit and profile_edit.is_enabled)

    enable = _cached("horilla:profile-edit", load_profile_edit)
    if enable:
        if not any(item[0] == "profile_edit" for item in ACCESSBILITY_FEATURE):
            ACCESSBILITY_FEATURE.append(("profile_edit", _("Profile Edit Access")))

    return {"profile_edit_enabled": enable}


def export_access_enabled(request):
    """
    Exposes whether the "Default Export Access" setting is enabled for
    the user's current company, so templates can decide whether to show
    export buttons/menu options without requiring per-view context.
    Superusers always see export actions regardless of the setting.
    """
    if request.user.is_superuser:
        return {"export_access_enabled": True}

    selected_company = request.session.get("selected_company") or "all"

    def load():
        if selected_company == "all":
            company = None
        else:
            company = Company.objects.filter(id=selected_company).first()
        setting = DefaultExportPermission.objects.filter(company_id=company).first()
        return setting is None or bool(setting.is_enabled)

    enabled = _cached(f"horilla:export:{selected_company}", load)
    return {"export_access_enabled": enabled}


def navbar_languages(request):
    """
    Exposes the list of languages available in the navbar language
    switcher for the user's current company. The switcher is only shown
    when a company has explicitly enabled more than one language; with
    zero or one language enabled, there is nothing to switch to, so it
    stays hidden.
    """
    selected_company = request.session.get("selected_company") or "all"

    def load():
        if selected_company == "all":
            company = None
        else:
            company = Company.objects.filter(id=selected_company).first()
        setting = CompanyLanguageSetting.objects.filter(company_id=company).first()
        if not setting or not setting.enabled_languages:
            return []
        enabled_codes = set(setting.enabled_languages)
        return [
            language[0]
            for language in settings.LANGUAGES
            if language[0] in enabled_codes
        ]

    enabled_codes = _cached(f"horilla:languages:{selected_company}", load)
    languages = [
        language for language in settings.LANGUAGES if language[0] in enabled_codes
    ]
    if len(languages) > 1:
        return {"navbar_languages": languages, "show_language_switcher": True}

    return {"navbar_languages": [], "show_language_switcher": False}


def horilla_version(request):
    """
    Expose the running product version to every template.

    Until now `horilla/__version__.py` was read only by the build -- the Docker
    label, and the CI check that the tag matches it. Nothing showed it to the
    people running the product, so "which version are you on?" could not be
    answered from the screen. Support threads answered it with a branch name,
    which spans several releases and cannot say whether a given security fix is
    present.

    Deliberately not added to `/health/` or `/ready/`: both are unauthenticated
    and publicly reachable, and a version string there hands any scanner the
    exact set of advisories that apply.
    """
    return {"horilla_version": __version__}
