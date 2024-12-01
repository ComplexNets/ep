from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Event(models.Model):
    WRITING_PHASE_CHOICES = [
        ('facts', 'Factual Description'),
        ('feelings', 'Emotional Response'),
        ('associations', 'Behavioral Associations'),
        ('growth', 'Positive Reframing & Growth')
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
