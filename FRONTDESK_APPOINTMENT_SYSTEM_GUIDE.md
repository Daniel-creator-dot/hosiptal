# Front Desk Appointment Management System with SMS Notifications

## Overview
A comprehensive appointment management system designed for front desk staff to create, manage, and track patient appointments with automatic SMS notifications.

## Features

### ✅ Core Functionality
1. **Appointment Creation with SMS Notification**
   - Create appointments for patients
   - Automatic SMS confirmation sent to patient's phone
   - Select provider (doctor), department, date/time, and duration
   - Add reason for visit and additional notes

2. **Dashboard View**
   - View today's appointments at a glance
   - Real-time statistics (scheduled, confirmed, completed, cancelled, no-show)
   - Upcoming appointments for next 7 days
   - Filter appointments by status
   - Color-coded status badges

3. **Appointment Management**
   - View detailed appointment information
   - Confirm appointments (with SMS notification)
   - Complete appointments
   - Cancel appointments (with SMS notification)
   - Mark as no-show
   - Edit appointment details (with SMS update notification)
   - Resend SMS reminders

4. **Search and Filtering**
   - Search by patient name, MRN, or reason
   - Filter by status, department, provider, date range
   - Pagination support for large lists

## Access URLs

### Main Pages
- **Dashboard**: `/hms/frontdesk/appointments/`
- **Create Appointment**: `/hms/frontdesk/appointments/create/`
- **All Appointments**: `/hms/frontdesk/appointments/list/`
- **Appointment Details**: `/hms/frontdesk/appointments/<appointment-id>/`
- **Edit Appointment**: `/hms/frontdesk/appointments/<appointment-id>/edit/`

## How to Use

### 1. Access the Front Desk Appointment Dashboard
```
Navigate to: http://localhost:8000/hms/frontdesk/appointments/
```

You'll see:
- Statistics cards showing today's appointment counts by status
- List of today's appointments with times, patient info, and status
- Upcoming appointments sidebar
- Quick action buttons

### 2. Create a New Appointment

**Step-by-Step:**

1. Click "**Create New Appointment**" button (top right)
2. Fill in the form:
   - **Patient**: Select from dropdown (required)
   - **Provider (Doctor)**: Choose the healthcare provider (required)
   - **Department**: Select department (required)
   - **Date & Time**: Choose appointment date and time (required)
   - **Duration**: Set appointment length in minutes (default: 30)
   - **Reason for Visit**: Describe why the patient is visiting (required)
   - **Additional Notes**: Optional notes for internal use

3. Click "**Create Appointment & Send SMS**"

**What Happens Next:**
- Appointment is saved to the database
- SMS notification is automatically sent to the patient's phone number
- Success message displays:
  - ✅ If SMS sent: "Appointment created successfully! SMS confirmation sent to [phone number]"
  - ⚠️ If SMS failed: "Appointment created, but SMS failed to send: [error message]"
  - ℹ️ If no phone: "Appointment created successfully. No phone number on file - SMS not sent."

### 3. View Appointment Details

1. From the dashboard or list view, click the eye icon (👁️) next to an appointment
2. View complete appointment information:
   - Patient details (name, MRN, phone, email)
   - Provider and department
   - Date, time, duration
   - Reason for visit
   - SMS reminder status

3. Perform actions:
   - **Confirm Appointment**: Changes status to confirmed and sends SMS
   - **Mark as Completed**: Updates status when patient visit is done
   - **Mark as No-Show**: Records when patient doesn't arrive
   - **Cancel Appointment**: Cancels and sends SMS notification to patient
   - **Resend SMS Reminder**: Sends another SMS reminder
   - **Edit Appointment**: Modify details (sends update SMS)

### 4. Manage Appointments

**Filter Today's Appointments by Status:**
- Click status buttons: All, Scheduled, Confirmed, Completed, Cancelled
- View only appointments with selected status

**Search All Appointments:**
1. Go to "View All Appointments"
2. Use search box: Enter patient name, MRN, or reason
3. Apply filters:
   - Status dropdown
   - Department dropdown
   - Date range (from/to)
4. Click "Filter" button

### 5. Edit an Appointment

1. Click the edit icon (✏️) or "Edit Appointment" button
2. Update any fields as needed
3. Click "Create Appointment & Send SMS"
4. Patient receives SMS notification about the update

## SMS Notification Templates

### New Appointment Confirmation
```
Dear [Patient First Name],

Your appointment with Dr. [Provider Name]
is scheduled for [Date] at [Time].

Please arrive 15 minutes early.

Reply STOP to opt out.
```

### Appointment Update
```
Dear [Patient First Name],

Your appointment has been updated:
Date: [Date] at [Time]
Provider: Dr. [Provider Name]
Department: [Department Name]

Please arrive 15 minutes early.

PrimeCare Medical Center
```

### Appointment Cancellation
```
Dear [Patient First Name],

Your appointment on [Date] at [Time]
has been cancelled.

Please contact us to reschedule.

PrimeCare Medical Center
```

## Appointment Status Workflow

```
Scheduled → Confirmed → Completed
           ↓
       Cancelled / No Show
```

### Status Definitions
- **Scheduled**: Initial status when appointment is created
- **Confirmed**: Patient has confirmed they will attend (via phone or SMS)
- **Completed**: Patient attended and appointment is finished
- **Cancelled**: Appointment was cancelled by staff or patient
- **No Show**: Patient did not arrive for scheduled appointment

## Tips for Front Desk Staff

### Best Practices
1. **Always verify patient phone number** before creating appointments
2. **Confirm appointments** 24 hours before scheduled time
3. **Update status** immediately after patient arrival or no-show
4. **Add clear reasons** for visit to help providers prepare
5. **Use notes field** for special instructions (e.g., "Bring previous lab results")

### SMS Sending Conditions
- SMS is only sent if patient has a valid phone number
- Phone number must be in format: +[country code][number] or local format
- Check SMS status in appointment details page
- If SMS fails, patient's phone number may be invalid or service may be unavailable

### Common Actions
- **Patient arrived?** → Confirm appointment (if not already confirmed)
- **Patient completed visit?** → Mark as completed
- **Patient didn't show up?** → Mark as no-show after 15 minutes
- **Need to reschedule?** → Edit appointment (patient gets update SMS)
- **Patient cancels?** → Cancel appointment (patient gets cancellation SMS)

## Troubleshooting

### SMS Not Sending?
**Check:**
1. Does patient have a phone number in their profile?
2. Is the phone number in correct format?
3. Is SMS API configured in settings?
4. Check SMS logs in admin panel for error details

### Cannot Find Patient?
- Make sure patient is registered in the system first
- Go to "Patients" → "New Patient" to register
- Search by MRN or name to verify

### Appointment Not Showing?
- Check selected filters (status, date range)
- Clear filters and search again
- Verify appointment wasn't deleted

## Integration with Other Modules

### Patient Management
- Click patient name to view full patient profile
- Create appointments directly from patient detail page
- View all patient appointments in one place

### Provider Calendar
- Appointments appear in provider's calendar
- Helps avoid double-booking
- Shows provider availability

### Reporting
- Appointment statistics tracked for reports
- No-show rates calculated
- Department performance metrics

## SMS Configuration

### Required Settings (already configured)
```python
# SMS Notify GH API Configuration
SMS_API_KEY = '84c879bb-f9f9-4666-84a8-9f70a9b238cc'
SMS_SENDER_ID = 'PrimeCare'
SMS_API_URL = 'https://sms.smsnotifygh.com/smsapi'
```

### SMS Service Provider
Using: **SMS Notify GH** (Ghana SMS Gateway)
- Reliable delivery
- Supports local and international numbers
- Automatic retry on failure
- Detailed delivery reports

## Quick Reference Card

| Task | URL | Button/Action |
|------|-----|---------------|
| View Dashboard | `/hms/frontdesk/appointments/` | Dashboard sidebar |
| Create Appointment | `/hms/frontdesk/appointments/create/` | "Create New Appointment" |
| View All | `/hms/frontdesk/appointments/list/` | "View All Appointments" |
| View Details | Click eye icon | From dashboard or list |
| Edit Appointment | Click pencil icon | From list or detail page |
| Confirm | Detail page | "Confirm Appointment" |
| Complete | Detail page | "Mark as Completed" |
| Cancel | Detail page | "Cancel Appointment" |
| Resend SMS | Detail page | "Resend SMS Reminder" |

## Support

### Need Help?
- Contact IT Support
- Check system logs: `logs/django.log`
- View SMS logs in Django Admin: `/admin/hospital/smslog/`

### Reporting Issues
When reporting issues, include:
1. What you were trying to do
2. Error message (if any)
3. Patient MRN or appointment ID
4. Screenshot (if applicable)

---

**System Version**: 1.0  
**Last Updated**: November 6, 2025  
**Module**: Front Desk Appointment Management with SMS Notifications






















