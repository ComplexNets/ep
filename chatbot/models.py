from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import json

# Create your models here.

class Event(models.Model):
    WRITING_PHASE_CHOICES = [
        ('facts', 'Facts'),
        ('feelings', 'Feelings'),
        ('thoughts', 'Thoughts'),
        ('growth', 'Growth')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date_occurred = models.DateField(help_text="When did this event occur?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    current_phase = models.CharField(
        max_length=20,
        choices=WRITING_PHASE_CHOICES,
        default='facts'
    )
    
    def __str__(self):
        return f"{self.title} ({self.get_current_phase_display()})"
    
    class Meta:
        ordering = ['-date_occurred']

class UserThread(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, null=True, blank=True)
    thread_id = models.CharField(max_length=255)
    writing_phase = models.CharField(
        max_length=20,
        choices=Event.WRITING_PHASE_CHOICES,
        default='facts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_interaction = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'thread_id']),
            models.Index(fields=['event', 'writing_phase']),
        ]

class ChatMessage(models.Model):
    MESSAGE_TYPES = [
        ('user', 'User Message'),
        ('assistant', 'Assistant Message'),
        ('system', 'System Message')
    ]
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, null=True, blank=True)
    user_thread = models.ForeignKey(UserThread, on_delete=models.CASCADE)
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    phase = models.CharField(
        max_length=20,
        choices=Event.WRITING_PHASE_CHOICES,
        default='facts'
    )

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['event', 'created_at'], name='chat_event_created_idx'),
            models.Index(fields=['user_thread', 'created_at'], name='chat_thread_created_idx'),
            models.Index(fields=['user_thread', 'phase'], name='chat_thread_phase_idx'),
        ]
    
    def get_formatted_time(self):
        return self.created_at.strftime("%I:%M %p")
    
    def get_formatted_date(self):
        return self.created_at.strftime("%B %d, %Y")

class Conversation(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'event', 'updated_at'], name='conv_user_event_updated_idx'),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_formatted_date()})"
    
    def get_formatted_date(self):
        return self.created_at.strftime("%B %d, %Y")
    
    def get_message_count(self):
        return self.chatmessage_set.count()

class UserProfile(models.Model):
    PERSONALITY_CHOICES = [
        ('professional', 'Professional and Academic'),
        ('empathetic', 'Empathetic and Supportive'),
        ('encouraging', 'Encouraging and Motivational'),
        ('friendly', 'Friendly and Casual'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio_context = models.TextField(blank=True, null=True, 
        help_text="Biographical context for the writing assistant")
    writing_goals = models.TextField(blank=True, null=True,
        help_text="User's writing goals and preferences")
    personality_preference = models.CharField(
        max_length=20,
        choices=PERSONALITY_CHOICES,
        default='professional',
        help_text="Choose how you'd like the AI to interact with you"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

class ChatSession(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='chat_sessions')
    phase = models.CharField(
        max_length=20,
        choices=Event.WRITING_PHASE_CHOICES,
        default='facts'
    )
    title = models.CharField(max_length=200, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    messages_json = models.TextField()
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event', 'phase', 'timestamp'], name='chat_session_lookup_idx'),
        ]
    
    def set_messages(self, messages):
        self.messages_json = json.dumps(messages)
    
    def get_messages(self):
        return json.loads(self.messages_json) if self.messages_json else []
    
    def __str__(self):
        return f"{self.event.title} - {self.phase} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"
    
    def get_formatted_date(self):
        return self.timestamp.strftime("%B %d, %Y %I:%M %p")

# Signal to create UserProfile when a new User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance, personality_preference='professional')

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance, personality_preference='professional')
