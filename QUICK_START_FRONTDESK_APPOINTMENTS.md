# Quick Start Guide: Front Desk Appointments with SMS

## 🚀 Getting Started (2 Minutes)

### Step 1: Access the System
1. Open your browser
2. Navigate to: **http://localhost:8000/hms/frontdesk/appointments/**
3. Login with your credentials

### Step 2: Create Your First Appointment

**Click**: "Create New Appointment" (top right corner)

**Fill in the form:**
```
✅ Patient: Select patient from dropdown
✅ Provider: Choose the doctor
✅ Department: Select department
✅ Date & Time: Pick appointment date/time
✅ Duration: Enter minutes (default: 30)
✅ Reason: Type reason for visit
📝 Notes: Optional additional info
```

**Click**: "Create Appointment & Send SMS"

### Step 3: Verify SMS Sent
Look for success message:
- ✅ Green message = SMS sent successfully!
- ⚠️ Yellow message = Appointment created but SMS failed
- ℹ️ Blue message = No phone number on file

## 📱 SMS Examples

### Patient Receives:
```
Dear John,

Your appointment with Dr. Smith
is scheduled for 15/11/2025 at 10:30 AM.

Please arrive 15 minutes early.

Reply STOP to opt out.
```

## 🎯 Common Tasks (Quick Reference)

| I want to... | Do this... |
|--------------|------------|
| **Create appointment** | Dashboard → "Create New Appointment" |
| **View today's schedule** | Go to dashboard (shows automatically) |
| **Find an appointment** | "View All Appointments" → Search |
| **Confirm appointment** | Click appointment → "Confirm Appointment" |
| **Cancel appointment** | Click appointment → "Cancel Appointment" |
| **Resend SMS** | Click appointment → "Resend SMS Reminder" |
| **Update appointment** | Click pencil icon → Edit → Save |

## ⚡ Pro Tips

1. **Before creating appointment**: Verify patient's phone number is correct
2. **Best practice**: Confirm appointments 24 hours before
3. **When patient arrives**: Mark as "Confirmed" or "Completed"
4. **If patient doesn't show**: Wait 15 minutes, then mark "No-Show"
5. **Need to change time?**: Edit appointment (patient gets update SMS)

## 🔍 Dashboard Features

### Statistics Cards (Top of Dashboard)
- **Total Today**: All appointments for today
- **Scheduled**: Awaiting confirmation
- **Confirmed**: Patient confirmed attendance
- **Completed**: Patient visited
- **Cancelled**: Cancelled appointments
- **No Show**: Patients who didn't arrive

### Status Filters
Click status buttons to filter view:
- All | Scheduled | Confirmed | Completed | Cancelled

### Today's Appointments
- Sorted by time
- Color-coded status badges
- One-click access to patient details
- Quick view of provider and department

### Upcoming Sidebar
- Shows next 7 days
- Quick preview of future appointments
- Fast access to details

## 📋 Appointment Status Guide

```
CREATE → Scheduled (SMS sent)
           ↓
CONFIRM → Confirmed (SMS sent)
           ↓
ATTEND → Completed
```

Or:

```
SCHEDULED → Cancelled (SMS sent)
         → No Show (no SMS)
```

## ❓ Troubleshooting Quick Fixes

### "SMS Failed to Send"
- ✅ Check: Patient has valid phone number
- ✅ Format: +233XXXXXXXXX or 0XXXXXXXXX
- ✅ Solution: Update patient phone, then "Resend SMS"

### "Can't Find Patient"
- ✅ Patient must be registered first
- ✅ Go to: Patients → New Patient
- ✅ Then return to create appointment

### "Appointment Not Visible"
- ✅ Check filters are not hiding it
- ✅ Click "Clear Filters"
- ✅ Search by patient MRN

## 🎨 Understanding Color Codes

| Color | Status | Meaning |
|-------|--------|---------|
| 🔵 Gray | Scheduled | Just created, needs confirmation |
| 🔵 Cyan | Confirmed | Patient confirmed they'll come |
| 🟢 Green | Completed | Visit finished |
| 🔴 Red | Cancelled | Appointment cancelled |
| 🟡 Yellow | No Show | Patient didn't arrive |

## 📞 SMS Notification Triggers

SMS automatically sent when:
1. ✅ **Creating** new appointment → Confirmation SMS
2. ✅ **Editing** appointment → Update SMS
3. ✅ **Cancelling** appointment → Cancellation SMS
4. ✅ **Confirming** appointment → Reminder SMS
5. ✅ **Clicking** "Resend SMS" → Reminder SMS

## 🔐 Access from Dashboard

1. Login to main dashboard
2. Look for "**Appointments**" section
3. Or navigate directly: `/hms/frontdesk/appointments/`

## 📚 Need More Details?

See full guide: `FRONTDESK_APPOINTMENT_SYSTEM_GUIDE.md`

---

**Ready to start?** Go to: http://localhost:8000/hms/frontdesk/appointments/

**Questions?** Contact IT Support

**Module**: Front Desk Appointment Management v1.0

























