import django_filters

from .models import StorageFile, StorageFolder


class StorageFileFilter(django_filters.FilterSet):
    """Фильтр для файлов"""

    name = django_filters.CharFilter(field_name="file__name", lookup_expr="icontains")
    mime_type = django_filters.CharFilter(lookup_expr="icontains")
    is_shared = django_filters.BooleanFilter()
    uploaded_after = django_filters.DateFilter(
        field_name="uploaded_at", lookup_expr="gte"
    )
    uploaded_before = django_filters.DateFilter(
        field_name="uploaded_at", lookup_expr="lte"
    )
    size_min = django_filters.NumberFilter(field_name="size", lookup_expr="gte")
    size_max = django_filters.NumberFilter(field_name="size", lookup_expr="lte")

    class Meta:
        model = StorageFile
        fields = ["name", "mime_type", "is_shared", "owner"]


class StorageFolderFilter(django_filters.FilterSet):
    """Фильтр для папок"""

    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = StorageFolder
        fields = ["name", "owner", "parent"]
