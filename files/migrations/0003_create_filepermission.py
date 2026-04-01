from django.conf import settings
from django.db import migrations, models


def _table_exists(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        return table_name in schema_editor.connection.introspection.table_names(cursor)


def _index_exists(schema_editor, table_name, index_name):
    if not _table_exists(schema_editor, table_name):
        return False
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(
            cursor, table_name
        )
    return index_name in constraints


class CreateModelIfMissing(migrations.CreateModel):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.name)
        if _table_exists(schema_editor, model._meta.db_table):
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)


class AddIndexIfMissing(migrations.AddIndex):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        if _index_exists(schema_editor, model._meta.db_table, self.index.name):
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):
    dependencies = [
        ("files", "0002_storagefile_schema_update"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        CreateModelIfMissing(
            name="FilePermission",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "file_type",
                    models.CharField(
                        choices=[
                            ("storage_file", "Р¤Р°Р№Р»"),
                            ("section_table", "РўР°Р±Р»РёС†Р° СЂР°Р·РґРµР»Р°"),
                            ("document", "Р”РѕРєСѓРјРµРЅС‚"),
                        ],
                        max_length=20,
                        verbose_name="РўРёРї РѕР±СЉРµРєС‚Р°",
                    ),
                ),
                ("file_id", models.IntegerField(verbose_name="ID РѕР±СЉРµРєС‚Р°")),
                (
                    "permission",
                    models.CharField(
                        choices=[
                            ("read", "рџ‘ЃпёЏ РўРѕР»СЊРєРѕ С‡С‚РµРЅРёРµ"),
                            ("write", "вњЏпёЏ Р§С‚РµРЅРёРµ Рё Р·Р°РїРёСЃСЊ"),
                        ],
                        default="read",
                        max_length=10,
                        verbose_name="Р Р°Р·СЂРµС€РµРЅРёРµ",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name="Р”Р°С‚Р° РїСЂРµРґРѕСЃС‚Р°РІР»РµРЅРёСЏ",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="file_permissions",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ",
                    ),
                ),
            ],
            options={
                "verbose_name": "Р Р°Р·СЂРµС€РµРЅРёРµ",
                "verbose_name_plural": "Р Р°Р·СЂРµС€РµРЅРёСЏ",
                "unique_together": {("file_type", "file_id", "user")},
            },
        ),
        AddIndexIfMissing(
            model_name="filepermission",
            index=models.Index(
                fields=["file_type", "file_id", "user"],
                name="files_filep_file_ty_1f2a3b_idx",
            ),
        ),
        AddIndexIfMissing(
            model_name="filepermission",
            index=models.Index(
                fields=["user", "file_type"], name="files_filep_user_fi_3c4d5e_idx"
            ),
        ),
    ]
