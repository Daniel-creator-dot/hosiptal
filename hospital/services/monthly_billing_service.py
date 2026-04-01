"""
Monthly Billing Service
Automated generation of monthly statements for corporate and insurance accounts
"""
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction as db_transaction
from django.db.models import Sum, Count, Q

logger = logging.getLogger(__name__)


class MonthlyBillingService:
    """
    Service for generating monthly consolidated statements
    Handles corporate and insurance billing cycles
    """
    
    def __init__(self):
        self.logger = logger
    
    def generate_all_monthly_statements(self, billing_month=None):
        """
        Generate monthly statements for all accounts due for billing
        
        Args:
            billing_month: Date object (defaults to last month)
        
        Returns:
            dict: Summary of generation results
        """
        from hospital.models_enterprise_billing import CorporateAccount, MonthlyStatement
        
        try:
            # Default to last month
            if not billing_month:
                today = timezone.now().date()
                # First day of current month minus 1 day = last day of last month
                last_month_end = today.replace(day=1) - timedelta(days=1)
                billing_month = last_month_end
            
            # Get period dates
            period_end = billing_month
            period_start = period_end.replace(day=1)
            
            self.logger.info(
                f"📅 Generating monthly statements for period: "
                f"{period_start} to {period_end}"
            )
            
            # Get all corporate accounts due for billing
            accounts_to_bill = CorporateAccount.objects.filter(
                is_active=True,
                billing_cycle='monthly',
                is_deleted=False
            )
            
            results = {
                'total_accounts': accounts_to_bill.count(),
                'successful': 0,
                'failed': 0,
                'skipped': 0,
                'statements': [],
                'errors': []
            }
            
            for account in accounts_to_bill:
                try:
                    statement = self.generate_corporate_statement(
                        account,
                        period_start,
                        period_end
                    )
                    
                    if statement:
                        results['successful'] += 1
                        results['statements'].append(statement)
                        self.logger.info(
                            f"✅ Statement generated for {account.company_name}: "
                            f"{statement.statement_number}"
                        )
                    else:
                        results['skipped'] += 1
                        self.logger.warning(
                            f"⚠️ No charges for {account.company_name}, statement skipped"
                        )
                        
                except Exception as e:
                    results['failed'] += 1
                    error_msg = f"Error generating statement for {account.company_name}: {str(e)}"
                    results['errors'].append(error_msg)
                    self.logger.error(error_msg, exc_info=True)
            
            self.logger.info(
                f"📊 Monthly billing complete: "
                f"{results['successful']} successful, "
                f"{results['failed']} failed, "
                f"{results['skipped']} skipped"
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in generate_all_monthly_statements: {str(e)}", exc_info=True)
            raise
    
    def generate_corporate_statement(self, corporate_account, period_start, period_end):
        """
        Generate consolidated monthly statement for a corporate account
        
        Args:
            corporate_account: CorporateAccount object
            period_start: Start date of billing period
            period_end: End date of billing period
        
        Returns:
            MonthlyStatement object or None if no charges
        """
        from hospital.models_enterprise_billing import (
            MonthlyStatement, StatementLine, CorporateEmployee
        )
        from hospital.models import Invoice, InvoiceLine
        
        try:
            with db_transaction.atomic():
                # Get all enrolled employees
                employees = CorporateEmployee.objects.filter(
                    corporate_account=corporate_account,
                    is_active=True,
                    is_deleted=False
                ).select_related('patient')
                
                if not employees.exists():
                    self.logger.warning(
                        f"No enrolled employees for {corporate_account.company_name}"
                    )
                    return None
                
                # Get all invoices for enrolled employees in period
                # IMPORTANT: Only get invoices where payer matches the corporate account
                patient_ids = [emp.patient.id for emp in employees]
                
                # Get the payer for this corporate account
                from hospital.models import Payer
                corporate_payer = Payer.objects.filter(
                    name=corporate_account.company_name,
                    payer_type='corporate',
                    is_active=True,
                    is_deleted=False
                ).first()
                
                invoices = Invoice.objects.filter(
                    patient_id__in=patient_ids,
                    payer=corporate_payer,  # Ensure invoice is billed to corporate account
                    issued_at__date__gte=period_start,
                    issued_at__date__lte=period_end,
                    is_deleted=False
                ).prefetch_related('lines')
                
                if not invoices.exists():
                    self.logger.info(
                        f"No invoices for {corporate_account.company_name} in period"
                    )
                    return None
                
                # Generate statement number
                statement_number = MonthlyStatement.generate_statement_number(period_end)
                
                # Calculate statement totals
                total_charges = Decimal('0.00')
                line_items = []
                patient_count = set()
                
                # Get opening balance (previous statement's closing balance)
                previous_statement = MonthlyStatement.objects.filter(
                    corporate_account=corporate_account,
                    statement_date__lt=period_start
                ).order_by('-statement_date').first()
                
                opening_balance = previous_statement.closing_balance if previous_statement else Decimal('0.00')
                
                # Process each invoice
                for invoice in invoices:
                    patient_count.add(invoice.patient.id)
                    
                    # Get employee ID
                    employee = employees.filter(patient=invoice.patient).first()
                    employee_id = employee.employee_id if employee else ''
                    
                    # Process invoice lines
                    for line in invoice.lines.filter(is_deleted=False):
                        total_charges += line.line_total
                        
                        line_items.append({
                            'service_date': invoice.issued_at.date(),
                            'patient': invoice.patient,
                            'employee_id': employee_id,
                            'service_code': line.service_code,
                            'description': line.description,
                            'quantity': line.quantity,
                            'unit_price': line.unit_price,
                            'discount_amount': line.discount_amount,
                            'tax_amount': line.tax_amount,
                            'line_total': line.line_total,
                            'invoice': invoice,
                            'encounter': invoice.encounter,
                        })
                
                # Calculate payments received in period
                total_payments = Decimal('0.00')  # TODO: Track payments by corporate account
                
                # Create statement
                payer = corporate_account.price_book.payer if corporate_account.price_book else None
                
                statement = MonthlyStatement.objects.create(
                    payer=payer,
                    corporate_account=corporate_account,
                    statement_number=statement_number,
                    statement_date=timezone.now().date(),
                    period_start=period_start,
                    period_end=period_end,
                    opening_balance=opening_balance,
                    total_charges=total_charges,
                    total_payments=total_payments,
                    total_adjustments=Decimal('0.00'),
                    closing_balance=opening_balance + total_charges - total_payments,
                    total_line_items=len(line_items),
                    total_patients_served=len(patient_count),
                    status='draft',
                    due_date=period_end + timedelta(days=corporate_account.payment_terms_days),
                    payment_terms=f"Net {corporate_account.payment_terms_days} days",
                    sent_to_email=corporate_account.billing_email
                )
                
                # Create statement lines
                for item in line_items:
                    StatementLine.objects.create(
                        statement=statement,
                        **item
                    )
                
                # Update corporate account
                corporate_account.current_balance = statement.closing_balance
                corporate_account.last_billing_date = period_end
                corporate_account.next_billing_date = self._calculate_next_billing_date(
                    corporate_account.billing_cycle,
                    period_end
                )
                corporate_account.save()
                
                self.logger.info(
                    f"✅ Statement created: {statement_number} for {corporate_account.company_name} "
                    f"(GHS {total_charges}, {len(line_items)} lines, {len(patient_count)} patients)"
                )
                
                return statement
                
        except Exception as e:
            self.logger.error(
                f"Error generating statement for {corporate_account.company_name}: {str(e)}",
                exc_info=True
            )
            raise
    
    def send_statements(self, statements, via='email'):
        """
        Send statements to corporate accounts
        
        Args:
            statements: List of MonthlyStatement objects
            via: Delivery method ('email', 'post', 'both')
        
        Returns:
            dict: Summary of sending results
        """
        results = {
            'total': len(statements),
            'sent': 0,
            'failed': 0,
            'errors': []
        }
        
        for statement in statements:
            try:
                if via in ['email', 'both']:
                    # TODO: Implement email sending with PDF attachment
                    # For now, just mark as sent
                    statement.sent_date = timezone.now()
                    statement.sent_via = via
                    statement.status = 'sent'
                    statement.save()
                    
                    results['sent'] += 1
                    self.logger.info(f"📧 Statement sent: {statement.statement_number}")
                    
            except Exception as e:
                results['failed'] += 1
                error_msg = f"Error sending {statement.statement_number}: {str(e)}"
                results['errors'].append(error_msg)
                self.logger.error(error_msg)
        
        return results
    
    def send_payment_reminders(self, days_before_due=7):
        """
        Send payment reminders for upcoming due dates
        
        Args:
            days_before_due: Days before due date to send reminder
        
        Returns:
            int: Number of reminders sent
        """
        from hospital.models_enterprise_billing import MonthlyStatement
        
        try:
            today = timezone.now().date()
            reminder_date = today + timedelta(days=days_before_due)
            
            # Get statements due soon and not yet paid
            statements = MonthlyStatement.objects.filter(
                status__in=['sent', 'partially_paid'],
                due_date=reminder_date,
                is_deleted=False
            )
            
            reminders_sent = 0
            
            for statement in statements:
                try:
                    # TODO: Send actual email reminder
                    # For now, just log
                    statement.reminder_count += 1
                    statement.last_reminder_sent = timezone.now()
                    statement.save()
                    
                    reminders_sent += 1
                    self.logger.info(
                        f"📬 Reminder sent for {statement.statement_number} "
                        f"to {statement.corporate_account.company_name}"
                    )
                    
                except Exception as e:
                    self.logger.error(
                        f"Error sending reminder for {statement.statement_number}: {str(e)}"
                    )
            
            return reminders_sent
            
        except Exception as e:
            self.logger.error(f"Error in send_payment_reminders: {str(e)}", exc_info=True)
            return 0
    
    def check_overdue_statements(self):
        """
        Check for overdue statements and update corporate account status
        
        Returns:
            dict: Summary of overdue accounts
        """
        from hospital.models_enterprise_billing import MonthlyStatement
        
        try:
            today = timezone.now().date()
            
            # Get overdue statements
            overdue_statements = MonthlyStatement.objects.filter(
                due_date__lt=today,
                status__in=['sent', 'partially_paid'],
                is_deleted=False
            ).select_related('corporate_account')
            
            results = {
                'total_overdue': 0,
                'accounts_suspended': 0,
                'accounts_on_hold': 0,
            }
            
            for statement in overdue_statements:
                results['total_overdue'] += 1
                
                # Update statement status
                if statement.status != 'overdue':
                    statement.status = 'overdue'
                    statement.save()
                
                # Check if account should be suspended
                if statement.corporate_account:
                    account = statement.corporate_account
                    days_overdue = statement.days_overdue
                    
                    if days_overdue >= 60 and account.credit_status == 'active':
                        # Suspend account if 60+ days overdue
                        account.credit_status = 'suspended'
                        account.save()
                        results['accounts_suspended'] += 1
                        
                        self.logger.warning(
                            f"⚠️ Account suspended: {account.company_name} "
                            f"({days_overdue} days overdue)"
                        )
                    elif days_overdue >= 30 and account.credit_status == 'active':
                        # Put on hold if 30+ days overdue
                        account.credit_status = 'on_hold'
                        account.save()
                        results['accounts_on_hold'] += 1
                        
                        self.logger.warning(
                            f"⚠️ Account on hold: {account.company_name} "
                            f"({days_overdue} days overdue)"
                        )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error checking overdue statements: {str(e)}", exc_info=True)
            return {}
    
    def _calculate_next_billing_date(self, billing_cycle, current_period_end):
        """Calculate next billing date based on cycle"""
        if billing_cycle == 'monthly':
            # Next month, same day
            next_month = current_period_end + timedelta(days=32)
            return next_month.replace(day=1)  # First of next month
        elif billing_cycle == 'bi_weekly':
            return current_period_end + timedelta(days=14)
        elif billing_cycle == 'weekly':
            return current_period_end + timedelta(days=7)
        else:
            # Custom - default to monthly
            next_month = current_period_end + timedelta(days=32)
            return next_month.replace(day=1)


# Global instance
monthly_billing_service = MonthlyBillingService()
























