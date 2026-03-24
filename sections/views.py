from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import SectionTable
from .serializers import SectionTableSerializer


class SectionTableViewSet(viewsets.ModelViewSet):
    serializer_class = SectionTableSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SectionTable.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def save_content(self, request, pk=None):
        table = self.get_object()
        table.content = request.data.get('content', {})
        table.save()
        return Response({'status': 'saved'})
