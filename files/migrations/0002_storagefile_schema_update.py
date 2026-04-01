import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _noop(apps, schema_editor):
    pass


def _table_exists(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        return table_name in schema_editor.connection.introspection.table_names(cursor)


def _column_exists(schema_editor, table_name, column_name):
    if not _table_exists(schema_editor, table_name):
        return False
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(
            cursor, table_name
        )
    return any(col.name == column_name for col in description)


def _index_exists(schema_editor, table_name, index_name):
    if not _table_exists(schema_editor, table_name):
        return False
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(
            cursor, table_name
        )
    return index_name in constraints


class AddFieldIfMissing(migrations.AddField):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        if getattr(self.field, "remote_field", None) is not None:
            column_name = self.field.db_column or f"{self.name}_id"
        else:
            column_name = self.field.db_column or self.name
        if _column_exists(schema_editor, model._meta.db_table, column_name):
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)


class RemoveFieldIfExists(migrations.RemoveField):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.model_name)
        field = model._meta.get_field(self.name)
        if not _column_exists(schema_editor, model._meta.db_table, field.column):
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)


class AddIndexIfMissing(migrations.AddIndex):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        if _index_exists(schema_editor, model._meta.db_table, self.index.name):
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)


class RemoveIndexIfExists(migrations.RemoveIndex):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.model_name)
        if not _index_exists(schema_editor, model._meta.db_table, self.name):
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)


class DeleteModelIfExists(migrations.DeleteModel):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.name)
        if not _table_exists(schema_editor, model._meta.db_table):
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):
    dependencies = [
        ("files", "0001_initial"),
    ]

    operations = [
        AddFieldIfMissing(
            model_name="storagefile",
            name="file_name",
            field=models.CharField(
                blank=True, default="", max_length=255, verbose_name="РРјСЏ С„Р°Р№Р»Р°"
            ),
        ),
        migrations.AlterField(
            model_name="storagefile",
            name="mime_type",
            field=models.CharField(
                blank=True, default="", max_length=100, verbose_name="MIME С‚РёРї"
            ),
        ),
        migrations.AlterField(
            model_name="storagefile",
            name="size",
            field=models.BigIntegerField(
                default=0, verbose_name="Р Р°Р·РјРµСЂ (Р±Р°Р№С‚С‹)"
            ),
        ),
        migrations.AlterField(
            model_name="storagefile",
            name="folder",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="files",
                to="files.storagefolder",
                verbose_name="РџР°РїРєР°",
            ),
        ),
        migrations.AlterModelOptions(
            name="storagefile",
            options={
                "ordering": ["-uploaded_at"],
                "verbose_name": "Р¤Р°Р№Р»",
                "verbose_name_plural": "Р¤Р°Р№Р»С‹",
            },
        ),
        migrations.AlterModelOptions(
            name="storagefolder",
            options={
                "ordering": ["name"],
                "verbose_name": "РџР°РїРєР°",
                "verbose_name_plural": "РџР°РїРєРё",
                "unique_together": {("owner", "name", "parent")},
            },
        ),
        migrations.AlterField(
            model_name="auditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("upload", "рџ“¤ Р—Р°РіСЂСѓР·РєР°"),
                    ("download", "в¬‡пёЏ РЎРєР°С‡РёРІР°РЅРёРµ"),
                    ("delete", "рџ—‘пёЏ РЈРґР°Р»РµРЅРёРµ"),
                    ("share", "рџ”— РџСЂРµРґРѕСЃС‚Р°РІР»РµРЅРёРµ РґРѕСЃС‚СѓРїР°"),
                    ("login", "рџ”‘ Р’С…РѕРґ"),
                    ("logout", "рџљЄ Р’С‹С…РѕРґ"),
                    ("create", "вћ• РЎРѕР·РґР°РЅРёРµ"),
                    ("update", "вњЏпёЏ РћР±РЅРѕРІР»РµРЅРёРµ"),
                ],
                max_length=20,
                verbose_name="Р”РµР№СЃС‚РІРёРµ",
            ),
        ),
        AddFieldIfMissing(
            model_name="auditlog",
            name="file",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="audit_logs",
                to="files.storagefile",
                verbose_name="Р¤Р°Р№Р»",
            ),
        ),
        migrations.AlterField(
            model_name="auditlog",
            name="details",
            field=models.TextField(blank=True, verbose_name="Р”РµС‚Р°Р»Рё"),
        ),
        migrations.AlterField(
            model_name="auditlog",
            name="timestamp",
            field=models.DateTimeField(auto_now_add=True, verbose_name="Р”Р°С‚Р°"),
        ),
        migrations.AlterField(
            model_name="auditlog",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="audit_logs",
                to=settings.AUTH_USER_MODEL,
                verbose_name="РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ",
            ),
        ),
        DeleteModelIfExists(name="FileAccessPermission"),
        DeleteModelIfExists(name="FileLock"),
        RemoveFieldIfExists(model_name="storagefile", name="updated_at"),
        RemoveFieldIfExists(model_name="storagefile", name="is_shared"),
        migrations.AlterField(
            model_name="storagefile",
            name="file",
            field=models.FileField(
                upload_to="files.models.file_upload_path", verbose_name="Р¤Р°Р№Р»"
            ),
        ),
        RemoveIndexIfExists(
            model_name="storagefile", name="files_stora_is_shar_abe3ba_idx"
        ),
        AddIndexIfMissing(
            model_name="storagefile",
            index=models.Index(
                fields=["owner", "-uploaded_at"],
                name="files_stora_owner_upl_6d1d12_idx",
            ),
        ),
        AddIndexIfMissing(
            model_name="storagefile",
            index=models.Index(
                fields=["folder", "-uploaded_at"],
                name="files_stora_folder_upl_1a2b34_idx",
            ),
        ),
        migrations.RunPython(_noop, reverse_code=_noop),
    ]
