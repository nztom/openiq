from django.db import migrations,models


class Migration(migrations.Migration):
    dependencies=[('guilds','0001_initial')]
    operations=[migrations.CreateModel(name='RequestLimit',fields=[('key',models.CharField(max_length=64,primary_key=True,serialize=False)),('count',models.PositiveIntegerField(default=0)),('expires',models.PositiveBigIntegerField(db_index=True))])]
