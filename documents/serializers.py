from rest_framework import serializers
from .models import Document, DocumentPermission


class DocumentPermissionSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = DocumentPermission
        fields = ['id', 'document', 'user', 'user_username', 'permission', 'granted_at']
        read_only_fields = ['granted_at']


class DocumentSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    folder_name = serializers.CharField(source='folder.name', read_only=True)
    is_editable = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id', 'owner', 'owner_username', 'title', 'doc_type', 'content',
            'folder', 'folder_name', 'created_at', 'updated_at', 'is_shared',
            'is_editable'
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']

    def get_is_editable(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if obj.owner == request.user:
            return True
        perm = DocumentPermission.objects.filter(
            document=obj, user=request.user, permission='write'
        ).first()
        return perm is not None


class DocumentListSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    doc_type_display = serializers.CharField(source='get_doc_type_display', read_only=True)

    class Meta:
        model = Document
        fields = [
            'id', 'title', 'doc_type', 'doc_type_display', 'owner_username',
            'folder', 'folder_name', 'updated_at', 'is_shared'
        ]
