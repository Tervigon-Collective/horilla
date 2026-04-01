#!/usr/bin/env python
"""
Quick setup script for testing Work From Home approval feature
Run this with: python setup_wfh_test.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'horilla.settings')
django.setup()

from django.contrib.auth.models import User
from employee.models import Employee, EmployeeWorkInformation
from attendance.models import Attendance
from base.models import AttendanceAllowedIP, EmployeeShift, EmployeeShiftDay
from datetime import date, time

def setup_test_environment():
    """Set up test data for WFH approval feature"""

    print("=" * 60)
    print("🚀 Setting up Work From Home Test Environment")
    print("=" * 60)

    # Step 1: Enable IP restriction
    print("\n📍 Step 1: Configuring IP Restriction...")
    ip_config, created = AttendanceAllowedIP.objects.get_or_create(id=1)
    ip_config.is_enabled = True
    ip_config.additional_data = {"allowed_ips": ["182.77.58.234"]}
    ip_config.save()
    print("   ✅ IP restriction enabled for office IP: 182.77.58.234")

    # Step 2: Find or create test users
    print("\n👥 Step 2: Setting up test users...")

    # Get all employees
    employees = Employee.objects.all()

    if employees.count() < 2:
        print("   ⚠️  Warning: Need at least 2 employees (manager + employee)")
        print("   Please create employees first through admin panel")
        return

    # Use first employee as manager
    manager = employees.first()
    print(f"   👔 Manager: {manager.get_full_name()} (ID: {manager.id})")

    # Use second employee as test employee
    employee = employees[1] if employees.count() > 1 else employees.first()
    print(f"   👤 Employee: {employee.get_full_name()} (ID: {employee.id})")

    # Step 3: Set reporting manager relationship
    print("\n🔗 Step 3: Setting reporting manager relationship...")
    if hasattr(employee, 'employee_work_info') and employee.employee_work_info:
        work_info = employee.employee_work_info
        work_info.reporting_manager_id = manager
        work_info.save()
        print(f"   ✅ {manager.get_full_name()} is now reporting manager for {employee.get_full_name()}")
    else:
        print("   ⚠️  Warning: Employee doesn't have work info. Please set it up in admin panel.")
        return

    # Step 4: Clean up old test data
    print("\n🧹 Step 4: Cleaning up old WFH test data...")
    old_wfh = Attendance.objects.filter(
        employee_id=employee,
        wfh_requested=True,
        attendance_date=date.today()
    )
    deleted_count = old_wfh.count()
    old_wfh.delete()
    print(f"   ✅ Removed {deleted_count} old WFH test records")

    # Step 5: Create test WFH attendance
    print("\n📝 Step 5: Creating test WFH attendance request...")

    try:
        # Get shift and work type
        shift = work_info.shift_id
        work_type = work_info.work_type_id

        if not shift:
            print("   ⚠️  Warning: Employee doesn't have a shift assigned")
            print("   Please assign a shift in admin panel")
            return

        # Get today's day
        day_name = date.today().strftime("%A").lower()
        attendance_day = EmployeeShiftDay.objects.get(day=day_name)

        # Create WFH attendance
        attendance = Attendance.objects.create(
            employee_id=employee,
            attendance_date=date.today(),
            attendance_clock_in_date=date.today(),
            attendance_clock_in=time(9, 0, 0),
            shift_id=shift,
            work_type_id=work_type,
            attendance_day=attendance_day,
            minimum_hour="08:00",
            is_work_from_home=True,
            wfh_requested=True,
            wfh_request_ip="192.168.1.100",
            wfh_approval_status="pending",
            attendance_validated=False
        )
        print(f"   ✅ Created WFH attendance request (ID: {attendance.id})")
        print(f"   📅 Date: {attendance.attendance_date}")
        print(f"   🕘 Check-in: {attendance.attendance_clock_in}")
        print(f"   🌐 IP: {attendance.wfh_request_ip}")

    except Exception as e:
        print(f"   ❌ Error creating attendance: {e}")
        return

    # Step 6: Display test information
    print("\n" + "=" * 60)
    print("✅ TEST ENVIRONMENT READY!")
    print("=" * 60)
    print(f"\n📊 Test Data Summary:")
    print(f"   Manager: {manager.get_full_name()}")
    print(f"   Employee: {employee.get_full_name()}")
    print(f"   WFH Attendance ID: {attendance.id}")
    print(f"   Status: {attendance.wfh_approval_status}")

    print(f"\n🧪 Test Instructions:")
    print(f"   1. Start server: python manage.py runserver")
    print(f"   2. Login as manager: {manager.employee_user_id.username if manager.employee_user_id else 'N/A'}")
    print(f"   3. Visit: http://127.0.0.1:8000/attendance/wfh-pending-requests/")
    print(f"   4. You should see 1 pending WFH request")
    print(f"   5. Test approve/reject buttons")

    print(f"\n📱 To Test Check-in Flow:")
    print(f"   1. Login as employee: {employee.employee_user_id.username if employee.employee_user_id else 'N/A'}")
    print(f"   2. Go to attendance page")
    print(f"   3. Click check-in (will show WFH prompt if IP != 182.77.58.234)")

    print(f"\n💡 Tip: Check TEST_WFH_FEATURE.md for detailed testing guide")
    print("=" * 60)

if __name__ == "__main__":
    try:
        setup_test_environment()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure you have:")
        print("  1. Run migrations: python manage.py migrate")
        print("  2. Created at least 2 employees")
        print("  3. Set up work info for employees")
        sys.exit(1)
