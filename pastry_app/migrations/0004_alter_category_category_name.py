# Generated by Django 4.2.6 on 2025-03-07 15:27

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pastry_app", "0003_alter_category_category_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="category",
            name="category_name",
            field=models.CharField(max_length=200, verbose_name="category_name"),
        ),
    ]
