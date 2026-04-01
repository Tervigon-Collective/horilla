#!/usr/bin/env python
"""
Verification script to check if WFH feature files are correctly implemented
Run this before testing: python verify_wfh_implementation.py
"""

import os
import sys

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if os.path.exists(filepath):
        print(f"   [OK] {description}")
        return True
    else:
        print(f"   [FAIL] {description} - NOT FOUND")
        return False

def check_string_in_file(filepath, search_string, description):
    """Check if a string exists in a file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if search_string in content:
                print(f"   [OK] {description}")
                return True
            else:
                print(f"   [FAIL] {description} - NOT FOUND")
                return False
    except FileNotFoundError:
        print(f"   [FAIL] {description} - FILE NOT FOUND")
        return False

def verify_implementation():
    """Verify all WFH implementation files and changes"""

    print("=" * 70)
    print("VERIFYING WORK FROM HOME IMPLEMENTATION")
    print("=" * 70)

    all_checks_passed = True

    # Check 1: Model Fields
    print("\n[1] Checking Model Changes (attendance/models.py)...")
    checks = [
        ('attendance/models.py', 'is_work_from_home', 'is_work_from_home field'),
        ('attendance/models.py', 'wfh_requested', 'wfh_requested field'),
        ('attendance/models.py', 'wfh_request_ip', 'wfh_request_ip field'),
        ('attendance/models.py', 'wfh_approval_status', 'wfh_approval_status field'),
        ('attendance/models.py', 'wfh_approved_by', 'wfh_approved_by field'),
    ]
    for filepath, search, desc in checks:
        if not check_string_in_file(filepath, search, desc):
            all_checks_passed = False

    # Check 2: Clock-in View Changes
    print("\n[2] Checking Clock-in View (attendance/views/clock_in_out.py)...")
    checks = [
        ('attendance/views/clock_in_out.py', 'wfh-confirmation-modal', 'WFH confirmation modal'),
        ('attendance/views/clock_in_out.py', 'Are you working from home?', 'WFH prompt message'),
        ('attendance/views/clock_in_out.py', 'def clock_in_wfh', 'clock_in_wfh function'),
    ]
    for filepath, search, desc in checks:
        if not check_string_in_file(filepath, search, desc):
            all_checks_passed = False

    # Check 3: WFH Approval Views
    print("\n[3] Checking WFH Approval Views...")
    checks = [
        ('attendance/views/wfh_approval.py', 'wfh_pending_requests', 'Pending requests view'),
        ('attendance/views/wfh_approval.py', 'wfh_approve_request', 'Approve request view'),
        ('attendance/views/wfh_approval.py', 'wfh_reject_request', 'Reject request view'),
        ('attendance/views/wfh_approval.py', 'wfh_requests_count', 'Request count API'),
    ]
    for filepath, search, desc in checks:
        if not check_string_in_file(filepath, search, desc):
            all_checks_passed = False

    # Check 4: URL Configuration
    print("\n[4] Checking URL Configuration (attendance/urls.py)...")
    checks = [
        ('attendance/urls.py', 'wfh_approval', 'WFH approval import'),
        ('attendance/urls.py', 'clock-in-wfh', 'WFH clock-in URL'),
        ('attendance/urls.py', 'wfh-pending-requests', 'Pending requests URL'),
        ('attendance/urls.py', 'wfh-approve-request', 'Approve URL'),
        ('attendance/urls.py', 'wfh-reject-request', 'Reject URL'),
    ]
    for filepath, search, desc in checks:
        if not check_string_in_file(filepath, search, desc):
            all_checks_passed = False

    # Check 5: Templates
    print("\n[5] Checking Templates...")
    template_path = 'attendance/templates/attendance/wfh_approval/pending_requests.html'
    if check_file_exists(template_path, 'WFH pending requests template'):
        checks = [
            (template_path, 'Pending WFH Requests', 'Template title'),
            (template_path, 'wfh-approve-request', 'Approve button'),
            (template_path, 'wfh-reject-request', 'Reject button'),
        ]
        for filepath, search, desc in checks:
            if not check_string_in_file(filepath, search, desc):
                all_checks_passed = False
    else:
        all_checks_passed = False

    # Check 6: Migration
    print("\n[6] Checking Database Migration...")
    migration_path = 'attendance/migrations/0001_add_wfh_fields.py'
    if check_file_exists(migration_path, 'WFH fields migration'):
        checks = [
            (migration_path, 'is_work_from_home', 'is_work_from_home in migration'),
            (migration_path, 'wfh_approval_status', 'wfh_approval_status in migration'),
        ]
        for filepath, search, desc in checks:
            if not check_string_in_file(filepath, search, desc):
                all_checks_passed = False
    else:
        all_checks_passed = False

    # Check 7: Test Files
    print("\n[7] Checking Test/Documentation Files...")
    check_file_exists('TEST_WFH_FEATURE.md', 'Testing guide')
    check_file_exists('setup_wfh_test.py', 'Test setup script')

    # Final Summary
    print("\n" + "=" * 70)
    if all_checks_passed:
        print("[SUCCESS] ALL CHECKS PASSED! Implementation looks good.")
        print("=" * 70)
        print("\nNEXT STEPS:")
        print("   1. Install/activate virtual environment")
        print("   2. Run: python manage.py makemigrations")
        print("   3. Run: python manage.py migrate")
        print("   4. Run: python setup_wfh_test.py")
        print("   5. Run: python manage.py runserver")
        print("   6. Follow TEST_WFH_FEATURE.md for testing")
        print("\nQuick Start:")
        print("   source venv/Scripts/activate  # Activate venv")
        print("   python manage.py migrate")
        print("   python setup_wfh_test.py")
        print("   python manage.py runserver")
    else:
        print("[WARNING] SOME CHECKS FAILED - Review the output above")
        print("=" * 70)
        return False

    print("=" * 70)
    return True

if __name__ == "__main__":
    try:
        success = verify_implementation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Verification Error: {e}")
        sys.exit(1)
