"""
Management command to check and fix leave request statuses
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from hospital.models_advanced import LeaveRequest


class Command(BaseCommand):
    help = 'Check and fix leave request statuses'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Checking leave requests...'))
        
        # Get all leave requests
        all_leaves = LeaveRequest.objects.filter(is_deleted=False)
        
        self.stdout.write(f'\nTotal leave requests: {all_leaves.count()}')
        
        # Count by status
        for status in ['draft', 'pending', 'approved', 'rejected', 'cancelled']:
            count = all_leaves.filter(status=status).count()
            self.stdout.write(f'  - {status.upper()}: {count}')
        
        # Check for recently approved leaves
        self.stdout.write(self.style.WARNING('\n\nRecently approved leaves (last 24 hours):'))
        recent_approved = all_leaves.filter(
            status='approved',
            approved_at__gte=timezone.now() - timezone.timedelta(days=1)
        ).select_related('staff__user', 'approved_by__user')
        
        if recent_approved.exists():
            for leave in recent_approved:
                approver = leave.approved_by.user.get_full_name() if leave.approved_by else 'Unknown'
                self.stdout.write(
                    f'  - {leave.staff.user.get_full_name()}: '
                    f'{leave.start_date} to {leave.end_date} '
                    f'(Approved by: {approver} at {leave.approved_at})'
                )
        else:
            self.stdout.write('  No recently approved leaves found.')
        
        # Check for pending leaves without request numbers
        self.stdout.write(self.style.WARNING('\n\nPending leaves without request numbers:'))
        pending_no_number = all_leaves.filter(
            status='pending',
            request_number__isnull=True
        )
        
        if pending_no_number.exists():
            self.stdout.write(f'  Found {pending_no_number.count()} pending leaves without request numbers')
            for leave in pending_no_number:
                self.stdout.write(f'  - {leave.staff.user.get_full_name()}: {leave.start_date} to {leave.end_date}')
        else:
            self.stdout.write('  All pending leaves have request numbers.')
        
        # Check for approved leaves without approved_by
        self.stdout.write(self.style.WARNING('\n\nApproved leaves without approver:'))
        approved_no_approver = all_leaves.filter(
            status='approved',
            approved_by__isnull=True
        )
        
        if approved_no_approver.exists():
            self.stdout.write(self.style.ERROR(f'  Found {approved_no_approver.count()} approved leaves without approver!'))
            for leave in approved_no_approver:
                self.stdout.write(f'  - ID: {leave.pk}, Staff: {leave.staff.user.get_full_name()}, Dates: {leave.start_date} to {leave.end_date}')
            
            # Offer to fix
            fix = input('\nDo you want to set approved_at for these? (y/n): ')
            if fix.lower() == 'y':
                for leave in approved_no_approver:
                    if not leave.approved_at:
                        leave.approved_at = leave.updated_at or leave.created_at
                        leave.save()
                self.stdout.write(self.style.SUCCESS(f'Fixed {approved_no_approver.count()} leave requests'))
        else:
            self.stdout.write('  All approved leaves have approvers.')
        
        # List all leave requests for a specific staff if name provided
        self.stdout.write(self.style.SUCCESS('\n\nDone!'))
































