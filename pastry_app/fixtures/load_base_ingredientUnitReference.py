import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enchante.settings')
django.setup()

from pastry_app.models import Ingredient, IngredientUnitReference

"""
Script de préremplissage de la table IngredientUnitReference pour une base de données de pâtisserie.

Ce script crée automatiquement les références d'équivalences unité/poids pour les ingrédients courants utilisés en pâtisserie,
en s'appuyant sur le nom d'ingrédient existant en base (champ 'ingredient_name', insensible à la casse).
Il évite toute gestion manuelle des IDs et ne crée aucune doublon.
À UTILISER APRÈS avoir peuplé la table Ingredient avec les ingrédients de base !

- Si une référence existe déjà pour un ingrédient et une unité données, elle n'est pas dupliquée.
- Si un ingrédient de la liste n'est pas trouvé, un avertissement est affiché (à corriger dans la base d'ingrédients).
"""

# Ta table de correspondance de base, avec le nom d'ingrédient (slug ou exact)
REFERENCES = [
    # Oeuf & dérivés
    {"ingredient_name": "œuf", "unit": "unit", "weight_in_grams": 50, "notes": "Œuf moyen entier"},
    {"ingredient_name": "jaune d'œuf", "unit": "unit", "weight_in_grams": 17, "notes": "Jaune d'œuf seul"},
    {"ingredient_name": "blanc d'œuf", "unit": "unit", "weight_in_grams": 33, "notes": "Blanc d'œuf seul"},

    # Levures & poudres
    {"ingredient_name": "sachet de levure chimique", "unit": "unit", "weight_in_grams": 11, "notes": "Levure chimique (1 sachet)"},
    {"ingredient_name": "levure boulangère sèche", "unit": "cac", "weight_in_grams": 3, "notes": "1 cc = 3g"},
    {"ingredient_name": "levure boulangère sèche", "unit": "sachet", "weight_in_grams": 5, "notes": "Sachet standard"},
    {"ingredient_name": "bicarbonate de soude", "unit": "cac", "weight_in_grams": 5, "notes": "1 cc = 5g"},

    # Lait & Crèmes
    {"ingredient_name": "lait", "unit": "ml", "weight_in_grams": 1, "notes": "1ml = 1g (eau/lait)"},
    {"ingredient_name": "lait", "unit": "cup", "weight_in_grams": 250, "notes": "1 cup = 250ml = 250g"},
    {"ingredient_name": "crème liquide", "unit": "ml", "weight_in_grams": 1, "notes": "1ml = 1g"},
    {"ingredient_name": "crème épaisse", "unit": "cas", "weight_in_grams": 20, "notes": "1 cuillère à soupe = 20g"},

    # Farine
    {"ingredient_name": "farine", "unit": "cas", "weight_in_grams": 10, "notes": "1 cuillère à soupe rase = 10g"},
    {"ingredient_name": "farine", "unit": "cac", "weight_in_grams": 3, "notes": "1 cuillère à café rase = 3g"},
    {"ingredient_name": "farine", "unit": "cup", "weight_in_grams": 120, "notes": "1 cup = 120g"},
    {"ingredient_name": "maïzena", "unit": "cas", "weight_in_grams": 8, "notes": "1 cuillère à soupe rase = 8g"},

    # Sucre & dérivés
    {"ingredient_name": "sucre", "unit": "cas", "weight_in_grams": 15, "notes": "1 cuillère à soupe = 15g"},
    {"ingredient_name": "sucre", "unit": "cac", "weight_in_grams": 5, "notes": "1 cuillère à café = 5g"},
    {"ingredient_name": "sucre", "unit": "cup", "weight_in_grams": 200, "notes": "1 cup = 200g"},
    {"ingredient_name": "sucre glace", "unit": "cas", "weight_in_grams": 12, "notes": "1 cuillère à soupe = 12g"},
    {"ingredient_name": "cassonade", "unit": "cas", "weight_in_grams": 14, "notes": "1 cuillère à soupe = 14g"},

    # Beurre, Margarine & Huiles
    {"ingredient_name": "beurre", "unit": "cas", "weight_in_grams": 12, "notes": "1 cuillère à soupe = 12g"},
    {"ingredient_name": "beurre", "unit": "noisette", "weight_in_grams": 5, "notes": "1 noisette de beurre = 5g"},
    {"ingredient_name": "beurre", "unit": "cup", "weight_in_grams": 240, "notes": "1 cup = 240g"},
    {"ingredient_name": "huile", "unit": "cas", "weight_in_grams": 10, "notes": "1 cuillère à soupe = 10g"},
    {"ingredient_name": "huile", "unit": "cac", "weight_in_grams": 3, "notes": "1 cuillère à café = 3g"},

    # Sel & épices
    {"ingredient_name": "sel", "unit": "cac", "weight_in_grams": 5, "notes": "1 cuillère à café = 5g"},
    {"ingredient_name": "fleur de sel", "unit": "cac", "weight_in_grams": 3, "notes": "1 cuillère à café = 3g"},
    {"ingredient_name": "cannelle", "unit": "cac", "weight_in_grams": 2, "notes": "1 cuillère à café = 2g"},
    {"ingredient_name": "cacao en poudre", "unit": "cas", "weight_in_grams": 8, "notes": "1 cuillère à soupe = 8g"},

    # Chocolat & fruits secs
    {"ingredient_name": "chocolat", "unit": "carré", "weight_in_grams": 5, "notes": "1 carré = 5g"},
    {"ingredient_name": "amande en poudre", "unit": "cas", "weight_in_grams": 10, "notes": "1 cuillère à soupe = 10g"},
    {"ingredient_name": "noisettes", "unit": "cas", "weight_in_grams": 10, "notes": "1 cuillère à soupe = 10g"},
    {"ingredient_name": "pistaches", "unit": "cas", "weight_in_grams": 10, "notes": "1 cuillère à soupe = 10g"},
    {"ingredient_name": "pépites de chocolat", "unit": "cas", "weight_in_grams": 15, "notes": "1 cuillère à soupe = 15g"},

    # Fruits courants (pour gâteaux, compotes)
    {"ingredient_name": "pomme", "unit": "unit", "weight_in_grams": 150, "notes": "Pomme moyenne"},
    {"ingredient_name": "banane", "unit": "unit", "weight_in_grams": 120, "notes": "Banane moyenne"},
    {"ingredient_name": "citron", "unit": "unit", "weight_in_grams": 60, "notes": "Citron jaune moyen"},
    {"ingredient_name": "orange", "unit": "unit", "weight_in_grams": 150, "notes": "Orange moyenne"},

    # Divers
    {"ingredient_name": "yaourt nature", "unit": "unit", "weight_in_grams": 125, "notes": "1 pot"},
    {"ingredient_name": "fromage blanc", "unit": "cas", "weight_in_grams": 20, "notes": "1 cuillère à soupe = 20g"},
    {"ingredient_name": "compote", "unit": "cas", "weight_in_grams": 20, "notes": "1 cuillère à soupe = 20g"},
    {"ingredient_name": "miel", "unit": "cas", "weight_in_grams": 25, "notes": "1 cuillère à soupe = 25g"},
    {"ingredient_name": "confiture", "unit": "cas", "weight_in_grams": 20, "notes": "1 cuillère à soupe = 20g"},
    {"ingredient_name": "pâte à tartiner", "unit": "cas", "weight_in_grams": 20, "notes": "1 cuillère à soupe = 20g"},
]

def main():
    for ref in REFERENCES:
        try:
            ingredient = Ingredient.objects.get(ingredient_name__iexact=ref["ingredient_name"])
            obj, created = IngredientUnitReference.objects.get_or_create(
                ingredient=ingredient,
                unit=ref["unit"],
                user=None,
                guest_id=None,
                defaults={
                    "weight_in_grams": ref["weight_in_grams"],
                    "notes": ref["notes"],
                    "is_hidden": False,
                }
            )
            if created:
                print(f"Ajouté : {ingredient.ingredient_name} ({ref['unit']}) = {ref['weight_in_grams']}g")
            else:
                print(f"Déjà existant : {ingredient.ingredient_name} ({ref['unit']})")
        except Ingredient.DoesNotExist:
            print(f"⚠️ Ingrédient introuvable : {ref['ingredient_name']}")

if __name__ == "__main__":
    main()
