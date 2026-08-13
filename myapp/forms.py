from django import forms
from .models import Observation

class ObservationForm(forms.ModelForm):
    class Meta:
        model = Observation
        fields = ['title', 'description', 'location', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }