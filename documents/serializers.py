# documents/serializers.py
from rest_framework import serializers
from .models import Document
from users.serializers import UserListSerializer


class DocumentSerializer(serializers.ModelSerializer):
    """
    Сериализатор для документов
    """
    owner = UserListSerializer(read_only=True)
    owner_username = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = Document
        fields = [
            'id',
            'title',
            'doc_type',
            'owner',
            'owner_username',
            'content',
            'is_editable',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if request:
            validated_data['owner'] = request.user
        return super().create(validated_data)
