# sections/serializers.py
from rest_framework import serializers
from .models import SectionTable
from users.serializers import UserListSerializer


class SectionTableSerializer(serializers.ModelSerializer):
    """
    Сериализатор для таблиц разделов
    """
    owner = UserListSerializer(read_only=True)
    owner_username = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = SectionTable
        fields = [
            'id',
            'title',
            'section_type',
            'owner',
            'owner_username',
            'content',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']

    def create(self, validated_data):
        """
        При создании таблицы автоматически устанавливаем owner из request
        """
        request = self.context.get('request')
        if request:
            validated_data['owner'] = request.user
        return super().create(validated_data)
