from pastry_app.models import (
    Ingredient, IngredientPrice, Recipe, RecipeIngredient, SubRecipe,
    Category, Label, Pan, RoundPan, SquarePan, RecipeStep
)
from django.utils.timezone import now

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

# Création des catégories et labels d’ingrédients
category_dairy = Category.objects.create(name="Produits laitiers")
category_sugar = Category.objects.create(name="Sucreries")
label_bio = Label.objects.create(name="Bio")
label_local = Label.objects.create(name="Local")

# Création d’un ingrédient (Beurre)
butter = Ingredient.objects.create(ingredient_name="Beurre")
butter.categories.add(category_dairy)
butter.labels.add(label_bio, label_local)

# Ajout de prix pour le beurre dans différents magasins
IngredientPrice.objects.create(
    ingredient=butter, brand="Président", store_name="Carrefour",
    date=now().date(), quantity=250, unit="g", price=2.50
)
IngredientPrice.objects.create(
    ingredient=butter, brand="Elle & Vire", store_name="Auchan",
    date=now().date(), quantity=250, unit="g", price=2.40
)

# Création d’une recette simple (Pâte brisée)
pate_brisee = Recipe.objects.create(
    recipe_name="Pâte Brisée", chef="Chef Pierre", default_volume=500, default_servings=6
)

# Ajout d’un ingrédient à la recette
RecipeIngredient.objects.create(recipe=pate_brisee, ingredient=butter, quantity=125, unit="g")

# Ajout d'étapes pour la recette
RecipeStep.objects.create(recipe=pate_brisee, step_number=1, instruction="Mélanger la farine et le beurre.")
RecipeStep.objects.create(recipe=pate_brisee, step_number=2, instruction="Ajouter l'eau et pétrir jusqu'à obtenir une pâte homogène.")

# Création d’une recette plus complexe avec une sous-recette (Tarte aux pommes)
tarte_pommes = Recipe.objects.create(
    recipe_name="Tarte aux pommes", chef="Chef Pierre", default_volume=1000, default_servings=8
)

# Ajout d’un ingrédient à la tarte aux pommes
pommes = Ingredient.objects.create(ingredient_name="Pommes")
RecipeIngredient.objects.create(recipe=tarte_pommes, ingredient=pommes, quantity=3, unit="unités")

# Ajout de la sous-recette (Utilisation de la pâte brisée)
SubRecipe.objects.create(recipe=tarte_pommes, sub_recipe=pate_brisee, quantity=1)

# Création de moules (1 rond, 1 carré)
round_pan = RoundPan.objects.create(pan_name="Moule rond 20cm", pan_type="ROUND", diameter=20, height=5)
square_pan = SquarePan.objects.create(pan_name="Moule carré 15cm", pan_type="SQUARE", length=15, width=15, height=5)

# Affichage des éléments créés
print("📌 Données de test insérées avec succès !")
print(f"Ingrédient créé : {butter.ingredient_name}")
print(f"Recette créée : {pate_brisee.recipe_name}")
print(f"Recette avec sous-recette : {tarte_pommes.recipe_name}")
print(f"Moules créés : {round_pan.pan_name}, {square_pan.pan_name}")
