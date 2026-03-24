from rest_framework import serializers
from .models import SectionTable


class SectionTableSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = SectionTable
        fields = ['id', 'owner', 'section_type', 'title', 'content', 'created_at', 'updated_at']
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']