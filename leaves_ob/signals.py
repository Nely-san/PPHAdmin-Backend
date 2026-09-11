from datetime import timedelta
from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver
from leaves_ob.models import LeaveOBApplication
from biometrics_attendance.models import AttendanceRecord
from scheduling.models import Schedule

@receiver(post_save, sender=LeaveOBApplication)
def sync_approved_leave_to_attendance(sender, instance, created, **kwargs):
    """
    When a Leave or OB application is approved, automatically creates/updates
    AttendanceRecord and Schedule for the duration of the leave.
    """
    if instance.status == 'APPROVED':
        cur_date = instance.start_date
        while cur_date <= instance.end_date:
            is_ob = instance.request_type == 'OFFICIAL_BUSINESS'
            status_code = 'BUSINESS_TRIP' if is_ob else 'ON_LEAVE'
            hours = Decimal('8.00') if is_ob else Decimal('0.00')

            # Update/Create AttendanceRecord
            AttendanceRecord.objects.update_or_create(
                person=instance.person,
                date=cur_date,
                defaults={
                    'status': status_code,
                    'is_leave': not is_ob,
                    'is_business_trip': is_ob,
                    'is_field_ob': is_ob,
                    'actual_hours': hours,
                    'required_hours': Decimal('8.00'),
                    'memo': f"{instance.get_request_type_display()}: {instance.reason}",
                    'is_abnormal': False,
                    'is_archived': False
                }
            )

            # Update/Create Schedule
            schedule_type = 'BUSINESS_TRIP' if is_ob else 'LEAVE'
            Schedule.objects.update_or_create(
                person=instance.person,
                date=cur_date,
                defaults={
                    'schedule_type': schedule_type,
                    'note': f"Approved {instance.get_request_type_display()}",
                    'is_archived': False
                }
            )
            cur_date += timedelta(days=1)
