# Testing Work-From-Home Approval Feature

## Step 1: Setup Environment

### 1.1 Create Virtual Environment (if not exists)
```bash
# Navigate to project directory
cd /c/Users/ekamm/OneDrive/Desktop/SpaceProjects/horilla

# Create virtual environment
python -m venv venv

# Activate it
source venv/Scripts/activate  # On Windows Git Bash
# OR
venv\Scripts\activate  # On Windows CMD
```

### 1.2 Install Dependencies
```bash
pip install -r requirements.txt
```

### 1.3 Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

---

## Step 2: Configure IP Restriction

### 2.1 Access Admin Panel
1. Start the server: `python manage.py runserver`
2. Go to: `http://127.0.0.1:8000/admin`
3. Login with superuser credentials

### 2.2 Enable IP Restriction
1. Navigate to: **Base > Attendance Allowed IPs**
2. Create/Edit the IP configuration:
   - ✅ Check "Is enabled"
   - Add allowed IP: `182.77.58.234`
   - Save

**Alternative: Using Django Shell**
```bash
python manage.py shell
```

```python
from base.models import AttendanceAllowedIP

# Create or update IP configuration
ip_config, created = AttendanceAllowedIP.objects.get_or_create(id=1)
ip_config.is_enabled = True
ip_config.additional_data = {"allowed_ips": ["182.77.58.234"]}
ip_config.save()

print("IP restriction enabled!")
exit()
```

---

## Step 3: Test Scenarios

### Test 1: Normal Check-in from Office IP ✅

**Setup:**
- Configure your test to simulate office IP (182.77.58.234)

**Steps:**
1. Login as employee
2. Click "Check-In" button
3. **Expected Result:** Normal check-in, no WFH prompt

**To Simulate Office IP:**
You can temporarily modify the IP in `clock_in` view for testing:
```python
# In attendance/views/clock_in_out.py, line ~230
ip = "182.77.58.234"  # Force office IP for testing
```

---

### Test 2: Check-in from Home IP (WFH Prompt) 🏠

**Setup:**
- Use actual IP or force a different IP

**Steps:**
1. Login as employee
2. Click "Check-In" button
3. **Expected Result:** Modal appears with message:
   - "You are checking in from a different IP address (YOUR_IP)"
   - "Are you working from home?"
   - Two buttons: "No" and "Yes"

**To Simulate Home IP:**
```python
# In attendance/views/clock_in_out.py, line ~230
ip = "192.168.1.100"  # Force home IP for testing
```

---

### Test 3: Employee Clicks "No" ❌

**Steps:**
1. Get WFH prompt (from Test 2)
2. Click "No" button
3. **Expected Result:** 
   - Modal closes
   - No check-in recorded
   - Can try again

---

### Test 4: Employee Clicks "Yes" - WFH Check-in ✅

**Steps:**
1. Get WFH prompt (from Test 2)
2. Click "Yes" button
3. **Expected Result:**
   - Check-in successful
   - Check-Out button appears
   - Alert message: "Your work from home attendance is pending approval from your reporting manager."

**Verify in Database:**
```bash
python manage.py shell
```
```python
from attendance.models import Attendance

# Get latest attendance
att = Attendance.objects.latest('id')
print(f"Employee: {att.employee_id.get_full_name()}")
print(f"Is WFH: {att.is_work_from_home}")
print(f"WFH Requested: {att.wfh_requested}")
print(f"Approval Status: {att.wfh_approval_status}")
print(f"Request IP: {att.wfh_request_ip}")
print(f"Validated: {att.attendance_validated}")

# Should show:
# Is WFH: True
# WFH Requested: True
# Approval Status: pending
# Validated: False
```

---

### Test 5: Manager Views Pending Requests 👀

**Prerequisites:**
- At least one WFH request pending (from Test 4)
- Login as the employee's reporting manager

**Steps:**
1. Login as reporting manager
2. Navigate to: `http://127.0.0.1:8000/attendance/wfh-pending-requests/`
3. **Expected Result:**
   - Table showing pending WFH requests
   - Columns: Employee, Date, Check-In Time, IP Address, Shift, Actions
   - Each row has "Approve" and "Reject" buttons

**If No Reporting Manager Set:**
```bash
python manage.py shell
```
```python
from employee.models import Employee, EmployeeWorkInformation

# Get employee who checked in
employee = Employee.objects.get(id=YOUR_EMPLOYEE_ID)

# Get a manager
manager = Employee.objects.get(id=MANAGER_ID)

# Set reporting manager
work_info = employee.employee_work_info
work_info.reporting_manager_id = manager
work_info.save()

print(f"Set {manager.get_full_name()} as reporting manager for {employee.get_full_name()}")
```

---

### Test 6: Manager Approves WFH Request ✅

**Steps:**
1. On pending requests page
2. Click "Approve" button for a request
3. **Expected Result:**
   - Success message appears
   - Row changes to green with "Request approved successfully"
   - Row fades out after 2 seconds
   - Request removed from pending list

**Verify in Database:**
```python
from attendance.models import Attendance

att = Attendance.objects.get(id=ATTENDANCE_ID)
print(f"Approval Status: {att.wfh_approval_status}")
print(f"Approved By: {att.wfh_approved_by.get_full_name()}")
print(f"Validated: {att.attendance_validated}")

# Should show:
# Approval Status: approved
# Approved By: [Manager Name]
# Validated: True
```

---

### Test 7: Manager Rejects WFH Request ❌

**Steps:**
1. On pending requests page
2. Click "Reject" button for a request
3. **Expected Result:**
   - Warning message appears
   - Row changes to yellow with "Request rejected successfully"
   - Row fades out after 2 seconds
   - Request removed from list
   - Attendance record deleted from database

**Verify in Database:**
```python
from attendance.models import Attendance

# Try to get the attendance (should not exist)
try:
    att = Attendance.objects.get(id=ATTENDANCE_ID)
    print("ERROR: Attendance still exists!")
except Attendance.DoesNotExist:
    print("✅ Attendance successfully deleted")
```

---

## Step 4: Quick Testing Script

Create a test script to quickly set up test data:

```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User
from employee.models import Employee, EmployeeWorkInformation
from attendance.models import Attendance
from base.models import AttendanceAllowedIP, EmployeeShift
from datetime import date, datetime, time

# 1. Enable IP restriction
ip_config, _ = AttendanceAllowedIP.objects.get_or_create(id=1)
ip_config.is_enabled = True
ip_config.additional_data = {"allowed_ips": ["182.77.58.234"]}
ip_config.save()
print("✅ IP restriction enabled")

# 2. Create test manager and employee (if not exists)
# Adjust this based on your existing users
manager = Employee.objects.first()
employee = Employee.objects.last()

# Set reporting relationship
if hasattr(employee, 'employee_work_info'):
    work_info = employee.employee_work_info
    work_info.reporting_manager_id = manager
    work_info.save()
    print(f"✅ Set {manager.get_full_name()} as manager for {employee.get_full_name()}")

# 3. Create a test WFH attendance
attendance = Attendance.objects.create(
    employee_id=employee,
    attendance_date=date.today(),
    attendance_clock_in_date=date.today(),
    attendance_clock_in=time(9, 0),
    shift_id=employee.employee_work_info.shift_id,
    work_type_id=employee.employee_work_info.work_type_id,
    attendance_day=EmployeeShiftDay.objects.get(day=date.today().strftime("%A").lower()),
    is_work_from_home=True,
    wfh_requested=True,
    wfh_request_ip="192.168.1.100",
    wfh_approval_status="pending",
    attendance_validated=False
)
print(f"✅ Created test WFH attendance (ID: {attendance.id})")

print("\n📝 Test Data Summary:")
print(f"Manager: {manager.get_full_name()} (ID: {manager.id})")
print(f"Employee: {employee.get_full_name()} (ID: {employee.id})")
print(f"WFH Attendance ID: {attendance.id}")
print(f"\nNow login as manager and visit:")
print("http://127.0.0.1:8000/attendance/wfh-pending-requests/")
```

---

## Step 5: Manual Browser Testing Checklist

### Pre-flight Check:
- [ ] Server running: `python manage.py runserver`
- [ ] IP restriction enabled
- [ ] Test employee has reporting manager set
- [ ] Test employee can login

### Test Checklist:

#### Employee Tests:
- [ ] Check-in from office IP works normally (no prompt)
- [ ] Check-in from home IP shows WFH modal
- [ ] Clicking "No" closes modal without check-in
- [ ] Clicking "Yes" creates WFH attendance with pending status
- [ ] Pending message shows after WFH check-in
- [ ] Can check-out normally after WFH check-in

#### Manager Tests:
- [ ] Can access `/attendance/wfh-pending-requests/`
- [ ] Pending requests display correctly
- [ ] Employee details show (avatar, name, position)
- [ ] IP address is visible
- [ ] Date and time display correctly
- [ ] "Approve" button works and validates attendance
- [ ] "Reject" button works and deletes attendance
- [ ] Success/warning messages appear
- [ ] Rows fade out after action
- [ ] Empty state shows when no pending requests

---

## Troubleshooting

### Issue: "No module named 'django'"
**Solution:** Activate virtual environment first
```bash
source venv/Scripts/activate
```

### Issue: Modal doesn't appear
**Solution:** Check browser console for JavaScript errors. Ensure HTMX is loaded.

### Issue: Can't access pending requests page
**Solution:** Ensure logged-in user has employee record with subordinates

### Issue: Migration errors
**Solution:** Update migration dependency
```python
# In attendance/migrations/0001_add_wfh_fields.py
# Change:
('attendance', '__latest__'),
# To:
('attendance', 'YOUR_LAST_MIGRATION_NUMBER'),
```

### Issue: IP not detected correctly
**Solution:** Check if behind proxy. The view checks `HTTP_X_FORWARDED_FOR` first.

---

## Expected Console Output (Success)

When testing approval:
```
✅ IP restriction enabled
✅ Set John Manager as manager for Jane Employee
✅ Created test WFH attendance (ID: 123)

📝 Test Data Summary:
Manager: John Manager (ID: 1)
Employee: Jane Employee (ID: 2)
WFH Attendance ID: 123

Now login as manager and visit:
http://127.0.0.1:8000/attendance/wfh-pending-requests/
```

---

## Quick Test Commands

```bash
# Start server
python manage.py runserver

# In another terminal - watch database changes
python manage.py shell
>>> from attendance.models import Attendance
>>> Attendance.objects.filter(wfh_requested=True).values('id', 'employee_id__employee_first_name', 'wfh_approval_status', 'attendance_validated')
```

---

## Next Steps After Testing

1. ✅ Verify all test scenarios pass
2. 🎨 Customize modal styling to match your theme
3. 📧 Add email notifications to managers when WFH requested
4. 📊 Add WFH statistics to dashboard
5. 🔔 Add badge count for pending requests in navigation
6. 📱 Test on mobile devices
7. 🌐 Test with actual different IPs (not simulated)

---

## Support

If you encounter issues:
1. Check Django logs
2. Check browser console
3. Verify database state with shell commands above
4. Ensure HTMX is working (check other HTMX features)
