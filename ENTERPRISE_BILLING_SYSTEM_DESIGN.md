# 🏢 World-Class Enterprise Billing & Accounts Receivable System

## 📋 **Business Requirements**

### Your Needs:
1. **Corporate Clients**: Send consolidated monthly bills
2. **Insurance Companies**: Send consolidated monthly claims
3. **Multi-Tier Pricing**: 
   - Cash prices (walk-in patients)
   - Corporate prices (company employees)
   - Insurance prices (insured patients)
4. **Outstanding Tracking**: Age analysis, credit limits, payment terms
5. **Monthly Billing Cycles**: Automated invoice generation
6. **Professional Statements**: Detailed monthly statements

---

## 🎯 **Solution: Enterprise Billing System**

### Core Components:

```
┌─────────────────────────────────────────────────────────────┐
│                   ENTERPRISE BILLING SYSTEM                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Multi-Tier Pricing Engine                              │
│     ├─ Cash Price Book                                      │
│     ├─ Corporate Price Book (per company)                   │
│     └─ Insurance Price Book (per insurer)                   │
│                                                              │
│  2. Corporate Account Management                            │
│     ├─ Company Profiles                                     │
│     ├─ Employee Enrollment                                  │
│     ├─ Credit Limits & Terms                               │
│     └─ Monthly Billing Cycles                              │
│                                                              │
│  3. Insurance Claims Management                             │
│     ├─ Policy Verification                                 │
│     ├─ Pre-Authorization                                   │
│     ├─ Claims Batching                                     │
│     └─ Monthly Submission                                  │
│                                                              │
│  4. Accounts Receivable                                    │
│     ├─ Outstanding Balance Tracking                        │
│     ├─ Aging Analysis (30/60/90/120+ days)               │
│     ├─ Payment Terms Management                           │
│     └─ Collection Workflows                               │
│                                                              │
│  5. Monthly Billing Engine                                 │
│     ├─ Automated Invoice Generation                       │
│     ├─ Consolidated Statements                            │
│     ├─ Email/Print Distribution                           │
│     └─ Follow-up Reminders                                │
│                                                              │
│  6. Reporting & Analytics                                  │
│     ├─ Outstanding Reports                                 │
│     ├─ Revenue by Payer Type                              │
│     ├─ Collection Performance                             │
│     └─ Pricing Analysis                                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 **Database Schema**

### 1. Corporate Account Model
```python
class CorporateAccount(BaseModel):
    """Corporate/Company client with monthly billing"""
    
    # Company Information
    company_name = models.CharField(max_length=200, unique=True)
    company_code = models.CharField(max_length=20, unique=True)
    registration_number = models.CharField(max_length=50, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    
    # Contact Details
    billing_contact_name = models.CharField(max_length=200)
    billing_email = models.EmailField()
    billing_phone = models.CharField(max_length=20)
    billing_address = models.TextField()
    
    # Financial Terms
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2)
    payment_terms_days = models.IntegerField(default=30)  # Net 30
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('suspended', 'Suspended - Credit Limit Exceeded'),
            ('on_hold', 'On Hold - Payment Issues'),
            ('closed', 'Account Closed')
        ],
        default='active'
    )
    
    # Billing Settings
    billing_cycle = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Monthly - End of Month'),
            ('bi_weekly', 'Bi-Weekly'),
            ('custom', 'Custom Schedule')
        ],
        default='monthly'
    )
    next_billing_date = models.DateField()
    last_billing_date = models.DateField(null=True, blank=True)
    
    # Price Book
    price_book = models.ForeignKey('PriceBook', on_delete=models.SET_NULL, null=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Contract
    contract_start_date = models.DateField()
    contract_end_date = models.DateField(null=True, blank=True)
    contract_document = models.FileField(upload_to='contracts/', blank=True)
    
    # Contact Person
    account_manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Notifications
    send_statement_email = models.BooleanField(default=True)
    send_payment_reminders = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['company_name']
```

### 2. Corporate Employee Enrollment
```python
class CorporateEmployee(BaseModel):
    """Link between company employees and their corporate account"""
    
    corporate_account = models.ForeignKey('CorporateAccount', on_delete=models.CASCADE)
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE)
    
    employee_id = models.CharField(max_length=50)
    department = models.CharField(max_length=100, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    
    enrollment_date = models.DateField(auto_now_add=True)
    termination_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Coverage limits (if applicable)
    annual_limit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    utilized_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Dependents
    covers_dependents = models.BooleanField(default=False)
    dependent_limit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    class Meta:
        unique_together = ['corporate_account', 'patient']
```

### 3. Monthly Statement
```python
class MonthlyStatement(BaseModel):
    """Consolidated monthly bill for corporate/insurance"""
    
    # Account Details
    payer = models.ForeignKey('Payer', on_delete=models.CASCADE)
    corporate_account = models.ForeignKey('CorporateAccount', on_delete=models.CASCADE, null=True, blank=True)
    
    # Statement Period
    statement_number = models.CharField(max_length=50, unique=True)
    statement_date = models.DateField()
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Financial Summary
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_charges = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_payments = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_adjustments = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Line Items (services provided)
    # Related to StatementLine model
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('sent', 'Sent'),
            ('partially_paid', 'Partially Paid'),
            ('paid', 'Paid'),
            ('overdue', 'Overdue')
        ],
        default='draft'
    )
    
    # Due Date
    due_date = models.DateField()
    payment_terms = models.CharField(max_length=100, default='Net 30 days')
    
    # Distribution
    sent_date = models.DateTimeField(null=True, blank=True)
    sent_via = models.CharField(max_length=20, choices=[('email', 'Email'), ('post', 'Post'), ('both', 'Both')], default='email')
    
    # PDF
    pdf_file = models.FileField(upload_to='statements/', blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
```

### 4. Statement Line Items
```python
class StatementLine(BaseModel):
    """Individual service line on monthly statement"""
    
    statement = models.ForeignKey('MonthlyStatement', on_delete=models.CASCADE, related_name='lines')
    
    # Service Details
    service_date = models.DateField()
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=50, blank=True)
    
    service_code = models.ForeignKey('ServiceCode', on_delete=models.SET_NULL, null=True)
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    
    # Pricing
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Reference
    invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True)
    encounter = models.ForeignKey('Encounter', on_delete=models.SET_NULL, null=True)
```

### 5. Multi-Tier Pricing
```python
class ServicePricing(BaseModel):
    """Multi-tier pricing for services"""
    
    service_code = models.ForeignKey('ServiceCode', on_delete=models.CASCADE)
    
    # Price Tiers
    cash_price = models.DecimalField(max_digits=10, decimal_places=2)
    corporate_price = models.DecimalField(max_digits=10, decimal_places=2)
    insurance_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Effective Dates
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Payer-Specific Overrides
    payer = models.ForeignKey('Payer', on_delete=models.CASCADE, null=True, blank=True)
    custom_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    class Meta:
        unique_together = ['service_code', 'payer', 'effective_from']
```

### 6. Accounts Receivable Aging
```python
class ARAgingSnapshot(BaseModel):
    """Accounts Receivable aging analysis snapshot"""
    
    snapshot_date = models.DateField(unique=True)
    
    # Totals by Age Bucket
    current_0_30 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    days_31_60 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    days_61_90 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    days_91_120 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    days_over_120 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_outstanding = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # By Payer Type
    cash_outstanding = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    corporate_outstanding = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    insurance_outstanding = models.DecimalField(max_digits=12, decimal_places=2, default=0)
```

---

## 🔧 **Services & Business Logic**

### 1. Pricing Engine Service
```python
class PricingEngineService:
    """Determine correct price based on payer type"""
    
    def get_service_price(self, service_code, payer, patient=None):
        """
        Get price for service based on payer type and contracts
        
        Priority:
        1. Payer-specific custom price
        2. Corporate contracted price
        3. Insurance negotiated price
        4. Standard price tier (cash/corporate/insurance)
        5. Default price
        """
        
    def apply_corporate_discount(self, amount, corporate_account):
        """Apply corporate discount percentage"""
        
    def check_coverage_limits(self, patient, amount):
        """Check if within corporate/insurance limits"""
```

### 2. Monthly Billing Service
```python
class MonthlyBillingService:
    """Generate monthly statements for corporate/insurance"""
    
    def generate_monthly_statements(self, billing_month):
        """
        Generate statements for all accounts due this month
        Returns: List of generated statements
        """
        
    def generate_corporate_statement(self, corporate_account, period_start, period_end):
        """
        Create consolidated statement for corporate account
        Includes all services for enrolled employees
        """
        
    def generate_insurance_statement(self, insurance_payer, period_start, period_end):
        """
        Create claims batch for insurance company
        Groups all claims for the period
        """
        
    def send_statements(self, statements):
        """Email/print and distribute statements"""
        
    def send_payment_reminders(self):
        """Send reminders for overdue statements"""
```

### 3. Accounts Receivable Service
```python
class AccountsReceivableService:
    """Manage outstanding balances and collections"""
    
    def calculate_aging(self, as_of_date=None):
        """
        Calculate AR aging buckets:
        - Current (0-30 days)
        - 31-60 days
        - 61-90 days
        - 91-120 days
        - Over 120 days
        """
        
    def get_outstanding_by_payer(self):
        """Get outstanding balances grouped by payer"""
        
    def check_credit_limit(self, corporate_account):
        """Check if account exceeds credit limit"""
        
    def suspend_account_for_non_payment(self, corporate_account):
        """Suspend account if payment overdue"""
        
    def generate_collection_report(self):
        """Generate report of accounts needing collection"""
```

---

## 📋 **User Interfaces**

### 1. Corporate Account Management
```
URL: /hms/billing/corporate/accounts/

┌─────────────────────────────────────────────────────────┐
│  🏢 Corporate Accounts Management                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  [+ New Corporate Account]  [Generate Monthly Bills]   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Company Name      │ Balance    │ Status │ Action │  │
│  ├──────────────────────────────────────────────────┤  │
│  │ ABC Corp Ltd      │ GHS 45,000 │ Active │ [View] │  │
│  │ XYZ Industries    │ GHS 23,500 │ Active │ [View] │  │
│  │ DEF Company       │ GHS 67,890 │ Overdue│ [View] │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 2. Corporate Account Detail
```
URL: /hms/billing/corporate/accounts/<id>/

┌─────────────────────────────────────────────────────────┐
│  ABC Corporation Ltd - Account Detail                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  📊 Financial Summary                                   │
│  ├─ Credit Limit: GHS 100,000                          │
│  ├─ Current Balance: GHS 45,000                        │
│  ├─ Available Credit: GHS 55,000                       │
│  ├─ Payment Terms: Net 30 days                         │
│  └─ Status: ✅ Active                                  │
│                                                          │
│  👥 Enrolled Employees: 125                             │
│  [View Employees] [Add Employee]                        │
│                                                          │
│  📄 Recent Statements                                   │
│  ┌────────────────────────────────────────────────┐    │
│  │ Date       │ Amount     │ Due      │ Status   │    │
│  ├────────────────────────────────────────────────┤    │
│  │ Oct 2025   │ GHS 15,000 │ Nov 30   │ Paid     │    │
│  │ Sep 2025   │ GHS 18,500 │ Oct 31   │ Paid     │    │
│  │ Aug 2025   │ GHS 12,340 │ Sep 30   │ Overdue  │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  [Generate Statement] [View All Invoices]               │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 3. Monthly Statement View
```
URL: /hms/billing/statements/<id>/

┌─────────────────────────────────────────────────────────┐
│  📄 MONTHLY STATEMENT                                    │
│  Statement #: STMT-2025-10-001                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Bill To: ABC Corporation Ltd                           │
│  Period: October 1 - 31, 2025                           │
│  Due Date: November 30, 2025                            │
│                                                          │
│  ───────────────────────────────────────────────────    │
│                                                          │
│  Opening Balance:        GHS  12,340.00                 │
│  Charges (October):      GHS  15,670.00                 │
│  Payments Received:      GHS -12,340.00                 │
│  Adjustments:            GHS      0.00                  │
│                          ──────────────                  │
│  Amount Due:             GHS  15,670.00                 │
│                                                          │
│  ───────────────────────────────────────────────────    │
│                                                          │
│  Service Details (125 transactions):                    │
│  ┌────────────────────────────────────────────────┐    │
│  │ Date  │ Patient      │ Service    │ Amount    │    │
│  ├────────────────────────────────────────────────┤    │
│  │ 10/01 │ John Doe     │ Consultation│  120.00  │    │
│  │ 10/01 │ Jane Smith   │ Lab Test    │  250.00  │    │
│  │ 10/02 │ Bob Johnson  │ X-Ray       │  180.00  │    │
│  │ ...   │ ...          │ ...         │  ...     │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  [Download PDF] [Email Statement] [Record Payment]      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 4. AR Aging Report
```
URL: /hms/billing/ar-aging/

┌─────────────────────────────────────────────────────────┐
│  📊 Accounts Receivable Aging Report                    │
│  As of: November 7, 2025                                │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Summary by Age:                                        │
│  ┌────────────────────────────────────────────────┐    │
│  │ Current (0-30)  │ GHS 125,000 │ 45% │ ████████│    │
│  │ 31-60 days      │ GHS  78,000 │ 28% │ █████   │    │
│  │ 61-90 days      │ GHS  45,000 │ 16% │ ███     │    │
│  │ 91-120 days     │ GHS  20,000 │  7% │ █       │    │
│  │ Over 120 days   │ GHS  12,000 │  4% │ █       │    │
│  │                 │─────────────│─────│         │    │
│  │ TOTAL           │ GHS 280,000 │100% │         │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  Breakdown by Payer Type:                               │
│  ├─ Corporate:  GHS 180,000 (64%)                      │
│  ├─ Insurance:  GHS  85,000 (30%)                      │
│  └─ Cash:       GHS  15,000 (6%)                       │
│                                                          │
│  Top 10 Outstanding Accounts:                           │
│  ┌────────────────────────────────────────────────┐    │
│  │ Account         │ Amount     │ Age    │ Action │    │
│  ├────────────────────────────────────────────────┤    │
│  │ ABC Corp        │ GHS 67,890 │ 45 days│ [Call] │    │
│  │ XYZ Industries  │ GHS 45,000 │ 15 days│ [View] │    │
│  │ DEF Company     │ GHS 32,500 │ 90 days│ [Send]│    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  [Export Excel] [Print Report] [Send Reminders]         │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 5. Pricing Matrix Management
```
URL: /hms/billing/pricing/

┌─────────────────────────────────────────────────────────┐
│  💰 Service Pricing Matrix                              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  [+ Add Service Pricing] [Import from Excel]            │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Service      │ Cash  │ Corporate │ Insurance   │  │
│  ├──────────────────────────────────────────────────┤  │
│  │ Consultation │  150  │    120    │     100     │  │
│  │ CBC Test     │  250  │    200    │     180     │  │
│  │ X-Ray Chest  │  300  │    250    │     220     │  │
│  │ Ultrasound   │  500  │    400    │     350     │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  Special Corporate Rates:                               │
│  ┌──────────────────────────────────────────────────┐  │
│  │ ABC Corp: 15% discount on all services            │  │
│  │ XYZ Industries: Custom pricing (view contract)    │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 🔄 **Automated Processes**

### Monthly Billing Cycle
```python
# Cron job: Run on 1st of each month at 2 AM
def run_monthly_billing():
    """
    1. Get all corporate accounts due for billing
    2. For each account:
       a. Collect all services for enrolled employees (last month)
       b. Apply corporate pricing
       c. Generate consolidated statement
       d. Calculate totals
       e. Create PDF
       f. Email statement
       g. Log in accounting system
    3. Update AR aging
    4. Send notifications to account managers
    """
```

### Payment Reminder System
```python
# Cron job: Run daily at 9 AM
def send_payment_reminders():
    """
    1. Check all statements due in 7 days (friendly reminder)
    2. Check all statements overdue (urgent reminder)
    3. Check statements 30+ days overdue (final notice)
    4. Suspend accounts 60+ days overdue
    5. Send to collections if 90+ days overdue
    """
```

---

## 📊 **Reporting Dashboard**

### Key Metrics:
1. **Total AR**: GHS 280,000
2. **Current Month Billings**: GHS 125,000
3. **Collection Rate**: 85%
4. **Average Days to Pay**: 45 days
5. **Credit Limit Utilization**: 67%

### Charts:
- AR Aging Trend (last 12 months)
- Revenue by Payer Type
- Collection Performance
- Top 10 Accounts
- Overdue Accounts Alert

---

## 🎯 **Implementation Phases**

### Phase 1: Core Models & Pricing (Week 1)
- [ ] Create corporate account models
- [ ] Create multi-tier pricing models
- [ ] Create statement models
- [ ] Migrations

### Phase 2: Pricing Engine (Week 2)
- [ ] Implement pricing service
- [ ] Corporate discount logic
- [ ] Coverage limit checks
- [ ] Integration with invoicing

### Phase 3: Monthly Billing (Week 3)
- [ ] Statement generation service
- [ ] PDF template design
- [ ] Email distribution
- [ ] Automated billing cron job

### Phase 4: AR Management (Week 4)
- [ ] Aging calculation
- [ ] Outstanding tracking
- [ ] Collection workflows
- [ ] Credit limit enforcement

### Phase 5: UI & Reports (Week 5)
- [ ] Corporate account management interface
- [ ] Statement viewing
- [ ] AR aging reports
- [ ] Pricing matrix management

---

## 💡 **Key Benefits**

### For Finance Team:
- ✅ Automated monthly billing
- ✅ Clear AR visibility
- ✅ Efficient collections
- ✅ Accurate pricing
- ✅ Professional statements

### For Corporate Clients:
- ✅ Consolidated monthly bills
- ✅ Detailed service breakdown
- ✅ Predictable billing cycle
- ✅ Credit terms
- ✅ Online access

### For Hospital:
- ✅ Improved cash flow
- ✅ Reduced billing errors
- ✅ Better client relationships
- ✅ Compliance with contracts
- ✅ Data-driven decisions

---

**This is enterprise-grade billing system used by major hospitals worldwide!** 🏥
























