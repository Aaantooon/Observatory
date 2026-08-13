from django import forms
from .models import SocialAccount, Post

class SocialAccountForm(forms.ModelForm):
    class Meta:
        model = SocialAccount
        fields = ['platform', 'name', 'chat_id', 'token', 'active']

class PostForm(forms.ModelForm):
    platforms = forms.ModelMultipleChoiceField(
        queryset=SocialAccount.objects.filter(active=True),
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
    class Meta:
        model = Post
        fields = ['text', 'image', 'platforms']