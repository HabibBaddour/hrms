from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

class SystemNotification(models.Model):
    """نموذج الإشعارات المركزي للنظام"""
    
    NOTIFICATION_TYPES = (
        ('SYSTEM', 'نظام'),
        ('EMPLOYEE', 'موظف'),
        ('DEPARTMENT', 'قسم'),
        ('LEAVE', 'إجازة'),
        ('PAYROLL', 'رواتب'),
    )
    
    VERB_CHOICES = (
        ('created', 'إنشاء'),
        ('updated', 'تعديل'),
        ('deleted', 'حذف'),
        ('assigned', 'تعيين'),
        ('submitted', 'تقديم'),
        ('approved', 'موافقة'),
        ('rejected', 'رفض'),
    )
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='system_notifications')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')
    verb = models.CharField(max_length=50, choices=VERB_CHOICES)
    
    # Generic Foreign Key for target objects
    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    target_object_id = models.PositiveIntegerField(null=True, blank=True)
    target = GenericForeignKey('target_content_type', 'target_object_id')
    
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='SYSTEM')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'إشعار نظام'
        verbose_name_plural = 'إشعارات النظام'
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.recipient.username} - {self.message[:50]}"
    
    def mark_as_read(self):
        """تحديد الإشعار كمقروء"""
        if not self.is_read:
            self.is_read = True
            self.save()
    
    @classmethod
    def create_notification(cls, recipient, verb, notification_type, message, actor=None, target=None):
        """إنشاء إشعار جديد"""
        notification = cls.objects.create(
            recipient=recipient,
            actor=actor,
            verb=verb,
            notification_type=notification_type,
            message=message
        )
        
        if target:
            notification.target_content_type = ContentType.objects.get_for_model(target)
            notification.target_object_id = target.id
            notification.save()
        
        return notification
    
    @classmethod
    def get_unread_count(cls, user):
        """الحصول على عدد الإشعارات غير المقروءة"""
        return cls.objects.filter(recipient=user, is_read=False).count()
    
    @classmethod
    def get_recent_notifications(cls, user, limit=10):
        """الحصول على أحدث الإشعارات"""
        return cls.objects.filter(recipient=user).select_related('actor')[:limit]
    
    @classmethod
    def mark_all_as_read(cls, user):
        """تحديد جميع إشعارات المستخدم كمقروءة"""
        cls.objects.filter(recipient=user, is_read=False).update(is_read=True)
    
    def get_notification_type_color(self):
        """Get Bootstrap color for notification type"""
        colors = {
            'SYSTEM': 'secondary',
            'EMPLOYEE': 'success',
            'DEPARTMENT': 'info',
            'LEAVE': 'warning',
            'PAYROLL': 'danger',
        }
        return colors.get(self.notification_type, 'secondary')
    
    def get_notification_type_display(self):
        """Get Arabic display for notification type"""
        types = {
            'SYSTEM': 'نظام',
            'EMPLOYEE': 'موظف',
            'DEPARTMENT': 'قسم',
            'LEAVE': 'إجازة',
            'PAYROLL': 'رواتب',
        }
        return types.get(self.notification_type, 'نظام')
    
    def get_target_url(self):
        """Get URL for the target object"""
        if not self.target:
            return None
        
        try:
            if hasattr(self.target, 'get_absolute_url'):
                return self.target.get_absolute_url()
            
            # Fallback for different model types
            content_type = self.target_content_type.model
            if content_type == 'department':
                return f"departments:department_detail"
            elif content_type == 'employee':
                return f"employees:edit_employee"
            elif content_type == 'position':
                return f"departments:department_detail"
            elif content_type == 'leaverequest':
                return f"leaves:leave_detail"
            else:
                return None
        except:
            return None

# Keep the old Notification model for backward compatibility
class Notification(models.Model):
    """نموذج الإشعارات القديم للتوافق"""
    
    NOTIFICATION_TYPES = (
        ('employee_created', 'إنشاء موظف'),
        ('department_created', 'إنشاء قسم'),
        ('position_created', 'إنشاء مسمى وظيفي'),
        ('employee_updated', 'تعديل موظف'),
        ('department_updated', 'تعديل قسم'),
        ('position_updated', 'تعديل مسمى وظيفي'),
        ('leave_request', 'طلب إجازة'),
        ('leave_approved', 'موافقة على إجازة'),
        ('leave_rejected', 'رفض إجازة'),
        ('general', 'إشعار عام'),
    )
    
    STATUS_CHOICES = (
        ('unread', 'غير مقروء'),
        ('read', 'مقروء'),
        ('opened', 'مفتوح'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='old_notifications')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES, default='general')
    title = models.CharField(max_length=200)
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unread')
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'إشعار قديم'
        verbose_name_plural = 'الإشعارات القديمة'
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"


class InternalMessage(models.Model):
    """نموذج الرسائل الداخلية"""
    
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    subject = models.CharField(max_length=200)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'رسالة داخلية'
        verbose_name_plural = 'الرسائل الداخلية'
        indexes = [
            models.Index(fields=['sender', 'created_at']),
            models.Index(fields=['recipient', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.sender.username} -> {self.recipient.username}: {self.subject}"
    
    def mark_as_read(self):
        """تحديد الرسالة كمقروءة"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    @classmethod
    def get_unread_count(cls, user):
        """الحصول على عدد الرسائل غير المقروءة"""
        return cls.objects.filter(recipient=user, is_read=False).count()
    
    @classmethod
    def get_conversation(cls, user1, user2):
        """الحصول على المحادثة بين مستخدمين"""
        return cls.objects.filter(
            (models.Q(sender=user1) & models.Q(recipient=user2)) |
            (models.Q(sender=user2) & models.Q(recipient=user1))
        ).order_by('created_at')