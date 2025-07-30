import math
from django.core.exceptions import ValidationError
from django.db import models as django_models
from django.db.models.functions import Abs
from .models import Pan

"""
=================================================
 BACKEND MÉTIER – SCALING/ADAPTATION DE RECETTE
=================================================

Toutes les fonctions métier d’adaptation, scaling, estimation, sont regroupées ici selon leur rôle.

L’entrée principale pour le scaling est :
    scale_recipe_recursively(recipe, target_servings=None, target_pan=None, target_volume=None)

Les helpers sont soit internes, soit exposés pour la suggestion/estimation.
"""

# ============================================================
# 0. NORMALISATION & HELPERS GÉNÉRAUX
# ============================================================

def normalize_case(value):
    """ Normalise une chaîne (minuscules, strip, espaces) """
    if isinstance(value, str):  # Vérifie que c'est bien une chaîne
        return " ".join(value.strip().lower().split())  
    return value  # Retourne la valeur telle quelle si ce n'est pas une chaîne

# ============================================================
# 1. HELPERS : CONVERSIONS VOLUMES / PORTIONS / MOULES
# ============================================================

def servings_to_volume(servings):
    """Convertit un nombre de portions en volume (ml/cm³)."""
    return servings * 150

def get_pan_volume(pan) -> float:
    """
    Retourne le volume (en cm³) du moule passé en argument.
    Si le volume est pré-calculé (pan.volume_cm3_cache), il est utilisé.
    Sinon, il est calculé à partir des dimensions et du type de moule.
    """
    if not pan:
        raise ValueError("Aucun moule (pan) fourni.")

    # Si le volume est déjà stocké
    if hasattr(pan, 'volume_cm3_cache') and pan.volume_cm3_cache:
        return float(pan.volume_cm3_cache)

    # Sinon, on recalcule selon le type de moule (exemples courants)
    pan_type = getattr(pan, 'pan_type', None)
    if pan_type == "ROUND":
        diameter = getattr(pan, 'diameter', None)
        height = getattr(pan, 'height', None)
        if diameter and height:
            return float(math.pi * (diameter / 2) ** 2 * height)
    elif pan_type == "RECTANGLE":
        length = getattr(pan, 'length', None)
        width = getattr(pan, 'width', None)
        rect_height = getattr(pan, 'rect_height', None) or getattr(pan, 'height', None)
        if length and width and rect_height:
            return float(length * width * rect_height)
    elif pan_type == "OTHER":
        volume_raw = getattr(pan, 'volume_raw', None)
        if volume_raw:
            return float(volume_raw)

    raise ValueError("Impossible de déterminer le volume du moule (pan) fourni.")

def get_source_volume(recipe):
    """
    Retourne un tuple (volume_source, mode) :
        - mode = 'pan' si la base est le pan d'origine,
        - mode = 'servings' sinon.

    Si la recette possède un pan : utilise le volume du pan
    Sinon : utilise la moyenne servings_min/servings_max (via serving_to_volume)
    """
    if getattr(recipe, "pan", None) and getattr(recipe.pan, "volume_cm3_cache", None):
        return recipe.pan.volume_cm3_cache, "pan"
    # Si pas de pan, on tente la moyenne des servings
    servings_min = getattr(recipe, "servings_min", None)
    servings_max = getattr(recipe, "servings_max", None)
    if servings_min and servings_max:
        return servings_to_volume((servings_min + servings_max) / 2), "servings"
    if servings_min:
        return servings_to_volume(servings_min), "servings"
    if servings_max:
        return servings_to_volume(servings_max), "servings"
    return None, None

def calculate_quantity_multiplier(from_volume_cm3: float, to_volume_cm3: float) -> float:
    """
    Calcule le multiplicateur pour passer d’un volume source à un volume cible.
    """
    if from_volume_cm3 <= 0:
        raise ValueError("Le volume source doit être supérieur à 0")
    return to_volume_cm3 / from_volume_cm3

# ============================================================
# 2. CALCUL DU MULTIPLICATEUR EN FONCTION DU CONTEXTE
# ============================================================

def get_scaling_multiplier(recipe, target_servings: int = None, target_pan = None) -> float:
    """
    Calcule le multiplicateur à appliquer à la recette selon le contexte cible :
    Priorité au pan d'origine s'il existe, sinon base servings_min/max
    """
    source_volume, source_mode = get_source_volume(recipe)
    if not source_volume:
        raise ValueError("Impossible de déterminer le volume source de la recette (ni pan ni servings d'origine).")

    if target_pan:
        target_volume = getattr(target_pan, "volume_cm3_cache", None)
        if not target_volume:
            raise ValueError("Le pan cible n'a pas de volume défini.")
    elif target_servings:
        target_volume = servings_to_volume(target_servings)
    else:
        raise ValueError("Il faut fournir une destination (target_pan ou target_servings) pour calculer le scaling.")

    return float(target_volume) / float(source_volume), source_mode

# ============================================================
# 3. SCALING / ADAPTATION DE RECETTE (MÉTIER)
# ============================================================

def scale_recipe_recursively(recipe, target_servings: int = None, target_pan = None) -> dict:
    """
    Fonction métier principale : adapte toute une recette (ingrédients ET sous-recettes, récursivement)
    selon un nombre de portions cible, un moule cible, ou un volume cible.
    Utilise les helpers pour calculer le multiplicateur, puis applique ce scaling partout.
    NE MODIFIE RIEN EN BASE.
    Retourne une structure complète : ingrédients adaptés, sous-recettes adaptées, scaling utilisé, etc.
    """
    # 1. Calcule le multiplicateur de scaling pour la recette courante
    scaling_multiplier, scaling_mode = get_scaling_multiplier(recipe, target_servings=target_servings, target_pan=target_pan)

    # 2. Scaling des ingrédients directs
    adapted_ingredients = _scale_ingredients_flat(recipe, scaling_multiplier)

    # 3. Scaling récursif des sous-recettes (si présentes)
    adapted_subrecipes = []
    for main_sub in recipe.main_recipes.all():
        sub_recipe = main_sub.sub_recipe
        if not hasattr(sub_recipe, 'default_quantity') or sub_recipe.default_quantity in (None, 0):
            raise ValueError(f"La sous-recette {sub_recipe} n’a pas de default_quantity définie.")
        # Le scaling à appliquer à la sous-recette dépend du ratio demandé
        sub_multiplier = (main_sub.quantity / sub_recipe.default_quantity) * scaling_multiplier
        adapted = scale_recipe_recursively(
            sub_recipe,
            target_servings=None,
            target_pan=None,
            target_volume=None,  # On propage juste le multiplicateur calculé
        )
        # Patch les quantités des ingrédients de la sous-recette avec sub_multiplier
        # (on peut ajouter le multiplicateur dans la synthèse si besoin)
        for ing in adapted["ingredients"]:
            ing["quantity"] = round(ing["quantity"] * sub_multiplier, 2) if ing["quantity"] is not None else None
        adapted_subrecipes.append({
            "sub_recipe_id": sub_recipe.id,
            "sub_recipe_name": getattr(sub_recipe, "name", ""),
            "quantity": main_sub.quantity,
            "unit": main_sub.unit,
            "ingredients": adapted["ingredients"],
            "subrecipes": adapted["subrecipes"],
            # Ajoute ici d’autres champs utiles (notes, etc.)
        })

    return {
        "recipe_id": recipe.id,
        "recipe_name": getattr(recipe, "name", ""),
        "scaling_multiplier": scaling_multiplier,
        "scaling_mode": scaling_mode,
        "ingredients": adapted_ingredients,
        "subrecipes": adapted_subrecipes,
    }

def _scale_ingredients_flat(recipe, multiplier: float) -> list:
    """
    Helper interne : adapte seulement les ingrédients directs de la recette (sans les sous-recettes) selon le multiplicateur donné.
    Retourne une liste de dicts {'ingredient', 'quantity', 'unit', ...} utilisables pour la synthèse ou l’API.
    NE MODIFIE RIEN en base !
    """
    adapted = []
    for ri in recipe.recipe_ingredients.all():
        adapted.append({
            "ingredient_id": ri.ingredient.id,
            "ingredient_name": ri.ingredient.ingredient_name,
            "display_name": getattr(ri, "display_name", ""),
            "quantity": round(ri.quantity * multiplier, 2) if ri.quantity is not None else None,
            "unit": ri.unit,
        })
    return adapted

# ============================================================
# 4. SUGGESTIONS ET ESTIMATIONS
# ============================================================

def get_servings_interval(volume_cm3: float) -> dict:
    """
    Calcule un intervalle réaliste de portions (min, standard, max) basé sur le volume.
    Utilisé dans la suggestion et l’estimation de moules/servings.
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

def suggest_pans_for_servings(target_servings: int) -> list:
    """
    Propose une liste de moules (pans) adaptés pour un nombre de portions cible (sans passer par une recette).
    Chaque suggestion contient les données du pan et une estimation du nombre de portions.
    Liste ordonnée (meilleur match en premier).
    """
    if target_servings <= 0:
        raise ValueError("Le nombre de portions doit être supérieur à 0.")

    # Calcul du volume cible
    target_volume = target_servings * 150

    # Recherche des moules compatibles (+/- 5%)
    lower_bound = target_volume * 0.95
    upper_bound = target_volume * 1.05

    suggested_pans_qs = Pan.objects.filter(
        volume_cm3_cache__gte=lower_bound,
        volume_cm3_cache__lte=upper_bound
    ).order_by('volume_cm3_cache')

    # Si aucun moule parfaitement compatible → proposer le plus proche
    if not suggested_pans_qs.exists():
        closest_pan = Pan.objects.order_by(Abs(django_models.F("volume_cm3_cache") - target_volume)).first()
        suggested_pans_qs = [closest_pan] if closest_pan else []

    # Construction de la réponse
    pans_data = []
    for pan in suggested_pans_qs:
        servings = get_servings_interval(pan.volume_cm3_cache)
        pans_data.append({
            "id": pan.id,
            "pan_name": pan.pan_name,
            "volume_cm3_cache": pan.volume_cm3_cache,
            "estimated_servings_min": servings["min"],
            "estimated_servings_standard": servings["standard"],
            "estimated_servings_max": servings["max"],
            "match_type": "close"  # Peut être "close" ou "closest"
        })

    # Si aucun moule parfaitement compatible → proposer le plus proche
    if not pans_data:
        closest_pan = Pan.objects.annotate(
            abs_diff=Abs(django_models.F("volume_cm3_cache") - target_volume)
        ).order_by('abs_diff').first()
        if closest_pan:
            servings = get_servings_interval(closest_pan.volume_cm3_cache)
            pans_data.append({
                "id": closest_pan.id,
                "pan_name": closest_pan.pan_name,
                "volume_cm3_cache": closest_pan.volume_cm3_cache,
                "estimated_servings_min": servings["min"],
                "estimated_servings_standard": servings["standard"],
                "estimated_servings_max": servings["max"],
                "match_type": "closest"
            })

    return pans_data

def estimate_servings_from_pan(pan) -> dict:
    """
    Estime le nombre de portions à partir d’un modèle pan existant.
    Utilise le volume stocké dans pan.volume_cm3_cache et la logique métier pour en déduire l’intervalle de portions.
    """
    if not pan or not hasattr(pan, 'volume_cm3_cache') or pan.volume_cm3_cache is None:
        raise ValueError("Le moule (pan) fourni est invalide ou n’a pas de volume renseigné.")

    volume = pan.volume_cm3_cache
    servings = get_servings_interval(volume)

    return {
        "pan_id": pan.id,
        "pan_name": pan.pan_name,
        "volume_cm3": round(volume, 2),
        "estimated_servings_min": servings["min"],
        "estimated_servings_standard": servings["standard"],
        "estimated_servings_max": servings["max"],
    }

# ============================================================
# 5. CAS PARTICULIERS (ADAPTATION PAR CONTRAINTE)
# ============================================================

def adapt_recipe_by_ingredients_constraints(recipe, ingredient_constraints: dict) -> dict:
    """
    Adapte une recette en fonction des quantités disponibles pour un ou plusieurs ingrédients. 
    (Scaling limitant, à part du scaling classique).

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