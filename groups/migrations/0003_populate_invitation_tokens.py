import uuid

from django.db import migrations


def generate_invitation_tokens(apps, schema_editor):
    AjoGroup = apps.get_model("groups", "AjoGroup")

    database = schema_editor.connection.alias

    groups = AjoGroup.objects.using(database).filter(
        invitation_token__isnull=True
    )

    for group in groups.iterator():
        AjoGroup.objects.using(database).filter(
            pk=group.pk
        ).update(
            invitation_token=uuid.uuid4()
        )


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0002_ajogroup_invitation_active_ajogroup_invitation_token"),
    ]

    operations = [
        migrations.RunPython(
            generate_invitation_tokens,
            migrations.RunPython.noop
        ),
    ]