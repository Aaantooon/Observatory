from rest_framework import serializers
from .models import User, Exercise, Result

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'vk_id', 'first_name', 'last_name', 'registered_at', 'streak', 'last_activity_date']

class ExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = ['id', 'title', 'description', 'type', 'order']

class ResultSerializer(serializers.ModelSerializer):
    exercise_title = serializers.ReadOnlyField(source='exercise.title')
    
    class Meta:
        model = Result
        fields = [
            'id', 'user', 'exercise', 'exercise_title',
            'result_data', 'is_approved', 'corrected_data',
            'correction_comment', 'completed_at'
        ]
        read_only_fields = ['user', 'completed_at']