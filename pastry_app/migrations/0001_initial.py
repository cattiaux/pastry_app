# Generated by Django 4.2.6 on 2025-03-21 21:30

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Category",
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
                    "category_name",
                    models.CharField(max_length=200, verbose_name="category_name"),
                ),
                (
                    "category_type",
                    models.CharField(
                        choices=[
                            ("ingredient", "Ingrédient"),
                            ("recipe", "Recette"),
                            ("both", "Les deux"),
                        ],
                        max_length=10,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Ingredient",
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
                ("ingredient_name", models.CharField(max_length=200)),
            ],
            options={
                "ordering": ["ingredient_name"],
            },
        ),
        migrations.CreateModel(
            name="IngredientCategory",
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
            ],
        ),
        migrations.CreateModel(
            name="IngredientLabel",
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
            ],
        ),
        migrations.CreateModel(
            name="IngredientPrice",
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
                    "brand_name",
                    models.CharField(
                        blank=True, default=None, max_length=200, null=True
                    ),
                ),
                (
                    "quantity",
                    models.FloatField(
                        validators=[django.core.validators.MinValueValidator(0)]
                    ),
                ),
                (
                    "unit",
                    models.CharField(
                        choices=[
                            ("g", "Grams"),
                            ("kg", "Kilograms"),
                            ("ml", "Milliliters"),
                            ("cl", "Centiliters"),
                            ("l", "Liters"),
                            ("tsp", "Teaspoons"),
                            ("tbsp", "Tablespoons"),
                            ("cas", "Cuillère à soupe"),
                            ("cc", "Cuillère à café"),
                            ("cup", "Cups"),
                            ("unit", "Unit"),
                        ],
                        max_length=50,
                    ),
                ),
                (
                    "price",
                    models.FloatField(
                        validators=[django.core.validators.MinValueValidator(0)]
                    ),
                ),
                (
                    "date",
                    models.DateField(
                        blank=True, default=django.utils.timezone.now, null=True
                    ),
                ),
                ("is_promo", models.BooleanField(default=False)),
                ("promotion_end_date", models.DateField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="IngredientPriceHistory",
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
                    "ingredient_name",
                    models.CharField(blank=True, default="", max_length=255, null=True),
                ),
                (
                    "brand_name",
                    models.CharField(
                        blank=True, default=None, max_length=200, null=True
                    ),
                ),
                (
                    "quantity",
                    models.FloatField(
                        validators=[django.core.validators.MinValueValidator(0)]
                    ),
                ),
                (
                    "unit",
                    models.CharField(
                        choices=[
                            ("g", "Grams"),
                            ("kg", "Kilograms"),
                            ("ml", "Milliliters"),
                            ("cl", "Centiliters"),
                            ("l", "Liters"),
                            ("tsp", "Teaspoons"),
                            ("tbsp", "Tablespoons"),
                            ("cas", "Cuillère à soupe"),
                            ("cc", "Cuillère à café"),
                            ("cup", "Cups"),
                            ("unit", "Unit"),
                        ],
                        max_length=50,
                    ),
                ),
                (
                    "price",
                    models.FloatField(
                        validators=[django.core.validators.MinValueValidator(0)]
                    ),
                ),
                ("is_promo", models.BooleanField(default=False)),
                ("promotion_end_date", models.DateField(blank=True, null=True)),
                (
                    "date",
                    models.DateField(
                        blank=True, default=django.utils.timezone.now, null=True
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Label",
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
                    "label_name",
                    models.CharField(
                        max_length=200, unique=True, verbose_name="label_name"
                    ),
                ),
                (
                    "label_type",
                    models.CharField(
                        choices=[
                            ("ingredient", "Ingrédient"),
                            ("recipe", "Recette"),
                            ("both", "Les deux"),
                        ],
                        default="both",
                        max_length=10,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Pan",
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
                    "pan_name",
                    models.CharField(
                        blank=True, max_length=200, null=True, unique=True
                    ),
                ),
                (
                    "pan_type",
                    models.CharField(
                        choices=[
                            ("ROUND", "Rond"),
                            ("RECTANGLE", "Rectangulaire"),
                            ("CUSTOM", "Silicone / Forme libre"),
                        ],
                        max_length=20,
                    ),
                ),
                ("pan_brand", models.CharField(blank=True, max_length=100, null=True)),
                (
                    "diameter",
                    models.FloatField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0.1)],
                    ),
                ),
                (
                    "height",
                    models.FloatField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0.1)],
                    ),
                ),
                (
                    "length",
                    models.FloatField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0.1)],
                    ),
                ),
                (
                    "width",
                    models.FloatField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0.1)],
                    ),
                ),
                (
                    "rect_height",
                    models.FloatField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0.1)],
                    ),
                ),
                (
                    "volume_raw",
                    models.FloatField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "unit",
                    models.CharField(
                        choices=[("cm3", "cm³"), ("L", "Litres")],
                        default="cm3",
                        max_length=4,
                    ),
                ),
                (
                    "volume_cm3_cache",
                    models.FloatField(blank=True, editable=False, null=True),
                ),
            ],
            options={
                "ordering": ["pan_name", "pan_type"],
            },
        ),
        migrations.CreateModel(
            name="Recipe",
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
                ("recipe_name", models.CharField(max_length=200)),
                ("chef_name", models.CharField(blank=True, max_length=200, null=True)),
                (
                    "default_volume",
                    models.FloatField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "default_servings",
                    models.IntegerField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "avg_density",
                    models.FloatField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("trick", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["recipe_name", "chef_name"],
            },
        ),
        migrations.CreateModel(
            name="SubRecipe",
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
                    "quantity",
                    models.FloatField(
                        validators=[django.core.validators.MinValueValidator(0)]
                    ),
                ),
                (
                    "unit",
                    models.CharField(
                        choices=[
                            ("g", "Grams"),
                            ("kg", "Kilograms"),
                            ("ml", "Milliliters"),
                            ("cl", "Centiliters"),
                            ("l", "Liters"),
                            ("tsp", "Teaspoons"),
                            ("tbsp", "Tablespoons"),
                            ("cas", "Cuillère à soupe"),
                            ("cc", "Cuillère à café"),
                            ("cup", "Cups"),
                            ("unit", "Unit"),
                        ],
                        max_length=50,
                    ),
                ),
                (
                    "recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="main_recipes",
                        to="pastry_app.recipe",
                    ),
                ),
                (
                    "sub_recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="used_in_recipes",
                        to="pastry_app.recipe",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Store",
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
                ("store_name", models.CharField(max_length=200)),
                ("city", models.CharField(blank=True, max_length=100, null=True)),
                ("zip_code", models.CharField(blank=True, max_length=10, null=True)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["store_name", "city", "zip_code"],
                        name="pastry_app__store_n_cde1df_idx",
                    )
                ],
                "unique_together": {("store_name", "city", "zip_code")},
            },
        ),
        migrations.CreateModel(
            name="RecipeStep",
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
                    "step_number",
                    models.IntegerField(
                        validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                ("instruction", models.TextField(max_length=250)),
                ("trick", models.TextField(blank=True, max_length=100, null=True)),
                (
                    "recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="steps",
                        to="pastry_app.recipe",
                    ),
                ),
            ],
            options={
                "ordering": ["recipe", "step_number"],
            },
        ),
        migrations.CreateModel(
            name="RecipeLabel",
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
                    "label",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="pastry_app.label",
                    ),
                ),
                (
                    "recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="pastry_app.recipe",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RecipeIngredient",
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
                    "quantity",
                    models.FloatField(
                        validators=[django.core.validators.MinValueValidator(0)]
                    ),
                ),
                (
                    "unit",
                    models.CharField(
                        choices=[
                            ("g", "Grams"),
                            ("kg", "Kilograms"),
                            ("ml", "Milliliters"),
                            ("cl", "Centiliters"),
                            ("l", "Liters"),
                            ("tsp", "Teaspoons"),
                            ("tbsp", "Tablespoons"),
                            ("cas", "Cuillère à soupe"),
                            ("cc", "Cuillère à café"),
                            ("cup", "Cups"),
                            ("unit", "Unit"),
                        ],
                        max_length=50,
                    ),
                ),
                (
                    "display_name",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "ingredient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ingredient_recipes",
                        to="pastry_app.ingredient",
                    ),
                ),
                (
                    "recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="recipe_ingredients",
                        to="pastry_app.recipe",
                    ),
                ),
            ],
            options={
                "ordering": ["recipe", "ingredient"],
            },
        ),
        migrations.CreateModel(
            name="RecipeCategory",
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
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="pastry_app.category",
                    ),
                ),
                (
                    "recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="pastry_app.recipe",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="recipe",
            name="categories",
            field=models.ManyToManyField(
                related_name="recipes",
                through="pastry_app.RecipeCategory",
                to="pastry_app.category",
            ),
        ),
        migrations.AddField(
            model_name="recipe",
            name="ingredients",
            field=models.ManyToManyField(
                related_name="recipes",
                through="pastry_app.RecipeIngredient",
                to="pastry_app.ingredient",
            ),
        ),
        migrations.AddField(
            model_name="recipe",
            name="pan",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="pastry_app.pan",
            ),
        ),
        migrations.AddField(
            model_name="recipe",
            name="parent_recipe",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="versions",
                to="pastry_app.recipe",
            ),
        ),
        migrations.AddConstraint(
            model_name="pan",
            constraint=models.UniqueConstraint(
                fields=("pan_name",), name="unique_pan_name"
            ),
        ),
        migrations.AddField(
            model_name="ingredientpricehistory",
            name="ingredient",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="pastry_app.ingredient",
            ),
        ),
        migrations.AddField(
            model_name="ingredientpricehistory",
            name="store",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="pastry_app.store",
            ),
        ),
        migrations.AddField(
            model_name="ingredientprice",
            name="ingredient",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="prices",
                to="pastry_app.ingredient",
            ),
        ),
        migrations.AddField(
            model_name="ingredientprice",
            name="store",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="prices",
                to="pastry_app.store",
            ),
        ),
        migrations.AddField(
            model_name="ingredientlabel",
            name="ingredient",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="pastry_app.ingredient"
            ),
        ),
        migrations.AddField(
            model_name="ingredientlabel",
            name="label",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to="pastry_app.label"
            ),
        ),
        migrations.AddField(
            model_name="ingredientcategory",
            name="category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to="pastry_app.category"
            ),
        ),
        migrations.AddField(
            model_name="ingredientcategory",
            name="ingredient",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="pastry_app.ingredient"
            ),
        ),
        migrations.AddField(
            model_name="ingredient",
            name="categories",
            field=models.ManyToManyField(
                blank=True, related_name="ingredients", to="pastry_app.category"
            ),
        ),
        migrations.AddField(
            model_name="ingredient",
            name="labels",
            field=models.ManyToManyField(
                blank=True, related_name="ingredients", to="pastry_app.label"
            ),
        ),
        migrations.AddField(
            model_name="category",
            name="parent_category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="subcategories",
                to="pastry_app.category",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="recipestep",
            unique_together={("recipe", "step_number")},
        ),
        migrations.AlterUniqueTogether(
            name="recipe",
            unique_together={("recipe_name", "chef_name")},
        ),
        migrations.AddConstraint(
            model_name="ingredientpricehistory",
            constraint=models.UniqueConstraint(
                fields=("ingredient", "store", "brand_name", "quantity", "unit"),
                name="unique_ingredient_price_history",
            ),
        ),
        migrations.AddConstraint(
            model_name="ingredientprice",
            constraint=models.UniqueConstraint(
                fields=("ingredient", "store", "brand_name", "quantity", "unit"),
                name="unique_ingredient_price",
            ),
        ),
    ]
