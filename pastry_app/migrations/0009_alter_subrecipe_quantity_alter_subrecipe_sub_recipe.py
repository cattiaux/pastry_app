# Generated by Django 4.2.6 on 2025-03-20 15:46

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("pastry_app", "0008_recipeingredient_display_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="subrecipe",
            name="quantity",
            field=models.FloatField(
                validators=[django.core.validators.MinValueValidator(0)]
            ),
        ),
        migrations.AlterField(
            model_name="subrecipe",
            name="sub_recipe",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="used_in_recipes",
                to="pastry_app.recipe",
            ),
        ),
    ]
