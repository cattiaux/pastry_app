from django.core.exceptions import ValidationError
from django.db import models as django_models
from django.db.models.functions import Abs
from .models import Recipe, Pan

"""
==============================================================
 LOGIQUE MÉTIER : ADAPTATION, SCALING ET SYNTHÈSES DE RECETTES
==============================================================

Ce module regroupe toutes les fonctions utilitaires liées à :
- L’adaptation (scaling) des recettes (plats et sous-recettes)
- Les calculs de portions, de volumes, de suggestions de moules
- La génération des synthèses complètes pour l’admin/API
- Les helpers de validation ou de normalisation métier

Toutes les fonctions sont organisées en blocs métiers pour
faciliter la compréhension et la relecture.

"""

# ============================================================
# 1. NORMALISATION & HELPERS GÉNÉRAUX
# ============================================================

def normalize_case(value):
    """ Normalise une chaîne (minuscules, strip, espaces) """
    if isinstance(value, str):  # Vérifie que c'est bien une chaîne
        return " ".join(value.strip().lower().split())  
    return value  # Retourne la valeur telle quelle si ce n'est pas une chaîne

# ============================================================
# 2. CALCULS DE MULTIPLICATEURS ET SCALING
# ============================================================

def calculate_quantity_multiplier(from_volume_cm3: float, to_volume_cm3: float) -> float:
    """
    Calcule le multiplicateur pour passer d’un volume source à un volume cible.
    """
    if from_volume_cm3 <= 0:
        raise ValueError("Le volume source doit être supérieur à 0")
    return to_volume_cm3 / from_volume_cm3

def apply_multiplier_to_ingredients(recipe, multiplier: float) -> list:
    """
    Applique un multiplicateur à tous les ingrédients d'une recette
    et retourne une nouvelle structure d'ingrédients recalculés.
    """
    adapted_ingredients = []
    for ri in recipe.recipe_ingredients.all():
        adapted_ingredients.append({
            "ingredient": ri.ingredient.id,
            "display_name": getattr(ri, "display_name", ""),
            "original_quantity": ri.quantity,
            "scaled_quantity": round(ri.quantity * multiplier, 2),
            "unit": ri.unit
        })
    return adapted_ingredients

# ============================================================
# 3. ADAPTATION / SCALING DE RECETTES (PLATS & SOUS-RECETTES)
# ============================================================

def adapt_recipe_with_target_volume(recipe, volume_target: float, volume_source: float = None) -> dict:
    """
    Fonction principale d’adaptation d’une recette à un volume cible.
    Utilisable avec un volume provenant d’un moule ou d’un nombre de portions.
    - Calcule le multiplicateur à partir du volume source (soit moule soit fourni manuellement)
    - Applique ce multiplicateur aux ingrédients
    - Estime un intervalle réaliste de portions sur le volume cible
    [⚠️ Uniquement les ingrédients directs, NE traite pas les sous-recettes]
    """
    if volume_source is None:
        if not recipe.pan or not recipe.pan.volume_cm3_cache:
            raise ValueError("Le moule d’origine de la recette est manquant ou invalide.")
        volume_source = recipe.pan.volume_cm3_cache

    multiplier = calculate_quantity_multiplier(volume_source, volume_target)
    adapted_ingredients = apply_multiplier_to_ingredients(recipe, multiplier)
    servings_info = get_servings_interval(volume_target)

    return {
        "recipe_id": recipe.id,
        "source_volume": volume_source,
        "target_volume": volume_target,
        "multiplier": multiplier,
        "ingredients": adapted_ingredients,
        "estimated_servings": servings_info["standard"],
        "estimated_servings_min": servings_info["min"],
        "estimated_servings_max": servings_info["max"]
    }

def adapt_recipe_pan_to_pan(recipe, target_pan) -> dict:
    """
    Adapte une recette d’un moule vers un autre moule (flat).
    """
    if not target_pan.volume_cm3_cache:
        raise ValueError("Le volume du moule cible est inconnu.")
    return adapt_recipe_with_target_volume(recipe, target_pan.volume_cm3_cache)

def adapt_recipe_servings_to_volume(recipe, target_servings: int) -> dict:
    """
    Adapte une recette à un nombre de portions cible (volume déduit via le pan de la recette) (flat).
    """
    if target_servings <= 0:
        raise ValueError("Le nombre de portions cible doit être supérieur à 0.")

    volume_target = target_servings * 150
    base_data = adapt_recipe_with_target_volume(recipe, volume_target)

    base_data["suggested_pans"] = get_suggested_pans(volume_target)
    return base_data

def adapt_recipe_servings_to_servings(recipe, target_servings: int) -> dict:
    """
    Adapte une recette à un nombre de portions cible (flat),
    en se basant sur servings_min et servings_max (sans moule).
    """
    if not recipe.servings_min:
        raise ValueError("La recette n’a pas d’information sur le nombre de portions d’origine.")
    if target_servings <= 0:
        raise ValueError("Le nombre de portions cible doit être supérieur à 0.")

    volume_source = servings_to_volume(recipe.servings_min, recipe.servings_max)
    volume_target = target_servings * 150

    data = adapt_recipe_with_target_volume(recipe, volume_target, volume_source)

    data["source_servings"] = (recipe.servings_min + recipe.servings_max) / 2 if recipe.servings_max else recipe.servings_min
    data["target_volume"] = volume_target
    data["estimated_servings"] = target_servings
    data["suggested_pans"] = get_suggested_pans(volume_target)

    return data

def scale_sub_recipe(sub_recipe, required_quantity):
    """
    Adapte les quantités de tous les ingrédients d’une sous-recette à une quantité cible.

    Met à jour les quantités (scaling) proportionnellement au ratio entre la quantité par défaut
    de la sous-recette et la quantité demandée. [MÉTIER : appelé lors du scaling récursif]
    Modifie directement les objets en base (peut être adapté pour renvoyer un résultat pur).
    """
    # Get the default quantity of the sub-recipe
    default_quantity = sub_recipe.quantity

    # Calculate the scaling factor
    scaling_factor = required_quantity / default_quantity

    # Scale the quantities of the ingredients
    for recipe_ingredient in sub_recipe.recipeingredient_set.all():
        recipe_ingredient.quantity *= scaling_factor
        recipe_ingredient.save()

# (On prévoit ici d’ajouter “adapt_recipe_recursively_with_subrecipes” plus tard)

# ============================================================
# 4. CALCULS & SYNTHÈSES AUTOUR DES PORTIONS ET VOLUMES
# ============================================================

def get_servings_interval(volume_cm3: float) -> dict:
    """
    Calcule un intervalle réaliste de portions (min, standard, max) basé sur le volume.
    Hypothèse standard : 150ml = portion standard
    """
    if volume_cm3 <= 0:
        raise ValueError("Volume invalide pour estimer les portions.")

    standard = round(volume_cm3 / 150)

    if standard <= 2:
        min_servings = max(1, standard)
        max_servings = standard
    elif standard <= 11:
        min_servings = standard - 1
        max_servings = standard + 1
    else:
        min_servings = standard - 1
        max_servings = standard + 2

    return {"standard": standard, "min": min_servings, "max": max_servings}

def servings_to_volume(servings_min: int, servings_max: int = None) -> float:
    """
    Calcule un volume estimé en ml à partir d’un nombre de portions.
    Si servings_max est donné, utilise la moyenne.
    """
    if servings_max:
        servings = (servings_min + servings_max) / 2
    else:
        servings = servings_min

    return servings * 150

def get_suggested_pans(volume_target: float) -> list:
    """
    Retourne les moules dont le volume est dans une plage de ±5% autour du volume cible.
    Inclut une estimation des portions pour chaque moule.
    """
    suggested = []
    for pan in Pan.objects.filter(
        volume_cm3_cache__gte=volume_target * 0.95,
        volume_cm3_cache__lte=volume_target * 1.05
    ):
        servings_info = get_servings_interval(pan.volume_cm3_cache)
        suggested.append({"id": pan.id, "pan_name": pan.pan_name, "volume_cm3_cache": pan.volume_cm3_cache, 
                          "servings_min": servings_info["min"], "servings_max": servings_info["max"]})

    return suggested

def estimate_servings_from_pan(pan: Pan = None, pan_type: str = None, diameter: float = None, height: float = None, length: float = None, 
                               width: float = None, rect_height: float = None, volume_raw: float = None) -> dict:
    """
    Estime le volume et l’intervalle de portions à partir d’un pan existant ou de dimensions fournies.
    """
    if pan:
        volume = pan.volume_cm3_cache
    elif pan_type == "ROUND" and diameter and height:
        volume = math.pi * (diameter / 2) ** 2 * height
    elif pan_type == "RECTANGLE" and length and width and rect_height:
        volume = length * width * rect_height
    elif pan_type == "OTHER" and volume_raw:
        volume = volume_raw
    else:
        raise ValueError("Les informations fournies sont insuffisantes pour calculer le volume.")

    servings = get_servings_interval(volume)

    return {
        "volume_cm3": round(volume, 2),
        "estimated_servings_standard": servings["standard"],
        "estimated_servings_min": servings["min"],
        "estimated_servings_max": servings["max"]
    }

def suggest_pans_for_servings(target_servings: int) -> dict:
    """
    Propose les moules adaptés pour un nombre de portions donné (sans passer par une recette).

    Utilise le calcul de volume cible estimé à partir des portions,
    puis propose la/les références de moules qui correspondent au mieux.
    [MÉTIER: suggestion automatique à la création/adaptation de recette]
    """
    if target_servings <= 0:
        raise ValueError("Le nombre de portions doit être supérieur à 0.")

    # Calcul du volume cible
    target_volume = target_servings * 150

    # Recherche des moules compatibles (+/- 5%)
    lower_bound = target_volume * 0.95
    upper_bound = target_volume * 1.05

    suggested_pans = Pan.objects.filter(
        volume_cm3_cache__gte=lower_bound,
        volume_cm3_cache__lte=upper_bound
    )

    # Si aucun moule parfaitement compatible → proposer le plus proche
    if not suggested_pans.exists():
        closest_pan = Pan.objects.order_by(Abs(django_models.F("volume_cm3_cache") - target_volume)).first()
        suggested_pans = [closest_pan] if closest_pan else []

    # Construction de la réponse
    pans_data = []
    for pan in suggested_pans:
        servings = get_servings_interval(pan.volume_cm3_cache)
        pans_data.append({
            "id": pan.id,
            "pan_name": pan.pan_name,
            "volume_cm3_cache": pan.volume_cm3_cache,
            "estimated_servings_min": servings["min"],
            "estimated_servings_standard": servings["standard"],
            "estimated_servings_max": servings["max"],
        })

    return {"target_volume_cm3": round(target_volume, 2), "suggested_pans": pans_data}

# ============================================================
# 5. ADAPTATION PAR CONTRAINTE D’INGRÉDIENTS (SCALING “LIMITANT”)
# ============================================================

def adapt_recipe_by_ingredients_constraints(recipe, ingredient_constraints: dict) -> dict:
    """
    Adapte une recette selon les quantités d’ingrédients réellement disponibles.

    :param recipe: instance de Recipe
    :param ingredient_constraints: dict sous la forme {ingredient_id: quantity_disponible, ...}
    :return: dict avec les quantités adaptées, le multiplicateur appliqué, l’ingrédient limitant, volumes estimés
    """

    if not recipe.recipe_ingredients.exists():
        raise ValidationError("La recette ne contient aucun ingrédient.")

    if not ingredient_constraints:
        raise ValidationError("Aucune contrainte de quantité d’ingrédient n’a été fournie.")

    multipliers = []

    for recipe_ingredient in recipe.recipe_ingredients.all():
        ingredient_id = recipe_ingredient.ingredient.id

        if ingredient_id in ingredient_constraints:
            available_quantity = ingredient_constraints[ingredient_id]
            if available_quantity <= 0:
                raise ValidationError(f"La quantité fournie pour l’ingrédient '{recipe_ingredient.ingredient}' doit être positive.")
            
            multiplier = available_quantity / recipe_ingredient.quantity
            multipliers.append((multiplier, ingredient_id))

    if not multipliers:
        raise ValidationError("Aucune correspondance entre les ingrédients de la recette et les contraintes fournies.")

    # Facteur limitant = le plus petit multiplicateur
    final_multiplier, limiting_ingredient_id = min(multipliers, key=lambda x: x[0])

    adapted_ingredients = []
    for recipe_ingredient in recipe.recipe_ingredients.all():
        adapted_ingredients.append({
            "ingredient_id": recipe_ingredient.ingredient.id,
            "ingredient_name": recipe_ingredient.ingredient.ingredient_name,
            "display_name": getattr(recipe_ingredient, "display_name", ""),
            "original_quantity": recipe_ingredient.quantity,
            "scaled_quantity": round(recipe_ingredient.quantity * final_multiplier, 2),
            "unit": recipe_ingredient.unit,
        })

    # Volume estimé (si la recette a un pan ou servings, sinon None)
    volume_source = None
    if recipe.pan and recipe.pan.volume_cm3_cache:
        volume_source = recipe.pan.volume_cm3_cache
    elif recipe.servings_min and recipe.servings_max:
        volume_source = round((recipe.servings_min + recipe.servings_max) / 2 * 150)

    volume_target = round(volume_source * final_multiplier, 2) if volume_source else None

    return {
        "recipe_id": recipe.id,
        "limiting_ingredient_id": limiting_ingredient_id,
        "multiplier": final_multiplier,
        "source_volume": volume_source,
        "target_volume": volume_target,
        "ingredients": adapted_ingredients
    }

# ============================================================
# 6. FONCTIONS “PURE” (math helpers, validation sans ORM, etc)
# ============================================================


# ============================================================
# 7. (DIVERS / À CLASSER)
# ============================================================

# Toute fonction orpheline à placer ici si besoin, avec commentaire métier ou TODO de classement.

