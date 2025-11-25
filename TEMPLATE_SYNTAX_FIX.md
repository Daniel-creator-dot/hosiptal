# ✅ Template Syntax Error - FIXED

## 🐛 **Error**

```
TemplateSyntaxError at /hms/hr/leave/approvals/

Could not parse the remainder: ' if leave.staff.department else '-'' 
from 'leave.staff.department.name if leave.staff.department else '-''
```

**Location:** `hospital/templates/hospital/leave_approval_list.html`

---

## ❌ **Problem**

Django template language doesn't support Python-style inline if-else (ternary operators).

**Incorrect Syntax (Python style):**
```django
{{ leave.staff.department.name if leave.staff.department else '-' }}
```

---

## ✅ **Solution**

Use Django template tags instead:

**Correct Syntax (Django style):**
```django
{% if leave.staff.department %}{{ leave.staff.department.name }}{% else %}-{% endif %}
```

---

## 🔧 **Fixed Lines**

### **Line 69:**
```django
<!-- Before (WRONG) -->
<td>{{ leave.staff.department.name if leave.staff.department else '-' }}</td>

<!-- After (CORRECT) -->
<td>{% if leave.staff.department %}{{ leave.staff.department.name }}{% else %}-{% endif %}</td>
```

### **Line 168:**
```django
<!-- Before (WRONG) -->
<strong>{{ leave.staff.department.name if leave.staff.department else '-' }}</strong>

<!-- After (CORRECT) -->
<strong>{% if leave.staff.department %}{{ leave.staff.department.name }}{% else %}-{% endif %}</strong>
```

---

## 📚 **Django Template Syntax Reference**

### **Conditional Display - Three Options:**

#### **Option 1: Full If-Else (Best for complex logic)**
```django
{% if variable %}
    {{ variable.property }}
{% else %}
    Default Value
{% endif %}
```

#### **Option 2: Default Filter (Best for simple defaults)**
```django
{{ variable.property|default:"-" }}
```
**Note:** Only works if `variable.property` is None or empty.

#### **Option 3: Default If None (Stricter)**
```django
{{ variable.property|default_if_none:"-" }}
```
**Note:** Only triggers on `None`, not empty strings.

---

## ⚠️ **Common Mistakes**

### **❌ Don't Use Python Syntax:**
```django
{{ value if condition else default }}           <!-- WRONG -->
{{ value1 or value2 }}                          <!-- WRONG -->
{{ condition and value }}                       <!-- WRONG -->
{{ list[0] }}                                   <!-- WRONG -->
```

### **✅ Use Django Syntax:**
```django
{% if condition %}{{ value }}{% else %}{{ default }}{% endif %}  <!-- CORRECT -->
{{ value1|default:value2 }}                                      <!-- CORRECT -->
{% if condition %}{{ value }}{% endif %}                         <!-- CORRECT -->
{{ list.0 }}                                                     <!-- CORRECT -->
```

---

## 🧪 **Test**

**Test URL:**
```
http://127.0.0.1:8000/hms/hr/leave/approvals/
```

**Expected Result:**
- ✅ Page loads without error
- ✅ Department column shows department name or "-"
- ✅ Modal details show department or "-"

---

## ✅ **Status: FIXED**

✅ Template syntax corrected  
✅ System check passed  
✅ Page accessible  
✅ No errors  

**Ready to use!** 🚀
































