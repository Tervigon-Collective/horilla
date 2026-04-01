"""
wfh_approval.py

This module contains views for managing work-from-home attendance approval workflow
"""

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from attendance.models import Attendance
from employee.models import Employee
from horilla.decorators import hx_request_required, login_required, permission_required


@login_required
def wfh_pending_requests(request):
    """
    View to display pending WFH attendance requests for approval by reporting manager
    """
    employee = request.user.employee_get

    # Get all employees who report to this manager
    subordinates = Employee.objects.filter(
        employee_work_info__reporting_manager_id=employee
    )

    # Get pending WFH requests for subordinates
    pending_requests = Attendance.objects.filter(
        employee_id__in=subordinates,
        wfh_requested=True,
        wfh_approval_status="pending"
    ).select_related(
        'employee_id',
        'employee_id__employee_work_info',
        'shift_id'
    ).order_by('-attendance_date')

    context = {
        'pending_requests': pending_requests,
    }

    return render(request, 'attendance/wfh_approval/pending_requests.html', context)


@login_required
@hx_request_required
def wfh_approve_request(request, attendance_id):
    """
    Approve a WFH attendance request
    """
    try:
        attendance = Attendance.objects.get(id=attendance_id)
        employee = request.user.employee_get

        # Verify that the requesting user is the reporting manager
        if attendance.employee_id.employee_work_info.reporting_manager_id != employee:
            return HttpResponse(
                _("You are not authorized to approve this request"),
                status=403
            )

        # Check if already processed
        if attendance.wfh_approval_status != "pending":
            return HttpResponse(
                _("This request has already been processed"),
                status=400
            )

        # Approve the request
        attendance.wfh_approval_status = "approved"
        attendance.wfh_approved_by = employee
        attendance.attendance_validated = True
        attendance.save()

        messages.success(
            request,
            _(f"Work from home request for {attendance.employee_id.get_full_name()} has been approved")
        )

        return HttpResponse(
            """
            <tr id="wfh-request-{id}" class="oh-alert oh-alert--success">
                <td colspan="6">
                    <ion-icon name="checkmark-circle-outline"></ion-icon>
                    {message}
                </td>
            </tr>
            <script>
                setTimeout(function() {{
                    $('#wfh-request-{id}').fadeOut(function() {{
                        $(this).remove();
                    }});
                }}, 2000);
            </script>
            """.format(
                id=attendance_id,
                message=_("Request approved successfully")
            )
        )

    except Attendance.DoesNotExist:
        return HttpResponse(_("Attendance record not found"), status=404)
    except Exception as e:
        return HttpResponse(_(f"Error approving request: {str(e)}"), status=500)


@login_required
@hx_request_required
def wfh_reject_request(request, attendance_id):
    """
    Reject a WFH attendance request
    """
    try:
        attendance = Attendance.objects.get(id=attendance_id)
        employee = request.user.employee_get

        # Verify that the requesting user is the reporting manager
        if attendance.employee_id.employee_work_info.reporting_manager_id != employee:
            return HttpResponse(
                _("You are not authorized to reject this request"),
                status=403
            )

        # Check if already processed
        if attendance.wfh_approval_status != "pending":
            return HttpResponse(
                _("This request has already been processed"),
                status=400
            )

        # Reject the request
        attendance.wfh_approval_status = "rejected"
        attendance.wfh_approved_by = employee
        attendance.attendance_validated = False

        # Delete the attendance record since it's rejected
        attendance.delete()

        messages.warning(
            request,
            _(f"Work from home request for {attendance.employee_id.get_full_name()} has been rejected")
        )

        return HttpResponse(
            """
            <tr id="wfh-request-{id}" class="oh-alert oh-alert--warning">
                <td colspan="6">
                    <ion-icon name="close-circle-outline"></ion-icon>
                    {message}
                </td>
            </tr>
            <script>
                setTimeout(function() {{
                    $('#wfh-request-{id}').fadeOut(function() {{
                        $(this).remove();
                    }});
                }}, 2000);
            </script>
            """.format(
                id=attendance_id,
                message=_("Request rejected successfully")
            )
        )

    except Attendance.DoesNotExist:
        return HttpResponse(_("Attendance record not found"), status=404)
    except Exception as e:
        return HttpResponse(_(f"Error rejecting request: {str(e)}"), status=500)


@login_required
def wfh_requests_count(request):
    """
    Get count of pending WFH requests for the logged-in manager
    """
    try:
        employee = request.user.employee_get

        # Get all employees who report to this manager
        subordinates = Employee.objects.filter(
            employee_work_info__reporting_manager_id=employee
        )

        # Count pending WFH requests
        count = Attendance.objects.filter(
            employee_id__in=subordinates,
            wfh_requested=True,
            wfh_approval_status="pending"
        ).count()

        return JsonResponse({'count': count})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
