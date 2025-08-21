import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enchante.settings')
django.setup()

from pastry_app.models import Ingredient, IngredientUnitReference, Category

"""
Script de préremplissage de la table IngredientUnitReference pour une base de données de pâtisserie.

Ce script crée automatiquement les références d'équivalences unité/poids pour les ingrédients courants utilisés en pâtisserie,
en s'appuyant sur le nom d'ingrédient existant en base (champ 'ingredient_name', insensible à la casse).
Ajoute un remplissage automatique facultatif pour les unités 'cas' et 'cac' 
en fonction d'une "forme" déduite de la catégorie de l’ingrédient: Forme physique/liquide | huile | sirop | poudre
Il évite toute gestion manuelle des IDs et ne crée aucune doublon.
À UTILISER APRÈS avoir peuplé la table Ingredient avec les ingrédients de base !

- Si une référence existe déjà pour un ingrédient et une unité données, elle n'est pas dupliquée.
- Si un ingrédient de la liste n'est pas trouvé, un avertissement est affiché (à corriger dans la base d'ingrédients).
"""

# ====== PARAMÈTRES DU BLOC AUTO (peuvent être ajustés) ======
ENABLE_AUTO_FORM_IUR = True   # mettre False pour désactiver l'auto
FORCE = False                 # True => met à jour les IUR existantes cas/cac issues des formes
UNITS = ("cas", "cac")        # doivent exister dans UNIT_CHOICES côté recette si utilisées
# g moyens par cuillère selon la forme
SPOON_FALLBACKS = {
    "cas": {"LIQUIDE": 15.0, "HUILE": 10.0, "SIROP": 20.0, "POUDRE": 8.0},
    "cac": {"LIQUIDE": 5.0,  "HUILE": 3.0,  "SIROP": 7.0,  "POUDRE": 3.0},
}
# Noms EXACTS des catégories enfants (insensibles à la casse lors de la recherche)
FORM_CATEGORIES = {
    "LIQUIDE": "liquide",
    "HUILE":   "huile",
    "SIROP":   "sirop",
    "POUDRE":  "poudre",
}
# Si un ingrédient a plusieurs formes, on tranche par priorité:
FORM_PRECEDENCE = ["HUILE", "SIROP", "LIQUIDE", "POUDRE"]

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
    {"ingredient_name": "gélatine (feuille)", "unit": "unit", "weight_in_grams": 2, "notes": "1 feuille de gélatine = 2g"},
]

def load_references_list():
    created = exists = missing = 0
    for ref in REFERENCES:
        try:
            ingredient = Ingredient.objects.get(ingredient_name__iexact=ref["ingredient_name"])
            obj, was_created = IngredientUnitReference.objects.get_or_create(
                ingredient=ingredient,
                unit=ref["unit"],
                user=None,
                guest_id=None,
                defaults={
                    "weight_in_grams": ref["weight_in_grams"],
                    "notes": ref.get("notes", ""),
                    "is_hidden": False,
                }
            )
            if was_created:
                created += 1
                print(f"[IUR new] {ingredient.ingredient_name} ({ref['unit']}) = {ref['weight_in_grams']} g")
            else:
                exists += 1
                print(f"[IUR ok ] {ingredient.ingredient_name} ({ref['unit']}) déjà présent")
        except Ingredient.DoesNotExist:
            missing += 1
            print(f"[IUR miss] ingr introuvable: {ref['ingredient_name']}")
    print(f"[IUR list] created={created} exists={exists} missing={missing}")

def auto_iur_from_form_categories(force: bool = False):
    """
    Crée/Met à jour des IUR par défaut pour cas/cac selon la 'forme' de l’ingrédient.
    Formes reconnues: liquide | huile | sirop | poudre (catégories enfants de 'Forme physique').
    Règles:
      - IUR spécifique (existante) prime; sans force, on ne modifie pas.
      - Si plusieurs formes attribuées, on tranche via FORM_PRECEDENCE.
    """
    # Récup catégories forme
    form_cats = {}
    for key, name in FORM_CATEGORIES.items():
        cat = Category.objects.filter(category_type="ingredient", category_name__iexact=name).first()
        if cat:
            form_cats[key] = cat
        else:
            print(f"[FORM warn] catégorie absente: {name}")

    if not form_cats:
        print("[FORM stop] aucune catégorie de forme trouvée.")
        return

    created = updated = skipped = 0
    qs = Ingredient.objects.prefetch_related("categories")

    for ing in qs:
        # détecte la/les formes de l’ingrédient
        forms = [k for k, cat in form_cats.items() if cat in ing.categories.all()]
        if not forms:
            continue
        if len(forms) > 1:
            forms.sort(key=lambda k: FORM_PRECEDENCE.index(k))
        form_key = forms[0]

        for unit in UNITS:
            grams = SPOON_FALLBACKS[unit][form_key]
            obj, was_created = IngredientUnitReference.objects.get_or_create(
                ingredient=ing, unit=unit, user=None, guest_id=None,
                defaults={"weight_in_grams": grams, "is_hidden": False, "notes": f"default {form_key.lower()}"},
            )
            if was_created:
                created += 1
                print(f"[FORM new] {ing.ingredient_name} {unit}={grams}g ({form_key})")
            else:
                if force and obj.weight_in_grams != grams:
                    obj.weight_in_grams = grams
                    obj.is_hidden = False
                    obj.notes = f"default {form_key.lower()}"
                    obj.save(update_fields=["weight_in_grams", "is_hidden", "notes"])
                    updated += 1
                    print(f"[FORM upd] {ing.ingredient_name} {unit}={grams}g ({form_key})")
                else:
                    skipped += 1

    print(f"[FORM sum] created={created} updated={updated} skipped={skipped}")

def main():
    # 1) Comportement historique
    load_references_list()
    # 2) Auto IUR par formes (facultatif, activé par défaut ici)
    if ENABLE_AUTO_FORM_IUR:
        auto_iur_from_form_categories(force=FORCE)

if __name__ == "__main__":
    main()