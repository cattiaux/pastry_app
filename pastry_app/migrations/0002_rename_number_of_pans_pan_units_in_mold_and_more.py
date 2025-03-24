# Generated by Django 4.2.6 on 2025-03-24 19:30

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pastry_app", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="pan",
            old_name="number_of_pans",
            new_name="units_in_mold",
        ),
        migrations.AddField(
            model_name="pan",
            name="is_total_volume",
            field=models.BooleanField(
                default=False,
                help_text="True si volume_raw est le volume total (toutes empreintes confondues), False si c'est le volume unitaire.",
            ),
        ),
        migrations.AddField(
            model_name="recipe",
            name="pan_quantity",
            field=models.PositiveIntegerField(
                default=1,
                help_text="Nombre d'exemplaires de ce moule utilisés dans cette recette (ex: 6 cercles individuels).",
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
    ]
