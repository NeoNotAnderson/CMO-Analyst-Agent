"""
Django REST Framework Serializers for API

All serializers are skeleton implementations with TODOs.
You will implement the actual serialization logic.
"""

from rest_framework import serializers
from core.models import Prospectus
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class ProspectusSerializer(serializers.ModelSerializer):
    """
    Serializer for Prospectus model
    """
    class Meta:
        model = Prospectus
        fields = [
            'prospectus_id',
            'prospectus_name',
            'prospectus_file',
            'upload_date',
            'parse_status',
            'created_by'
        ]
        read_only_fields = ['prospectus_id', 'upload_date', 'parse_status']


class ChatMessageSerializer(serializers.Serializer):
    """
    Serializer for chat messages

    TODO: Define fields for chat messages
    Fields: id, role, content, timestamp, prospectus_id
    """
    id = serializers.CharField(read_only=True)
    role = serializers.ChoiceField(choices=['user', 'assistant', 'system'])
    content = serializers.CharField()
    timestamp = serializers.DateTimeField(read_only=True)
    prospectus_id = serializers.UUIDField(required=False, allow_null=True)


class UploadResponseSerializer(serializers.Serializer):
    """
    Serializer for prospectus upload response

    TODO: Define fields for upload response
    """
    prospectus_id = serializers.UUIDField()
    prospectus_name = serializers.CharField()
    status = serializers.CharField()
    message = serializers.CharField()
