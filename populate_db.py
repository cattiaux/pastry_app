import os, django

# Définir les paramètres Django pour accéder aux modèles
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "enchante.settings")  
django.setup() # Initialiser Django

from pastry_app.models import (
    Category, Label, Ingredient, Recipe, RecipeIngredient, RecipeStep, SubRecipe,
    Pan, RoundPan, SquarePan, CustomPan, Store, IngredientPrice
)
from django.core.management.base import BaseCommand

# Suppression des anciennes données pour éviter les doublons
Ingredient.objects.all().delete()
IngredientPrice.objects.all().delete()
Recipe.objects.all().delete()
RecipeIngredient.objects.all().delete()
SubRecipe.objects.all().delete()
Category.objects.all().delete()
Label.objects.all().delete()
Pan.objects.all().delete()
RecipeStep.objects.all().delete()

# Liste des catégories initiales
CATEGORIES_INITIALES = [
    {"name": "Desserts", "type": "recipe", "parent": None},
    {"name": "Tartes", "type": "recipe", "parent": "Desserts"},
    {"name": "Entremets", "type": "recipe", "parent": "Desserts"},
    {"name": "Viennoiseries", "type": "recipe", "parent": None},
    {"name": "Fruits", "type": "ingredient", "parent": None},
    {"name": "Épices", "type": "ingredient", "parent": None},
    {"name": "Other", "type": "both", "parent": None},
]

# Labels initiaux
LABELS_INITIAUX = [
    {"name": "Bio", "type": "both"},
    {"name": "Local", "type": "both"},
    {"name": "Sans Gluten", "type": "both"},
    {"name": "Vegan", "type": "recipe"},
]

# Ingrédients de base avec prix et magasins
INGREDIENTS_INITIAUX = [
    {
        "name": "Beurre",
        "categories": ["Produits laitiers"],
        "labels": ["Bio"],
        "prices": [{"store": "Carrefour", "price": 2.5, "quantity": 250, "unit": "g"}],
    },
    {
        "name": "Pommes",
        "categories": ["Fruits"],
        "labels": [],
        "prices": [{"store": "Grand Frais", "price": 1.8, "quantity": 1, "unit": "kg"}],
    },
]

# Magasins initiaux
STORES_INITIAUX = [
    {"name": "Carrefour", "city": "Paris", "zip_code": "75001"},
    {"name": "Grand Frais", "city": "Lyon", "zip_code": "69003"},
    {"name": "Auchan", "city": "Marseille", "zip_code": "13008"},
]

# Recettes de base
RECIPES_INITIALES = [
    {
        "name": "Pâte Brisée",
        "chef": "Chef Pierre",
        "ingredients": [{"name": "Beurre", "quantity": 125, "unit": "g"}],
        "steps": [
            "Mélanger la farine et le beurre.",
            "Ajouter l'eau et pétrir jusqu'à obtenir une pâte homogène."
        ]
    },
    {
        "name": "Tarte aux pommes",
        "chef": "Chef Pierre",
        "ingredients": [{"name": "Pommes", "quantity": 3, "unit": "unités"}],
        "sub_recipes": ["Pâte Brisée"]
    }
]

# Création des moules
PANS_INITIAUX = [
    {"type": "ROUND", "name": "Moule rond 20cm", "diameter": 20, "height": 5},
    {"type": "SQUARE", "name": "Moule carré 15cm", "length": 15, "width": 15, "height": 5},
]

class Command(BaseCommand):
    help = "Initialise les données de la base de données."

    def handle(self, *args, **kwargs):
        self.stdout.write("Début de l'initialisation de la base de données...")

        # Création des catégories avec parent_category et category_type
        category_objects = {}
        for cat in CATEGORIES_INITIALES:
            parent = category_objects.get(cat["parent"]) if cat["parent"] else None
            obj, created = Category.objects.get_or_create(
                category_name=cat["name"], defaults={"category_type": cat["type"], "parent_category": parent}
            )
            category_objects[cat["name"]] = obj
            self.stdout.write(self.style.SUCCESS(f"{'✅ Ajout' if created else '⚠️ Déjà existant'} : {cat['name']}"))

        # Création des labels avec `label_type`
        for lbl in LABELS_INITIAUX:
            obj, created = Label.objects.get_or_create(label_name=lbl["name"], defaults={"label_type": lbl["type"]})
            self.stdout.write(self.style.SUCCESS(f"{'✅ Ajout' if created else '⚠️ Déjà existant'} : {lbl['name']}"))

        # Création des magasins avec `city` et `zip_code`
        store_objects = {}
        for store in STORES_INITIAUX:
            obj, created = Store.objects.get_or_create(
                store_name=store["name"], defaults={"city": store["city"], "zip_code": store["zip_code"]}
            )
            store_objects[store["name"]] = obj
            self.stdout.write(self.style.SUCCESS(f"{'✅ Ajout' if created else '⚠️ Déjà existant'} : {store['name']}"))

        # Création des ingrédients avec prix et magasins
        for ing in INGREDIENTS_INITIAUX:
            ingredient, created = Ingredient.objects.get_or_create(ingredient_name=ing["name"])
            self.stdout.write(self.style.SUCCESS(f"{'✅ Ajout' if created else '⚠️ Déjà existant'} : {ing['name']}"))

            for cat_name in ing["categories"]:
                category = Category.objects.filter(category_name=cat_name).first()
                if category:
                    ingredient.categories.add(category)

            for lbl_name in ing["labels"]:
                label = Label.objects.filter(label_name=lbl_name).first()
                if label:
                    ingredient.labels.add(label)

            # Création des prix des ingrédients
            for price_data in ing["prices"]:
                store = store_objects.get(price_data["store"])
                if store:
                    IngredientPrice.objects.get_or_create(
                        ingredient=ingredient,
                        store=store,
                        price=price_data["price"],
                        quantity=price_data["quantity"],
                        unit=price_data["unit"]
                    )
    
        # Création des recettes avec ingrédients et étapes
        for rec in RECIPES_INITIALES:
            recipe, created = Recipe.objects.get_or_create(recipe_name=rec["name"], chef_name=rec["chef"])
            self.stdout.write(self.style.SUCCESS(f"{'✅ Ajout' if created else '⚠️ Déjà existant'} : {rec['name']}"))

            # Ajout des ingrédients
            for ing in rec.get("ingredients", []):
                ingredient = Ingredient.objects.filter(ingredient_name=ing["name"]).first()
                if ingredient:
                    RecipeIngredient.objects.get_or_create(recipe=recipe, ingredient=ingredient, quantity=ing["quantity"], unit=ing["unit"])

            # Ajout des étapes
            for i, step in enumerate(rec.get("steps", []), start=1):
                RecipeStep.objects.get_or_create(recipe=recipe, step_number=i, instruction=step)

            # Ajout des sous-recettes
            for sub_rec_name in rec.get("sub_recipes", []):
                sub_recipe = Recipe.objects.filter(recipe_name=sub_rec_name).first()
                if sub_recipe:
                    SubRecipe.objects.get_or_create(recipe=recipe, sub_recipe=sub_recipe, quantity=1)

        # Création des moules
        for pan in PANS_INITIAUX:
            if pan["type"] == "ROUND":
                obj, created = RoundPan.objects.get_or_create(
                    pan_name=pan["name"], diameter=pan["diameter"], height=pan["height"]
                )
            elif pan["type"] == "SQUARE":
                obj, created = SquarePan.objects.get_or_create(
                    pan_name=pan["name"], length=pan["length"], width=pan["width"], height=pan["height"]
                )
            else:
                continue  # Type inconnu
            self.stdout.write(self.style.SUCCESS(f"{'✅ Ajout' if created else '⚠️ Déjà existant'} : {pan['name']}"))

        self.stdout.write(self.style.SUCCESS("🎉 Base de données initialisée avec succès !"))
