# Quick Start Testing Guide for WFH Feature

## ✅ Verification Complete!
All implementation files are correctly in place.

---

## 🚀 How to Test (5 Simple Steps)

### Step 1: Set Up Virtual Environment

```bash
# Create virtual environment (if you don't have one)
python -m venv venv

# Activate it
source venv/Scripts/activate  # Git Bash on Windows
# OR
venv\Scripts\activate  # CMD on Windows
```

### Step 2: Install Dependencies & Run Migrations

```bash
# Install requirements (if not already done)
pip install -r requirements.txt

# Apply migrations
python manage.py makemigrations
python manage.py migrate
```

### Step 3: Set Up Test Data

```bash
# Run the test setup script
python setup_wfh_test.py
```

This script will:
- ✅ Enable IP restriction (office IP: 182.77.58.234)
- ✅ Set up a manager-employee relationship
- ✅ Create a test WFH attendance request

**Expected Output:**
```
==============================================================
Setting up Work From Home Test Environment
==============================================================

Step 1: Configuring IP Restriction...
   ✅ IP restriction enabled for office IP: 182.77.58.234

Step 2: Setting up test users...
   Manager: John Doe (ID: 1)
   Employee: Jane Smith (ID: 2)

... (more output)

✅ TEST ENVIRONMENT READY!
```

### Step 4: Start the Server

```bash
python manage.py runserver
```

Server will start at: `http://127.0.0.1:8000`

### Step 5: Test the Feature!

#### 🧪 Test A: Manager Approval Interface

1. **Login as the manager** (from setup_wfh_test.py output)
2. Navigate to: `http://127.0.0.1:8000/attendance/wfh-pending-requests/`
3. You should see:
   - ✅ A table with 1 pending WFH request
   - ✅ Employee name, avatar, date, time, IP address
   - ✅ Two buttons: "Approve" and "Reject"

4. **Click "Approve"**
   - ✅ Row turns green with success message
   - ✅ Row fades out after 2 seconds
   - ✅ Request disappears from list

#### 🧪 Test B: Employee Check-in (Manual Test)

**Test B1: Check-in from Office IP (Normal Flow)**

1. Login as employee
2. Go to attendance page
3. Click "Check-In"
4. **Expected:** Normal check-in, no WFH prompt ✅

> **Note:** To test this properly, you'll need to temporarily modify the code to simulate the office IP, or actually be on the office network.

**Test B2: Check-in from Home IP (WFH Flow)**

To simulate checking in from home:

1. Temporarily edit `attendance/views/clock_in_out.py` line ~230:
   ```python
   # Change:
   ip = request.META.get("REMOTE_ADDR")
   
   # To (for testing):
   ip = "192.168.1.100"  # Simulated home IP
   ```

2. Login as employee
3. Go to attendance page
4. Click "Check-In"
5. **Expected:** Modal appears asking "Are you working from home?"
6. **Click "Yes"**
7. **Expected:** 
   - Check-in succeeds
   - Alert shows: "Your work from home attendance is pending approval"
   - Can click Check-Out normally

8. Login as manager
9. Go to `/attendance/wfh-pending-requests/`
10. **Expected:** New WFH request appears
11. Click "Approve" or "Reject"

---

## 🎯 What to Look For

### ✅ Success Indicators:

1. **IP Restriction Works:**
   - Office IP (182.77.58.234) → Normal check-in
   - Other IPs → WFH prompt appears

2. **WFH Prompt Modal:**
   - Shows employee's IP address
   - Has "No" and "Yes" buttons
   - Clicking "No" closes modal without check-in
   - Clicking "Yes" creates pending attendance

3. **Manager Approval Page:**
   - Shows all pending WFH requests
   - Displays employee details
   - Approve button validates attendance
   - Reject button deletes attendance

4. **Database Verification:**
   ```bash
   python manage.py shell
   ```
   ```python
   from attendance.models import Attendance
   
   # Check pending WFH requests
   wfh_requests = Attendance.objects.filter(wfh_requested=True)
   for req in wfh_requests:
       print(f"Employee: {req.employee_id.get_full_name()}")
       print(f"Status: {req.wfh_approval_status}")
       print(f"Validated: {req.attendance_validated}")
       print(f"IP: {req.wfh_request_ip}")
       print("---")
   ```

---

## 🔧 Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'django'"
**Solution:** Activate virtual environment first
```bash
source venv/Scripts/activate
```

### Problem: "Need at least 2 employees"
**Solution:** Create employees through Django admin:
1. Go to `http://127.0.0.1:8000/admin`
2. Create at least 2 employees with work info

### Problem: Modal doesn't show up
**Solution:** Check browser console (F12) for JavaScript errors

### Problem: Can't see pending requests page
**Solution:** 
- Ensure logged-in user is a reporting manager
- Ensure at least one employee reports to them

### Problem: Migration already exists
**Solution:** 
```bash
# If you get migration conflicts
python manage.py migrate --fake attendance 0001_add_wfh_fields
```

---

## 📊 Test Checklist

Copy this checklist and mark items as you test:

```
Employee Tests:
[ ] Check-in from office IP works normally
[ ] Check-in from home IP shows WFH modal
[ ] Modal shows correct IP address
[ ] "No" button closes modal
[ ] "Yes" button creates pending attendance
[ ] Pending message shows after WFH check-in
[ ] Can check-out after WFH check-in

Manager Tests:
[ ] Can access pending requests page
[ ] Pending requests display correctly
[ ] Employee details show (name, avatar, position)
[ ] IP address is visible
[ ] Date and time are correct
[ ] "Approve" button works
[ ] "Reject" button works
[ ] Success/warning messages appear
[ ] Rows fade out after action

Database Tests:
[ ] WFH attendance has correct fields set
[ ] Approval changes attendance_validated
[ ] Rejection deletes attendance record
```

---

## 📸 What You Should See

### 1. WFH Confirmation Modal
```
┌─────────────────────────────────────────┐
│         Work From Home?                 │
├─────────────────────────────────────────┤
│ You are checking in from a different   │
│ IP address (192.168.1.100).            │
│                                         │
│ Are you working from home?              │
│                                         │
│ Your attendance will be marked as       │
│ pending until approved by your          │
│ reporting manager.                      │
├─────────────────────────────────────────┤
│        [No]          [Yes]              │
└─────────────────────────────────────────┘
```

### 2. Manager Approval Page
```
┌────────────────────────────────────────────────────────┐
│  Work From Home Approval Requests                      │
├────────────────────────────────────────────────────────┤
│ Employee    Date        Time   IP           Actions    │
├────────────────────────────────────────────────────────┤
│ Jane Smith  31 Mar 26  09:00  192.168.1.100           │
│ Developer                       [Approve] [Reject]     │
└────────────────────────────────────────────────────────┘
```

---

## 🎉 Success!

If all tests pass, you have successfully implemented and tested the Work From Home approval feature!

### What's Working:
✅ IP-based detection of remote check-ins
✅ Employee WFH confirmation prompt
✅ Pending status for WFH attendance
✅ Manager approval workflow
✅ Automatic validation on approval
✅ Record deletion on rejection

---

## 📚 Additional Resources

- **Full Testing Guide:** `TEST_WFH_FEATURE.md` (detailed scenarios)
- **Setup Script:** `setup_wfh_test.py` (quick test data)
- **Verification:** `verify_wfh_implementation.py` (check files)

---

## 🤝 Need Help?

If you encounter issues:
1. Check Django server logs
2. Check browser console (F12)
3. Run verification script: `python verify_wfh_implementation.py`
4. Verify database state using Django shell commands above
