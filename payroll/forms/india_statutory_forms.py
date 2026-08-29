"""Forms for Indian statutory payroll settings."""

from django import forms
from django.utils.translation import gettext_lazy as _

from payroll.models.india_statutory import (
    EmployeeStatutoryProfile,
    IndiaStatutorySettings,
)


class HorillaCheckboxInput(forms.CheckboxInput):
    template_name = "payroll/india_statutory/widgets/checkbox_switch.html"

    def __init__(self, attrs=None):
        attrs = attrs or {}
        attrs.setdefault("class", "oh-switch__checkbox")
        super().__init__(attrs)


class IndiaStatutorySettingsForm(forms.ModelForm):
    class Meta:
        model = IndiaStatutorySettings
        exclude = ["is_active", "company_id"]
        widgets = {
            "is_enabled": HorillaCheckboxInput(),
            "enable_pf": HorillaCheckboxInput(),
            "enable_esi": HorillaCheckboxInput(),
            "enable_pt": HorillaCheckboxInput(),
            "enable_tds": HorillaCheckboxInput(),
            "enable_lwf": HorillaCheckboxInput(),
            "enable_bonus": HorillaCheckboxInput(),
            "enable_gratuity": HorillaCheckboxInput(),
            "enable_code_on_wages_50pct": HorillaCheckboxInput(),
            "pf_wage_ceiling": forms.NumberInput(
                attrs={"class": "oh-input w-100", "step": "0.01"}
            ),
            "pf_employee_rate": forms.NumberInput(
                attrs={"class": "oh-input w-100", "step": "0.01"}
            ),
            "pf_employer_rate": forms.NumberInput(
                attrs={"class": "oh-input w-100", "step": "0.01"}
            ),
            "esi_gross_ceiling": forms.NumberInput(
                attrs={"class": "oh-input w-100", "step": "0.01"}
            ),
            "esi_employee_rate": forms.NumberInput(
                attrs={"class": "oh-input w-100", "step": "0.01"}
            ),
            "esi_employer_rate": forms.NumberInput(
                attrs={"class": "oh-input w-100", "step": "0.01"}
            ),
            "pt_state": forms.Select(attrs={"class": "oh-select oh-select-2 w-100"}),
            "default_tds_regime": forms.Select(
                attrs={"class": "oh-select oh-select-2 w-100"}
            ),
            "standard_deduction_annual": forms.NumberInput(
                attrs={"class": "oh-input w-100", "step": "0.01"}
            ),
            "standard_deduction_old_regime": forms.NumberInput(
                attrs={"class": "oh-input w-100", "step": "0.01"}
            ),
            "tan_number": forms.TextInput(
                attrs={"class": "oh-input w-100", "placeholder": "AAAA12345A"}
            ),
            "bsr_code": forms.TextInput(
                attrs={
                    "class": "oh-input w-100",
                    "placeholder": "0000000",
                    "maxlength": "7",
                }
            ),
            "pf_establishment_code": forms.TextInput(
                attrs={"class": "oh-input w-100"}
            ),
            "esi_establishment_code": forms.TextInput(
                attrs={"class": "oh-input w-100"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, HorillaCheckboxInput):
                continue
            field.widget.attrs.setdefault("class", "oh-input w-100")


class EmployeeStatutoryProfileForm(forms.ModelForm):
    class Meta:
        model = EmployeeStatutoryProfile
        exclude = ["is_active", "employee_id"]
        widgets = {
            "pf_applicable": HorillaCheckboxInput(),
            "esi_applicable": HorillaCheckboxInput(),
            "pt_applicable": HorillaCheckboxInput(),
            "tds_applicable": HorillaCheckboxInput(),
            "lwf_applicable": HorillaCheckboxInput(),
            "bonus_applicable": HorillaCheckboxInput(),
            "gratuity_applicable": HorillaCheckboxInput(),
            "tds_regime": forms.Select(attrs={"class": "oh-select oh-select-2 w-100"}),
            "section_80c_annual": forms.NumberInput(
                attrs={"class": "oh-input w-100", "step": "0.01"}
            ),
            "section_80d_annual": forms.NumberInput(
                attrs={"class": "oh-input w-100", "step": "0.01"}
            ),
            "other_chapter_vi_a": forms.NumberInput(
                attrs={"class": "oh-input w-100", "step": "0.01"}
            ),
            "vpf_rate": forms.NumberInput(
                attrs={"class": "oh-input w-100", "step": "0.01"}
            ),
            "contribute_pf_on_actual_wage": HorillaCheckboxInput(),
            "previous_employer_income": forms.NumberInput(
                attrs={"class": "oh-input w-100", "step": "0.01"}
            ),
            "previous_employer_tds": forms.NumberInput(
                attrs={"class": "oh-input w-100", "step": "0.01"}
            ),
            "other_income_annual": forms.NumberInput(
                attrs={"class": "oh-input w-100", "step": "0.01"}
            ),
            "proof_submission_status": forms.Select(
                attrs={"class": "oh-select oh-select-2 w-100"}
            ),
            "payroll_status": forms.Select(
                attrs={"class": "oh-select oh-select-2 w-100"}
            ),
        }
