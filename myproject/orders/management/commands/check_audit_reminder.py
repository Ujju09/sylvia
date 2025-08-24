from django.core.management.base import BaseCommand
from django.utils import timezone
import calendar


class Command(BaseCommand):
    help = 'Check if data audit reminder should be shown (last 7 days of month)'
    
    def handle(self, *args, **options):
        today = timezone.now().date()
        year = today.year
        month = today.month
        
        # Get last day of current month
        last_day_of_month = calendar.monthrange(year, month)[1]
        
        # Calculate if we're in the last 7 days
        days_until_end = last_day_of_month - today.day
        
        if days_until_end <= 6:  # Last 7 days of month (0-6 days remaining)
            self.stdout.write(
                self.style.SUCCESS(
                    f'AUDIT_REMINDER_ACTIVE: {days_until_end + 1} days left in {calendar.month_name[month]} {year}'
                )
            )
            return True
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'AUDIT_REMINDER_INACTIVE: {days_until_end + 1} days left in {calendar.month_name[month]} {year}'
                )
            )
            return False