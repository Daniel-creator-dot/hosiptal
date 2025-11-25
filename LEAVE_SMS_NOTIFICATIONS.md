# Leave SMS Notifications - Complete Guide

## ✅ **SMS NOTIFICATIONS INTEGRATED!**

Staff now receive **automatic SMS notifications** when their leave requests are approved or rejected!

---

## 📱 **SMS Notification Features**

### **3 Automatic Notifications:**

#### **1. Leave Approved ✅**
**Sent When:** Manager/Admin approves a leave request

**Message Content:**
```
Dear [Staff Name],

Your leave request has been APPROVED!

Type: Annual Leave
Dates: 01/12/2025 to 05/12/2025
Days: 5 day(s)

Enjoy your leave!

PrimeCare Hospital
```

**Triggered By:**
- Manager clicking "Approve" button
- Admin auto-approving when creating leave
- Any approval of pending leave request

---

#### **2. Leave Rejected ❌**
**Sent When:** Manager/Admin rejects a leave request

**Message Content:**
```
Dear [Staff Name],

Your leave request has been REJECTED.

Type: Sick Leave
Dates: 01/12/2025 to 03/12/2025

Reason: Medical certificate required for leaves > 3 days

Please contact your supervisor for clarification.

PrimeCare Hospital
```

**Triggered By:**
- Manager clicking "Reject" button (with reason)
- System includes rejection reason in SMS

---

#### **3. Leave Submitted (To Manager) 📨**
**Sent When:** Staff submits leave request for approval

**Message Content:**
```
Dear [Manager Name],

New leave request submitted by John Doe:

Type: Annual Leave
Dates: 15/12/2025 to 20/12/2025
Days: 6

Please review and approve/reject.

PrimeCare Hospital
```

**Triggered By:**
- Staff clicking "Submit for Approval"
- Leave status changes from Draft to Pending

**Sent To:**
- Department head (if assigned)
- HR department (fallback)

---

## 🔄 **Complete SMS Flow**

### **Workflow with SMS:**

```
Staff Creates Leave Request (Draft)
         ↓
Staff Clicks "Submit"
         ↓
[SMS] → Manager notified "New request from [Staff]"
         ↓
Manager Reviews Request
         ↓
         ├─ Approve ──→ [SMS] → Staff: "APPROVED! Enjoy your leave"
         │
         └─ Reject ───→ [SMS] → Staff: "REJECTED. Reason: [Reason]"
```

---

## 📊 **SMS Notification Matrix**

| Action | Who Gets SMS | Message Type | Trigger |
|--------|--------------|--------------|---------|
| **Staff submits leave** | Manager | leave_submitted | `submit()` method |
| **Manager approves** | Staff | leave_approved | `approve()` method |
| **Manager rejects** | Staff | leave_rejected | `reject()` method |
| **Admin creates & auto-approves** | Staff | leave_approved | Auto-approve ✅ |

---

## 🎯 **SMS Content Details**

### **What's Included in SMS:**

**All Leave SMS Include:**
- ✅ Staff/Manager first name (personalized)
- ✅ Leave type (Annual, Sick, etc.)
- ✅ Start and end dates (formatted dd/mm/yyyy)
- ✅ Number of days
- ✅ Hospital name/branding

**Approval SMS Includes:**
- ✅ "APPROVED" status
- ✅ Encouragement message
- ✅ Leave details

**Rejection SMS Includes:**
- ✅ "REJECTED" status
- ✅ Rejection reason (from manager)
- ✅ Next steps guidance

**Submission SMS Includes:**
- ✅ Staff name who submitted
- ✅ Request to review
- ✅ Leave details for quick assessment

---

## 🔧 **Technical Implementation**

### **How It Works:**

**1. Leave Approved:**
```python
# In LeaveRequest.approve() method
def approve(self, approver_staff, comments=''):
    # ... approve logic ...
    
    # Send SMS notification
    from services.sms_service import sms_service
    sms_service.send_leave_approved(self)
```

**2. Leave Rejected:**
```python
# In LeaveRequest.reject() method
def reject(self, approver_staff, reason):
    # ... reject logic ...
    
    # Send SMS notification
    sms_service.send_leave_rejected(self)
```

**3. Leave Submitted:**
```python
# In LeaveRequest.submit() method
def submit(self):
    # ... submit logic ...
    
    # Notify manager
    sms_service.send_leave_submitted(self)
```

---

## 📞 **Phone Number Handling**

### **Where Phone Numbers Come From:**

**For Staff:**
1. Check `staff.phone` field
2. Fallback to `staff.phone_number`
3. If none: Log failed SMS, don't send

**For Manager:**
1. Get department head
2. Check department head's phone
3. If none: Skip notification (no error)

### **Phone Number Format:**

**Accepted Formats:**
- `+233XXXXXXXXX` (International)
- `0XXXXXXXXX` (Local Ghana)
- `233XXXXXXXXX` (Without +)
- `XXXXXXXXX` (9 digits, auto-adds 233)

**Auto-Conversion:**
- Removes spaces, dashes, parentheses
- Adds country code (233) if missing
- Validates 12-digit format

---

## 🎨 **SMS Templates**

### **Template 1: Approved**
```
Dear {staff_first_name},

Your leave request has been APPROVED!

Type: {leave_type}
Dates: {start_date} to {end_date}
Days: {days_requested} day(s)

Enjoy your leave!

PrimeCare Hospital
```

### **Template 2: Rejected**
```
Dear {staff_first_name},

Your leave request has been REJECTED.

Type: {leave_type}
Dates: {start_date} to {end_date}

Reason: {rejection_reason}

Please contact your supervisor for clarification.

PrimeCare Hospital
```

### **Template 3: Submitted (To Manager)**
```
Dear {manager_name},

New leave request submitted by {staff_full_name}:

Type: {leave_type}
Dates: {start_date} to {end_date}
Days: {days_requested}

Please review and approve/reject.

PrimeCare Hospital
```

---

## 🔐 **Error Handling**

### **Graceful Degradation:**

**Scenario: Staff has no phone number**
```
Result: 
- SMS log created with status "failed"
- Error message: "Staff [Name] does not have a phone number"
- Leave approval still succeeds ✅
- No SMS sent, but leave is processed
```

**Scenario: SMS API is down**
```
Result:
- Error logged to system logs
- Leave approval still succeeds ✅
- SMS marked as failed
- Can retry later
```

**Scenario: Invalid phone number**
```
Result:
- SMS validation fails
- Error message logged
- Leave approval still succeeds ✅
```

**Key Principle:**
> **SMS failures NEVER block leave approvals!**  
> The leave process completes even if SMS fails.

---

## 📊 **SMS Logging & Tracking**

### **Every SMS Creates a Log:**

**SMSLog Record Includes:**
- Recipient phone number
- Recipient name
- Message content
- Message type (leave_approved, leave_rejected, leave_submitted)
- Status (pending → sent/failed)
- Sent timestamp
- Error message (if failed)
- Provider response
- Related leave request ID

### **View SMS Logs:**

**Admin Interface:**
```
Admin → Advanced → SMS Logs
```

**Filter By:**
- Message type
- Status (sent/failed)
- Date sent
- Recipient

**Use For:**
- Verify notifications sent
- Debug failed messages
- Audit trail
- Resend if needed

---

## 🎯 **Testing the SMS Feature**

### **Test 1: Approve Leave**
```
1. Have a pending leave request
2. Ensure staff has phone number in profile
3. Approve the leave request
4. Check: SMS log created
5. Verify: SMS sent (or failed with reason)
```

### **Test 2: Reject Leave**
```
1. Have a pending leave request
2. Reject with reason
3. Check SMS log
4. Staff should receive rejection SMS
```

### **Test 3: No Phone Number**
```
1. Staff without phone number
2. Approve their leave
3. Leave approved ✅
4. SMS log shows "failed" with reason
5. No error thrown
```

---

## ⚙️ **Configuration**

### **SMS Service Settings:**

**Current Configuration:**
```python
SMS_API_KEY = '3316dce1-fd2a-4b4e-b6b2-60b30be375bb'
SMS_SENDER_ID = 'PrimeCare'
SMS_API_URL = 'https://sms.smsnotifygh.com/smsapi'
```

**To Change Settings:**
Add to `hms/settings.py`:
```python
SMS_API_KEY = 'your-api-key'
SMS_SENDER_ID = 'HospitalName'
SMS_API_URL = 'your-sms-provider-url'
```

---

## 💡 **Use Cases**

### **Use Case 1: Emergency Leave Approved**
```
Admin creates emergency leave + auto-approve
    ↓
Staff immediately receives SMS:
"Your leave request has been APPROVED!
Type: Emergency Leave
Dates: 03/11/2025 to 05/11/2025
Days: 3 day(s)"
```

### **Use Case 2: Annual Leave Rejected (No Coverage)**
```
Manager rejects due to no coverage
    ↓
Staff receives SMS:
"Your leave request has been REJECTED.
Reason: No coverage available for requested dates.
Please contact your supervisor."
```

### **Use Case 3: Staff Submits Leave**
```
Staff submits leave request
    ↓
Manager receives SMS:
"New leave request from John Doe:
Type: Annual Leave
Dates: 15/12/2025 to 20/12/2025
Please review and approve/reject."
```

---

## 📈 **Benefits**

### **For Staff:**
- ✅ **Instant notification** - Know immediately
- ✅ **No login needed** - Get updates via SMS
- ✅ **Mobile friendly** - Check from anywhere
- ✅ **Peace of mind** - Confirmation received

### **For Managers:**
- ✅ **Quick alerts** - Know when requests come in
- ✅ **Faster processing** - Immediate awareness
- ✅ **Better communication** - Automatic updates
- ✅ **Less follow-up** - Staff informed automatically

### **For Organization:**
- ✅ **Professional** - Automated communications
- ✅ **Efficient** - Reduces phone calls/emails
- ✅ **Trackable** - All SMS logged
- ✅ **Reliable** - Fail-safe design

---

## 🎓 **Best Practices**

### **For Admins:**
1. ✅ **Ensure staff have phone numbers** in profiles
2. ✅ **Monitor SMS logs** for failed messages
3. ✅ **Keep SMS balance** topped up
4. ✅ **Test notifications** periodically
5. ✅ **Review failed messages** weekly

### **For Staff:**
1. ✅ **Update phone number** in profile
2. ✅ **Keep number active** to receive notifications
3. ✅ **Save important SMS** for records
4. ✅ **Reply STOP** only if you want to opt out

---

## 📊 **SMS Statistics**

### **Track Performance:**

**From Admin → SMS Logs:**
- Total SMS sent today
- Success rate
- Failed messages
- Leave notifications sent
- Most common errors

### **Key Metrics:**
- **Success Rate**: % of SMS delivered
- **Response Time**: API response time
- **Daily Volume**: SMS sent per day
- **Cost Tracking**: SMS costs per month

---

## ✅ **Verification Checklist**

After implementing, verify:

- [ ] Staff phone numbers in profiles
- [ ] SMS service configured
- [ ] Approve leave → SMS sent
- [ ] Reject leave → SMS sent
- [ ] Submit leave → Manager SMS sent
- [ ] Failed SMS logged (no phone)
- [ ] Leave still approved if SMS fails
- [ ] SMS logs viewable in admin

---

## 🎉 **Summary**

**SMS Notifications Now Active For:**

✅ **Leave Approved** - Staff notified instantly  
✅ **Leave Rejected** - Staff gets reason via SMS  
✅ **Leave Submitted** - Manager alerted to review  

**Key Features:**
- ✅ Automatic sending
- ✅ Personalized messages
- ✅ Error handling
- ✅ Complete logging
- ✅ Fail-safe design
- ✅ Phone format validation

**SMS Types Added:**
1. `leave_approved` - Approval notification
2. `leave_rejected` - Rejection notification
3. `leave_submitted` - Submission to manager

**Integration Points:**
- ✅ `LeaveRequest.approve()` - Sends SMS
- ✅ `LeaveRequest.reject()` - Sends SMS
- ✅ `LeaveRequest.submit()` - Sends SMS to manager

**Files Modified:**
- ✅ `hospital/services/sms_service.py` - Added 3 methods
- ✅ `hospital/models_advanced.py` - Integrated SMS calls

**Result:**
> **Staff get instant SMS notifications when their leave is approved/rejected!** 📱✅

---

## 🚀 **How to Test**

### **Test Approval SMS:**
```
1. Create leave request as staff (or admin creates)
2. Ensure staff has phone number
3. Approve the leave
4. Check: Staff receives SMS
5. Verify: Admin → SMS Logs shows "sent"
```

### **Test Rejection SMS:**
```
1. Have pending leave request
2. Reject with reason
3. Staff receives rejection SMS with reason
4. Check SMS logs
```

### **Test Without Phone:**
```
1. Staff without phone number
2. Approve their leave
3. Leave approved successfully ✅
4. SMS log shows "failed" - no phone number
5. System continues working
```

---

## 💼 **Provider Information**

**Current SMS Provider:** SMS Notify GH  
**API Endpoint:** https://sms.smsnotifygh.com/smsapi  
**Sender ID:** PrimeCare  
**Country:** Ghana (🇬🇭)  

**Supported Features:**
- International format support
- Delivery confirmation
- Error codes
- Balance checking

---

## 🎉 **COMPLETE!**

**Your leave system now has:**
- ✅ **Automatic SMS notifications**
- ✅ **Staff get approval/rejection alerts**
- ✅ **Managers get submission alerts**
- ✅ **Fail-safe design** (SMS failure doesn't block approval)
- ✅ **Complete logging** for audit trail
- ✅ **Professional messaging**

**Start using it now - notifications work automatically!** 🎊

---

**Created**: November 2025  
**Version**: 1.0  
**Status**: ✅ Active & Working
































