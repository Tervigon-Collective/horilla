from rest_framework import serializers

from base.models import Department, EmployeeType, JobPosition
from employee.models import (
    Actiontype,
    DisciplinaryAction,
    Employee,
    EmployeeBankDetails,
    EmployeeWorkInformation,
    Policy,
)
from horilla_documents.models import Document, DocumentRequest

from ...api_methods.employee.methods import get_next_badge_id
from ...api_methods.base.methods import mobile_file_path


class ActiontypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Actiontype
        fields = ["id", "title", "action_type"]


class EmployeeListSerializer(serializers.ModelSerializer):
    job_position_name = serializers.CharField(
        source="employee_work_info.job_position_id.job_position", read_only=True
    )
    employee_work_info_id = serializers.CharField(
        source="employee_work_info.id", read_only=True
    )
    employee_bank_details_id = serializers.CharField(
        source="employee_bank_details.id", read_only=True
    )

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_first_name",
            "employee_last_name",
            "email",
            "job_position_name",
            "employee_work_info_id",
            "employee_profile",
            "employee_bank_details_id",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["employee_profile"] = mobile_file_path(instance.employee_profile)
        return data


class EmployeeSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(
        source="employee_work_info.department_id.department", read_only=True
    )
    department_id = serializers.CharField(
        source="employee_work_info.department_id.id", read_only=True
    )
    job_position_name = serializers.CharField(
        source="employee_work_info.job_position_id.job_position", read_only=True
    )
    job_position_id = serializers.CharField(
        source="employee_work_info.job_position_id.id", read_only=True
    )
    employee_work_info_id = serializers.CharField(
        source="employee_work_info.id", read_only=True
    )
    employee_bank_details_id = serializers.CharField(
        source="employee_bank_details.id", read_only=True
    )

    class Meta:
        model = Employee
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        from employee.cbv.accessibility import is_hr_user

        data["employee_profile"] = mobile_file_path(instance.employee_profile)
        request = self.context.get("request")
        own_or_hr = bool(
            request
            and request.user.is_authenticated
            and (
                is_hr_user(request)
                or getattr(instance, "employee_user_id", None) == request.user
            )
        )
        if not own_or_hr:
            for field in (
                "dob",
                "gender",
                "address",
                "country",
                "state",
                "city",
                "zip",
                "qualification",
                "experience",
                "marital_status",
                "children",
                "emergency_contact",
                "emergency_contact_name",
                "emergency_contact_relation",
            ):
                data.pop(field, None)
        return data

    def create(self, validated_data):
        validated_data["badge_id"] = get_next_badge_id()
        return super().create(validated_data)


class EmployeeWorkInformationSerializer(serializers.ModelSerializer):
    job_position_name = serializers.CharField(
        source="job_position_id.job_position", read_only=True
    )
    department_name = serializers.CharField(
        source="department_id.department", read_only=True
    )
    shift_name = serializers.CharField(source="shift_id.employee_shift", read_only=True)
    employee_type_name = serializers.CharField(
        source="employee_type_id.employee_type", read_only=True
    )
    reporting_manager_first_name = serializers.CharField(
        source="reporting_manager_id.employee_first_name", read_only=True
    )
    reporting_manager_last_name = serializers.CharField(
        source="reporting_manager_id.employee_last_name", read_only=True
    )
    work_type_name = serializers.CharField(
        source="work_type_id.work_type", read_only=True
    )
    company_name = serializers.CharField(source="company_id.company", read_only=True)
    tags = serializers.SerializerMethodField()

    def get_tags(self, obj):
        return [
            {"id": tag.id, "title": tag.title, "color": tag.color}
            for tag in obj.tags.all()
        ]

    class Meta:
        model = EmployeeWorkInformation
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        from employee.cbv.accessibility import is_hr_user

        request = self.context.get("request")
        employee = getattr(instance, "employee_id", None)
        own_or_hr = bool(
            request
            and request.user.is_authenticated
            and (
                is_hr_user(request)
                or getattr(employee, "employee_user_id", None) == request.user
            )
        )
        if not own_or_hr:
            data.pop("basic_salary", None)
            data.pop("salary_hour", None)
        return data


class EmployeeBankDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeBankDetails
        fields = "__all__"


class EmployeeTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeType
        fields = "__all__"


class EmployeeBulkUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        # fields = [
        #     'employee_last_name',
        #     'address',
        #     'country',
        #     'state',
        #     'city',
        #     'zip',
        #     'dob',
        #     'gender',
        #     'qualification',
        #     'experience',
        #     'marital_status',
        #     'children',
        # ]
        fields = [
            "employee_last_name",
        ]


class DisciplinaryActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisciplinaryAction
        fields = "__all__"


class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = Policy
        fields = "__all__"


class DocumentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentRequest
        fields = "__all__"


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = "__all__"


class EmployeeSelectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_first_name",
            "employee_last_name",
            "badge_id",
            "employee_profile",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["employee_profile"] = mobile_file_path(instance.employee_profile)
        return data
