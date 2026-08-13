from rest_framework import serializers
from .models import UserProfile, Exercise, Result


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['id', 'vk_id', 'first_name', 'last_name', 'registered_at']


class ExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = ['id', 'title', 'description', 'type', 'order']


class ResultSerializer(serializers.ModelSerializer):
    exercise_title = serializers.ReadOnlyField(source='exercise.title')

    class Meta:
        model = Result
        fields = [
            'id', 'user_profile', 'exercise', 'exercise_title',
            'result_data', 'is_approved', 'corrected_data',
            'correction_comment', 'completed_at'
        ]
        read_only_fields = ['user_profile', 'completed_at']