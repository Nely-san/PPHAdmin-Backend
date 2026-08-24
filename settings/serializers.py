from rest_framework import serializers
from settings.models import SystemParameter

class SystemParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemParameter
        fields = ['id', 'key', 'value', 'description', 'category', 'created_at', 'updated_at']
