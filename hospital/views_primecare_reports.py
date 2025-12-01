"""
Primecare Medical Centre - Financial Reports
Balance Sheet and Profit & Loss matching the technical guide format
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from datetime import date, timedelta
from decimal import Decimal
from .models_accounting import Account, GeneralLedger
from .models_accounting_advanced import AdvancedGeneralLedger, FiscalYear, AccountingPeriod


def is_accountant(user):
    """Check if user is an accountant"""
    return user.groups.filter(name__in=['Accountant', 'Admin', 'Cashier']).exists() or user.is_staff


@login_required
@user_passes_test(is_accountant, login_url='/hms/login/')
def primecare_balance_sheet(request):
    """
    Balance Sheet (Financial Position) - IAS 1 Format
    Company Name: Primecare Medical Centre
    """
    # Get date from request or use today
    report_date = request.GET.get('date')
    if report_date:
        try:
            report_date = date.fromisoformat(report_date)
        except:
            report_date = timezone.now().date()
    else:
        report_date = timezone.now().date()
    
    # Get account balances up to report date
    def get_account_balance(account_code, as_of_date):
        """Get account balance as of specific date"""
        try:
            # Try advanced ledger first
            entries = AdvancedGeneralLedger.objects.filter(
                account__account_code=account_code,
                transaction_date__lte=as_of_date,
                is_voided=False,
                is_deleted=False
            ).aggregate(
                total_debits=Sum('debit_amount'),
                total_credits=Sum('credit_amount')
            )
            
            total_debits = entries['total_debits'] or Decimal('0.00')
            total_credits = entries['total_credits'] or Decimal('0.00')
            
            # For assets and expenses: debit - credit
            # For liabilities, equity, revenue: credit - debit
            account = Account.objects.filter(account_code=account_code).first()
            if account:
                if account.account_type in ['asset', 'expense']:
                    return total_debits - total_credits
                else:
                    return total_credits - total_debits
            return Decimal('0.00')
        except:
            # Fallback to old GeneralLedger
            try:
                entries = GeneralLedger.objects.filter(
                    account__account_code=account_code,
                    transaction_date__lte=as_of_date,
                    is_deleted=False
                ).aggregate(
                    total_debits=Sum('debit_amount'),
                    total_credits=Sum('credit_amount')
                )
                
                total_debits = entries['total_debits'] or Decimal('0.00')
                total_credits = entries['total_credits'] or Decimal('0.00')
                
                account = Account.objects.filter(account_code=account_code).first()
                if account:
                    if account.account_type in ['asset', 'expense']:
                        return total_debits - total_credits
                    else:
                        return total_credits - total_debits
                return Decimal('0.00')
            except:
                return Decimal('0.00')
    
    # CURRENT ASSETS
    cash_and_equivalents = get_account_balance('1010', report_date)
    undeposited_funds = get_account_balance('1015', report_date)
    bank_accounts = get_account_balance('1020', report_date) + get_account_balance('1021', report_date)
    inventories = get_account_balance('1400', report_date)
    trade_receivables = get_account_balance('1200', report_date)
    insurance_receivables = get_account_balance('1201', report_date)
    corporate_receivables = get_account_balance('1202', report_date)
    other_current_assets = get_account_balance('1500', report_date)
    advances_prepayments = get_account_balance('1501', report_date)
    income_tax_assets = get_account_balance('1600', report_date)
    short_term_investments = get_account_balance('1700', report_date)
    
    total_current_assets = (
        cash_and_equivalents + undeposited_funds + bank_accounts + inventories +
        trade_receivables + insurance_receivables + corporate_receivables +
        other_current_assets + advances_prepayments + income_tax_assets +
        short_term_investments
    )
    
    # NON-CURRENT ASSETS
    ppe = get_account_balance('1800', report_date)
    land = get_account_balance('1801', report_date)
    buildings = get_account_balance('1802', report_date)
    medical_equipment = get_account_balance('1803', report_date)
    furniture_fixtures = get_account_balance('1804', report_date)
    vehicles = get_account_balance('1805', report_date)
    accumulated_depreciation = get_account_balance('1806', report_date)  # This is negative
    intangible_assets = get_account_balance('1900', report_date)
    long_term_investments = get_account_balance('1901', report_date)
    deferred_tax_assets = get_account_balance('1902', report_date)
    
    total_ppe = ppe + land + buildings + medical_equipment + furniture_fixtures + vehicles + accumulated_depreciation
    total_non_current_assets = total_ppe + intangible_assets + long_term_investments + deferred_tax_assets
    
    total_assets = total_current_assets + total_non_current_assets
    
    # CURRENT LIABILITIES
    bank_overdrafts = get_account_balance('2010', report_date)
    short_term_borrowings = get_account_balance('2011', report_date)
    trade_payables = get_account_balance('2100', report_date)
    accounts_payable = get_account_balance('2101', report_date)
    provisions = get_account_balance('2200', report_date)
    income_tax_liabilities = get_account_balance('2300', report_date)
    other_liabilities = get_account_balance('2400', report_date)
    
    total_current_liabilities = (
        bank_overdrafts + short_term_borrowings + trade_payables + accounts_payable +
        provisions + income_tax_liabilities + other_liabilities
    )
    
    # NON-CURRENT LIABILITIES
    long_term_loans = get_account_balance('2500', report_date)
    interest_bearing_long_term = get_account_balance('2501', report_date)
    long_term_provisions = get_account_balance('2600', report_date)
    deferred_tax_liabilities = get_account_balance('2700', report_date)
    
    total_non_current_liabilities = (
        long_term_loans + interest_bearing_long_term + long_term_provisions + deferred_tax_liabilities
    )
    
    total_liabilities = total_current_liabilities + total_non_current_liabilities
    
    # EQUITY
    share_capital = get_account_balance('3000', report_date)
    reserves = get_account_balance('3100', report_date)
    retained_earnings = get_account_balance('3200', report_date)
    
    total_equity = share_capital + reserves + retained_earnings
    
    total_equity_and_liabilities = total_equity + total_liabilities
    
    context = {
        'report_date': report_date,
        'company_name': 'Primecare Medical Centre',
        
        # Current Assets
        'cash_and_equivalents': cash_and_equivalents,
        'undeposited_funds': undeposited_funds,
        'bank_accounts': bank_accounts,
        'inventories': inventories,
        'trade_receivables': trade_receivables,
        'insurance_receivables': insurance_receivables,
        'corporate_receivables': corporate_receivables,
        'other_current_assets': other_current_assets,
        'advances_prepayments': advances_prepayments,
        'income_tax_assets': income_tax_assets,
        'short_term_investments': short_term_investments,
        'total_current_assets': total_current_assets,
        
        # Non-Current Assets
        'ppe': ppe,
        'land': land,
        'buildings': buildings,
        'medical_equipment': medical_equipment,
        'furniture_fixtures': furniture_fixtures,
        'vehicles': vehicles,
        'accumulated_depreciation': accumulated_depreciation,
        'total_ppe': total_ppe,
        'intangible_assets': intangible_assets,
        'long_term_investments': long_term_investments,
        'deferred_tax_assets': deferred_tax_assets,
        'total_non_current_assets': total_non_current_assets,
        'total_assets': total_assets,
        
        # Current Liabilities
        'bank_overdrafts': bank_overdrafts,
        'short_term_borrowings': short_term_borrowings,
        'trade_payables': trade_payables,
        'accounts_payable': accounts_payable,
        'provisions': provisions,
        'income_tax_liabilities': income_tax_liabilities,
        'other_liabilities': other_liabilities,
        'total_current_liabilities': total_current_liabilities,
        
        # Non-Current Liabilities
        'long_term_loans': long_term_loans,
        'interest_bearing_long_term': interest_bearing_long_term,
        'long_term_provisions': long_term_provisions,
        'deferred_tax_liabilities': deferred_tax_liabilities,
        'total_non_current_liabilities': total_non_current_liabilities,
        'total_liabilities': total_liabilities,
        
        # Equity
        'share_capital': share_capital,
        'reserves': reserves,
        'retained_earnings': retained_earnings,
        'total_equity': total_equity,
        'total_equity_and_liabilities': total_equity_and_liabilities,
    }
    
    return render(request, 'hospital/primecare/balance_sheet.html', context)


@login_required
@user_passes_test(is_accountant, login_url='/hms/login/')
def primecare_profit_loss(request):
    """
    Profit or Loss Statement - Matching Document Format
    Company Name: Primecare Medical Centre
    """
    # Get date range from request
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        # Default to current month
        today = timezone.now().date()
        start_date = today.replace(day=1)
        end_date = today
    else:
        start_date = date.fromisoformat(start_date)
        end_date = date.fromisoformat(end_date)
    
    def get_revenue_balance(account_code, start, end):
        """Get revenue account balance for period"""
        try:
            entries = AdvancedGeneralLedger.objects.filter(
                account__account_code=account_code,
                transaction_date__gte=start,
                transaction_date__lte=end,
                is_voided=False,
                is_deleted=False
            ).aggregate(total=Sum('credit_amount'))
            return entries['total'] or Decimal('0.00')
        except:
            try:
                entries = GeneralLedger.objects.filter(
                    account__account_code=account_code,
                    transaction_date__gte=start,
                    transaction_date__lte=end,
                    is_deleted=False
                ).aggregate(total=Sum('credit_amount'))
                return entries['total'] or Decimal('0.00')
            except:
                return Decimal('0.00')
    
    def get_expense_balance(account_code, start, end):
        """Get expense account balance for period"""
        try:
            entries = AdvancedGeneralLedger.objects.filter(
                account__account_code=account_code,
                transaction_date__gte=start,
                transaction_date__lte=end,
                is_voided=False,
                is_deleted=False
            ).aggregate(total=Sum('debit_amount'))
            return entries['total'] or Decimal('0.00')
        except:
            try:
                entries = GeneralLedger.objects.filter(
                    account__account_code=account_code,
                    transaction_date__gte=start,
                    transaction_date__lte=end,
                    is_deleted=False
                ).aggregate(total=Sum('debit_amount'))
                return entries['total'] or Decimal('0.00')
            except:
                return Decimal('0.00')
    
    # INTERNALLY GENERATED REVENUE
    registration = get_revenue_balance('4100', start_date, end_date)
    consultation = get_revenue_balance('4110', start_date, end_date)
    laboratory = get_revenue_balance('4120', start_date, end_date)
    pharmacy = get_revenue_balance('4130', start_date, end_date)
    surgeries = get_revenue_balance('4140', start_date, end_date)
    admissions = get_revenue_balance('4150', start_date, end_date)
    radiology = get_revenue_balance('4160', start_date, end_date)
    dental = get_revenue_balance('4170', start_date, end_date)
    physiotherapy = get_revenue_balance('4180', start_date, end_date)
    
    total_internal_revenue = (
        registration + consultation + laboratory + pharmacy + surgeries +
        admissions + radiology + dental + physiotherapy
    )
    
    # COST OF SALES
    opening_inventory = get_expense_balance('5100', start_date, end_date)
    purchases_drugs = get_expense_balance('5110', start_date, end_date)
    purchases_lab_reagents = get_expense_balance('5111', start_date, end_date)
    purchases_dental = get_expense_balance('5112', start_date, end_date)
    purchases_radiology = get_expense_balance('5113', start_date, end_date)
    purchases_consumables = get_expense_balance('5114', start_date, end_date)
    purchases_physiotherapy = get_expense_balance('5115', start_date, end_date)
    purchases_others = get_expense_balance('5116', start_date, end_date)
    closing_inventory = get_expense_balance('5120', start_date, end_date)  # This is negative
    
    total_purchases = (
        purchases_drugs + purchases_lab_reagents + purchases_dental +
        purchases_radiology + purchases_consumables + purchases_physiotherapy +
        purchases_others
    )
    
    cost_of_sales = opening_inventory + total_purchases - closing_inventory
    gross_profit = total_internal_revenue - cost_of_sales
    
    # OTHER INCOME
    discount_received = get_revenue_balance('4210', start_date, end_date)
    interest_income = get_revenue_balance('4220', start_date, end_date)
    other_income = get_revenue_balance('4200', start_date, end_date)
    
    total_other_income = discount_received + interest_income + other_income
    total_income = gross_profit + total_other_income
    
    # OPERATING EXPENSES
    bills_rejections = get_expense_balance('5200', start_date, end_date)
    salaries = get_expense_balance('5210', start_date, end_date)
    employer_ssf = get_expense_balance('5211', start_date, end_date)
    printing_stationery = get_expense_balance('5220', start_date, end_date)
    electricity = get_expense_balance('5230', start_date, end_date)
    water = get_expense_balance('5240', start_date, end_date)
    telephone = get_expense_balance('5250', start_date, end_date)
    cleaning_sanitation = get_expense_balance('5260', start_date, end_date)
    bank_charges = get_expense_balance('5270', start_date, end_date)
    security_services = get_expense_balance('5280', start_date, end_date)
    insurance = get_expense_balance('5290', start_date, end_date)
    transport_travelling = get_expense_balance('5300', start_date, end_date)
    fuel = get_expense_balance('5310', start_date, end_date)
    training_development = get_expense_balance('5320', start_date, end_date)
    hire_equipment = get_expense_balance('5330', start_date, end_date)
    medical_discount_allowed = get_expense_balance('5340', start_date, end_date)
    advertisement_promotions = get_expense_balance('5350', start_date, end_date)
    medical_refunds = get_expense_balance('5360', start_date, end_date)
    repairs_maintenance = get_expense_balance('5370', start_date, end_date)
    depreciation = get_expense_balance('5380', start_date, end_date)
    other_expenses = get_expense_balance('5390', start_date, end_date)
    
    total_operating_expenses = (
        bills_rejections + salaries + employer_ssf + printing_stationery +
        electricity + water + telephone + cleaning_sanitation + bank_charges +
        security_services + insurance + transport_travelling + fuel +
        training_development + hire_equipment + medical_discount_allowed +
        advertisement_promotions + medical_refunds + repairs_maintenance +
        depreciation + other_expenses
    )
    
    net_profit_loss = total_income - total_operating_expenses
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'company_name': 'Primecare Medical Centre',
        
        # Revenue
        'registration': registration,
        'consultation': consultation,
        'laboratory': laboratory,
        'pharmacy': pharmacy,
        'surgeries': surgeries,
        'admissions': admissions,
        'radiology': radiology,
        'dental': dental,
        'physiotherapy': physiotherapy,
        'total_internal_revenue': total_internal_revenue,
        
        # Cost of Sales
        'opening_inventory': opening_inventory,
        'purchases_drugs': purchases_drugs,
        'purchases_lab_reagents': purchases_lab_reagents,
        'purchases_dental': purchases_dental,
        'purchases_radiology': purchases_radiology,
        'purchases_consumables': purchases_consumables,
        'purchases_physiotherapy': purchases_physiotherapy,
        'purchases_others': purchases_others,
        'total_purchases': total_purchases,
        'closing_inventory': closing_inventory,
        'cost_of_sales': cost_of_sales,
        'gross_profit': gross_profit,
        
        # Other Income
        'discount_received': discount_received,
        'interest_income': interest_income,
        'other_income': other_income,
        'total_other_income': total_other_income,
        'total_income': total_income,
        
        # Operating Expenses
        'bills_rejections': bills_rejections,
        'salaries': salaries,
        'employer_ssf': employer_ssf,
        'printing_stationery': printing_stationery,
        'electricity': electricity,
        'water': water,
        'telephone': telephone,
        'cleaning_sanitation': cleaning_sanitation,
        'bank_charges': bank_charges,
        'security_services': security_services,
        'insurance': insurance,
        'transport_travelling': transport_travelling,
        'fuel': fuel,
        'training_development': training_development,
        'hire_equipment': hire_equipment,
        'medical_discount_allowed': medical_discount_allowed,
        'advertisement_promotions': advertisement_promotions,
        'medical_refunds': medical_refunds,
        'repairs_maintenance': repairs_maintenance,
        'depreciation': depreciation,
        'other_expenses': other_expenses,
        'total_operating_expenses': total_operating_expenses,
        'net_profit_loss': net_profit_loss,
    }
    
    return render(request, 'hospital/primecare/profit_loss.html', context)














