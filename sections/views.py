from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import SectionTable
from .serializers import SectionTableSerializer


class IsOwnerOrShared(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return obj.owner == request.user or obj.is_shared
        return obj.owner == request.user


class SectionTableViewSet(viewsets.ModelViewSet):
    serializer_class = SectionTableSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrShared]

    def get_queryset(self):
        user = self.request.user
        section_type = self.request.query_params.get('section_type')
        queryset = SectionTable.objects.filter(
            Q(owner=user) | Q(is_shared=True)
        )
        if section_type:
            queryset = queryset.filter(section_type=section_type)
        return queryset

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def save_content(self, request, pk=None):
        table = self.get_object()
        content = request.data.get('content', {})
        table.content = content
        table.save()
        return Response({'status': 'saved'})
    