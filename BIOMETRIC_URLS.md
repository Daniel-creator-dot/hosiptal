# 🔐 BIOMETRIC AUTHENTICATION SYSTEM - URL GUIDE

## 📍 ALL AVAILABLE URLS

### **Frontend User Interfaces**

#### 1. **Biometric Login Portal**
- **URL**: `http://127.0.0.1:8000/hms/biometric/login/`
- **Purpose**: Staff authentication using Face or Fingerprint
- **Features**:
  - Face Recognition (multi-camera)
  - Fingerprint (upload/external device)
  - Auto-redirect after successful login
  - Attendance tracking integration

#### 2. **Staff Enrollment Interface**
- **URL**: `http://127.0.0.1:8000/hms/biometric/enrollment/`
- **Purpose**: Enroll staff biometric data
- **Features**:
  - Face Recognition enrollment
  - Fingerprint enrollment
  - Multi-camera selection
  - External device support
  - Quality score validation
  - Real-time preview

#### 3. **My Biometric Profile** (Staff Personal View)
- **URL**: `http://127.0.0.1:8000/hms/biometric/my-profile/`
- **Purpose**: Staff view their own enrolled biometrics
- **Features**:
  - View enrolled biometric types
  - Check quality scores
  - See enrollment dates
  - Request re-enrollment

#### 4. **Biometric Dashboard** (Analytics)
- **URL**: `http://127.0.0.1:8000/hms/biometric/dashboard/`
- **Purpose**: Analytics and statistics
- **Features**:
  - Enrollment statistics
  - Authentication success rates
  - Device performance metrics
  - Security alerts

#### 5. **Biometric Reports**
- **URL**: `http://127.0.0.1:8000/hms/biometric/reports/`
- **Purpose**: Generate biometric reports
- **Features**:
  - Authentication logs
  - Enrollment reports
  - Security audit reports

---

### **Admin Panel (Django Admin)**

#### 6. **Biometric Types Management**
- **URL**: `http://127.0.0.1:8000/admin/hospital/biometrictype/`
- **Purpose**: Manage available biometric types
- **Features**:
  - Enable/disable biometric types
  - Configure confidence thresholds
  - Set lockout parameters
  - View enrolled staff count

#### 7. **Staff Biometrics Management**
- **URL**: `http://127.0.0.1:8000/admin/hospital/staffbiometric/`
- **Purpose**: View all enrolled biometrics
- **Features**:
  - See all staff enrollments
  - Filter by type/status
  - View quality scores
  - Activate/deactivate biometrics
  - Unlock locked accounts

#### 8. **Authentication Logs**
- **URL**: `http://127.0.0.1:8000/admin/hospital/biometricauthenticationlog/`
- **Purpose**: Comprehensive audit trail
- **Features**:
  - All authentication attempts
  - Success/failure status
  - Confidence scores
  - Device information
  - Location tracking
  - Security flags

#### 9. **Biometric Devices**
- **URL**: `http://127.0.0.1:8000/admin/hospital/biometricdevice/`
- **Purpose**: Manage biometric capture devices
- **Features**:
  - Register devices
  - Track device status
  - Monitor performance
  - View statistics
  - Device heartbeat monitoring

#### 10. **Enrollment Sessions**
- **URL**: `http://127.0.0.1:8000/admin/hospital/biometricenrollmentsession/`
- **Purpose**: Track enrollment sessions
- **Features**:
  - Session history
  - Sample progress
  - Quality tracking
  - Success/failure analysis

#### 11. **Security Alerts**
- **URL**: `http://127.0.0.1:8000/admin/hospital/biometricsecurityalert/`
- **Purpose**: Security monitoring
- **Features**:
  - Spoofing attempts
  - Multiple failures
  - Unusual locations
  - Device malfunctions
  - Alert resolution

#### 12. **System Settings**
- **URL**: `http://127.0.0.1:8000/admin/hospital/biometricsystemsettings/`
- **Purpose**: Global configuration
- **Features**:
  - Enable/disable system
  - Liveness detection settings
  - Template expiry
  - Attendance integration
  - Alert configuration

---

### **API Endpoints** (For Integration)

#### 13. **Authentication API**
- **URL**: `http://127.0.0.1:8000/hms/biometric/api/authenticate/`
- **Method**: POST
- **Purpose**: Authenticate staff via API
- **Payload**:
  ```json
  {
    "image_data": "base64_encoded_image",
    "biometric_type_id": "uuid",
    "location": "string",
    "device_id": "string" (optional)
  }
  ```

#### 14. **Enrollment API**
- **URL**: `http://127.0.0.1:8000/hms/biometric/api/enroll/`
- **Method**: POST
- **Purpose**: Enroll staff biometric via API
- **Payload**:
  ```json
  {
    "staff_id": "uuid",
    "biometric_type_id": "uuid",
    "image_data": "base64_encoded_image",
    "location": "string",
    "device_id": "string" (optional)
  }
  ```

#### 15. **Device Heartbeat API**
- **URL**: `http://127.0.0.1:8000/hms/biometric/api/device/heartbeat/`
- **Method**: POST
- **Purpose**: Device health monitoring
- **Payload**:
  ```json
  {
    "device_id": "string",
    "status": "online/offline"
  }
  ```

---

## 🎯 QUICK ACCESS FROM DASHBOARDS

### **Admin Dashboard** → `/hms/admin-dashboard/`
- Biometric Security System section (purple gradient)
- 4 Quick access cards
- Direct links to all features

### **Staff Dashboard** → `/hms/staff-dashboard/`
- Quick Actions section
- Biometric Login button
- My Biometric Profile button

### **Main Dashboard** → `/hms/dashboard/`
- Quick Actions grid
- Biometric Enroll (purple card)
- Biometric Login (purple card)

---

## 🔌 SUPPORTED BIOMETRIC TYPES

### **Currently Active:**
- ✅ **Face Recognition** - FaceNet512 with Cosine Similarity
- ✅ **Fingerprint** - Image-based template matching

### **Available (Currently Inactive):**
- ⚪ **Iris Scan** - Can be activated in admin
- ⚪ **Voice Recognition** - Can be activated in admin
- ⚪ **Palm Print** - Can be activated in admin

To activate additional biometric types:
`http://127.0.0.1:8000/admin/hospital/biometrictype/` → Edit type → Set "Is Active" to True

---

## 📱 EXTERNAL DEVICE SUPPORT

### **Compatible Devices:**
- USB Fingerprint Scanners (all major brands)
- Multiple webcams/cameras
- IP cameras (if configured as system device)
- Virtual cameras (OBS, ManyCam, etc.)

### **How to Use External Fingerprint Scanner:**
1. Connect scanner to PC
2. Scan fingerprint using scanner software
3. Save image (PNG/JPG/BMP)
4. Go to enrollment page
5. Select "Fingerprint" type
6. Upload scanned image
7. Click "Enroll Fingerprint"

---

## 🛠️ ADMIN FEATURES

### **All Admin URLs:**
```
/admin/hospital/biometrictype/              - Manage biometric types
/admin/hospital/staffbiometric/             - View enrolled biometrics
/admin/hospital/biometricauthenticationlog/ - Authentication logs
/admin/hospital/biometricdevice/            - Device management
/admin/hospital/biometricenrollmentsession/ - Enrollment sessions
/admin/hospital/biometricsecurityalert/     - Security alerts
/admin/hospital/biometricsystemsettings/    - System settings
```

### **Configuration Options:**
- Confidence thresholds
- Liveness detection settings
- Failed attempt limits
- Lockout duration
- Template expiry
- Attendance integration
- Alert recipients

---

## 🎯 COMMON WORKFLOWS

### **Enroll New Staff:**
```
1. Login as admin
2. Go to: /hms/biometric/enrollment/
3. Select staff from list
4. Choose biometric type (Face or Fingerprint)
5. Select device/camera
6. Capture biometric data
7. Wait for success confirmation
```

### **Staff Login:**
```
1. Go to: /hms/biometric/login/
2. Select biometric type
3. Position face/finger
4. Click authenticate
5. Automatic redirect on success
```

### **View Audit Logs:**
```
1. Go to: /admin/hospital/biometricauthenticationlog/
2. Filter by date/staff/status
3. Export reports
4. Analyze patterns
```

### **Manage Devices:**
```
1. Go to: /admin/hospital/biometricdevice/
2. Add new device
3. Configure supported biometrics
4. Monitor device health
5. View statistics
```

---

## 🔒 SECURITY FEATURES

- ✅ Liveness detection (anti-spoofing)
- ✅ Quality score validation
- ✅ Confidence threshold enforcement
- ✅ Failed attempt tracking
- ✅ Automatic account lockout
- ✅ Comprehensive audit logging
- ✅ Security alerts
- ✅ Device authentication
- ✅ Location tracking
- ✅ IP address logging

---

## 📊 ALL FEATURES AT A GLANCE

| Feature | URL | Access Level |
|---------|-----|--------------|
| Enrollment | `/hms/biometric/enrollment/` | Admin/HR |
| Login | `/hms/biometric/login/` | All Staff |
| My Profile | `/hms/biometric/my-profile/` | Staff |
| Dashboard | `/hms/biometric/dashboard/` | Admin |
| Reports | `/hms/biometric/reports/` | Admin |
| Auth Logs | `/admin/hospital/biometricauthenticationlog/` | Admin |
| Device Mgmt | `/admin/hospital/biometricdevice/` | Admin |
| Security Alerts | `/admin/hospital/biometricsecurityalert/` | Admin |
| Settings | `/admin/hospital/biometricsystemsettings/` | Superuser |

---

**Last Updated:** November 11, 2025
**System Version:** HMS Biometric Authentication v1.0
**Supported Types:** Face Recognition, Fingerprint




















