from django import forms
from .models import UserProfile, Event

class UserProfileForm(forms.ModelForm):
    bio_context = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        required=False,
        help_text="Share any background information that would help personalize your writing experience."
    )
    writing_goals = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        required=False,
        help_text="What do you hope to achieve through expressive writing?"
    )

    class Meta:
        model = UserProfile
        fields = ['bio_context', 'writing_goals', 'personality_preference']
        widgets = {
            'bio_context': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'writing_goals': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'personality_preference': forms.Select(attrs={'class': 'form-control'}),
        }

class EventForm(forms.ModelForm):
    date_occurred = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="When did this event occur?"
    )
    
    class Meta:
        model = Event
        fields = ['title', 'description', 'date_occurred']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
        help_texts = {
            'title': "Give this event a meaningful title",
            'description': "Briefly describe what this event is about"
        }
