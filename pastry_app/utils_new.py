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

# def scale_recipe_recursively(recipe, target_servings: int = None, target_pan = None, 
#                              custom_multiplier=None, scaling_origin=None, _global_scaling_origin=None) -> dict:
#     """
#     Fonction métier principale : adapte toute une recette (ingrédients ET sous-recettes, récursivement)
#     selon un nombre de portions cible, un moule cible, ou un multiplicateur direct (custom_multiplier).
#     - Utilise la quantité totale produite si renseignée (total_recipe_quantity, en g)
#     - Sinon, fallback sur le volume du pan d'origine
#     - Si scaling par ingrédient limitant (custom_multiplier passé), on ne cherche ni pan ni total_quantity

#     - À la racine, on adapte via target_servings ou target_pan (calcul du scaling via get_scaling_multiplier).
#     - À chaque niveau de sous-recette, on applique le multiplicateur calculé (custom_multiplier),
#       sans recalculer de scaling global (plus de rappel à get_scaling_multiplier en récursion).

#     NE MODIFIE RIEN EN BASE.
#     Retourne une structure complète : ingrédients adaptés, sous-recettes adaptées, scaling utilisé, etc.
#     """
#     # 0. Initialise le mode de scaling global si absent (à la racine)
#     if _global_scaling_origin is None:
#         _global_scaling_origin = scaling_origin

#     # 1. Calcule le multiplicateur de scaling pour la recette courante
#     if custom_multiplier is not None:
#         # Si on est dans la récursivité, on utilise directement le multiplicateur transmis
#         scaling_multiplier = custom_multiplier
#         scaling_mode = _global_scaling_origin or "custom"
#     else:
#         # Au premier niveau, on calcule le scaling à partir de la cible choisie
#         scaling_multiplier, scaling_mode = get_scaling_multiplier(recipe, target_servings=target_servings, target_pan=target_pan)
#         _global_scaling_origin = scaling_mode

#     # 2. Scaling des ingrédients directs
#     adapted_ingredients = _scale_ingredients_flat(recipe, scaling_multiplier)

#     # 3. Scaling récursif des sous-recettes (si présentes)
#     adapted_subrecipes = []
#     for main_sub in recipe.main_recipes.all():
#         sub_recipe = main_sub.sub_recipe
#         local_ratio = None

#         # ---------------------------
#         # Calcul du multiplicateur à appliquer à la sous-recette 
#         #  - Si la sous-recette connaît sa quantité totale produite (en g), on utilise le ratio
#         #  - Sinon, fallback sur pan d'origine (volume)
#         # ---------------------------
#         if hasattr(sub_recipe, 'total_recipe_quantity') and sub_recipe.total_recipe_quantity:
#             # Cas standard : la sous-recette connaît la quantité totale qu'elle produit (en g)
#             if main_sub.unit != "g":
#                 raise ValueError("L'unité de la sous-recette doit être en grammes pour le scaling automatique.")
#             # Ex : besoin 400g / recette crème produit 1200g  → coeff = 0.333
#             local_ratio = main_sub.quantity / sub_recipe.total_recipe_quantity

#         elif sub_recipe.pan:
#             # Cas fallback : la sous-recette n'a pas de quantité totale, on utilise le volume du pan d'origine
#             # (Ex: une pâte pour un moule de 24cm, etc.)
#             sub_volume = get_pan_volume(sub_recipe.pan)
#             if main_sub.unit not in ["ml", "cm3", "g"]:
#                 raise ValueError("L'unité attendue doit être un volume (ml, cm3) ou gramme si équivalence 1g = 1ml.")
#             # On suppose densité ~1 si g/ml, sinon conversion volume si possible
#             desired_volume = main_sub.quantity
#             local_ratio = desired_volume / sub_volume
        
#         # Cas scaling imposé par un ingrédient limitant (pas besoin d'info de prod ou de pan)
#         elif scaling_mode == "ingredient_constraint" or (custom_multiplier is not None and scaling_origin == "ingredient_constraint"):
#             # On laisse local_ratio à None (ou 1), tout le scaling se fait par le multiplicateur global
#             local_ratio = None

#         elif getattr(sub_recipe, 'servings_min', None) and getattr(sub_recipe, 'servings_max', None):
#             avg_servings = (sub_recipe.servings_min + sub_recipe.servings_max) / 2
#             # Ici, main_sub.quantity doit représenter le nombre de portions souhaité pour cette sous-recette à ce niveau
#             local_ratio = main_sub.quantity / avg_servings

#         else:
#             print("\n[DEBUG - scale_recipe_recursively] Problème adaptation sous-recette")
#             print(f"  sub_recipe id: {sub_recipe.id}, name: {getattr(sub_recipe, 'recipe_name', '')}")
#             print(f"  total_recipe_quantity: {getattr(sub_recipe, 'total_recipe_quantity', None)}")
#             print(f"  pan: {getattr(sub_recipe, 'pan', None)}")
#             print(f"  servings_min: {getattr(sub_recipe, 'servings_min', None)}")
#             print(f"  servings_max: {getattr(sub_recipe, 'servings_max', None)}")
#             print(f"  custom_multiplier: {custom_multiplier}")
#             print(f"  scaling_mode: {scaling_mode}, scaling_origin: {scaling_origin}")
#             print(f"  _global_scaling_origin: {_global_scaling_origin if '_global_scaling_origin' in locals() else None}\n")
#             raise ValueError("Impossible d'adapter la sous-recette : ni quantité totale ni pan d'origine, ni scaling global (ingrédient limitant).")

#         # 4. Appel récursif sur la sous-recette en passant le multiplicateur calculé
#         adapted = scale_recipe_recursively(sub_recipe, custom_multiplier=scaling_multiplier, 
#                                            scaling_origin=scaling_mode, _global_scaling_origin=_global_scaling_origin)

#         adapted_subrecipes.append({
#             "sub_recipe_id": sub_recipe.id,
#             "sub_recipe_name": getattr(sub_recipe, "name", ""),
#             "quantity": main_sub.quantity * scaling_multiplier,  # quantité de sous-recette utilisée (déjà à l’échelle du parent)
#             "unit": main_sub.unit,
#             "ingredients": adapted["ingredients"],   # ingrédients déjà scaled globalement
#             "subrecipes": adapted["subrecipes"],
#             "scaling_multiplier": scaling_multiplier,  # le scaling global appliqué à ce niveau
#             "local_ratio": local_ratio,  # Ajouté pour debugger/comprendre la logique
#         })

#     return {
#         "recipe_id": recipe.id,
#         "recipe_name": getattr(recipe, "name", ""),
#         "scaling_multiplier": scaling_multiplier,
#         "scaling_mode": scaling_mode,
#         "ingredients": adapted_ingredients,
#         "subrecipes": adapted_subrecipes,
#     }

# def _scale_ingredients_flat(recipe, multiplier: float) -> list:
#     """
#     Helper interne : adapte seulement les ingrédients directs de la recette (sans les sous-recettes) selon le multiplicateur donné.
#     Retourne une liste de dicts {'ingredient', 'quantity', 'unit', ...} utilisables pour la synthèse ou l’API.
#     NE MODIFIE RIEN en base !
#     """
#     adapted = []
#     for ri in recipe.recipe_ingredients.all():
#         adapted.append({
#             "ingredient_id": ri.ingredient.id,
#             "ingredient_name": ri.ingredient.ingredient_name,
#             "display_name": getattr(ri, "display_name", ""),
#             "quantity": round(ri.quantity * multiplier, 2) if ri.quantity is not None else None,
#             "unit": ri.unit,
#         })
#     return adapted

def scale_recipe_globally(recipe, multiplier):
    """
    Adapte récursivement une recette entière (ingrédients ET sous-recettes)
    en appliquant un coefficient multiplicateur global.
    
    Ce mode correspond à une adaptation pour :
        - un nouveau nombre de portions (servings)
        - un nouveau moule (pan)
        - une contrainte sur un ingrédient limitant
        - ou tout autre cas où l'on souhaite scaler la recette à l'identique partout

    Comportement :
        - Multiplie toutes les quantités d'ingrédients et de sous-recettes, à tous les niveaux,
          par le multiplicateur global calculé à la racine.
        - Ignore totalement les éventuelles informations de "quantité totale produite",
          "pan d'origine" ou "servings" des sous-recettes : 
          TOUT est scaled uniformément, conformément à la logique "scaling global".

    NE MODIFIE RIEN EN BASE.
    Retourne une structure imbriquée complète avec les quantités adaptées.

    :param recipe: instance de Recipe
    :param multiplier: float (coefficient de scaling à appliquer partout)
    :return: dict structuré (identique à l'API classique)
    """

    # 1. Adaptation des ingrédients directs de la recette principale
    adapted_ingredients = []
    for recipe_ingredient in recipe.recipe_ingredients.all():
        adapted_ingredients.append({
            "ingredient_id": recipe_ingredient.ingredient.id,
            "ingredient_name": recipe_ingredient.ingredient.ingredient_name,
            "display_name": getattr(recipe_ingredient, "display_name", ""),
            "original_quantity": recipe_ingredient.quantity,
            "quantity": round(recipe_ingredient.quantity * multiplier, 2),
            "unit": recipe_ingredient.unit,
        })

    # 2. Adaptation récursive des sous-recettes (si présentes)
    adapted_subrecipes = []
    for main_sub in recipe.main_recipes.all():
        sub_recipe = main_sub.sub_recipe

        # La quantité de sous-recette utilisée est scaled globalement
        scaled_quantity = main_sub.quantity * multiplier

        # Récursivité : adapte toute la sous-recette avec le même multiplicateur global
        adapted_sub = scale_recipe_globally(sub_recipe, multiplier)

        adapted_subrecipes.append({
            "sub_recipe_id": sub_recipe.id,
            "sub_recipe_name": getattr(sub_recipe, "recipe_name", ""),
            "original_quantity": main_sub.quantity,
            "quantity": round(scaled_quantity, 2),
            "unit": main_sub.unit,
            "ingredients": adapted_sub["ingredients"],      # déjà scaled
            "subrecipes": adapted_sub["subrecipes"],        # récursivité profonde
            "scaling_multiplier": multiplier,
        })

    # 3. Structure de retour
    return {
        "recipe_id": recipe.id,
        "recipe_name": getattr(recipe, "recipe_name", ""),
        "scaling_multiplier": multiplier,
        "ingredients": adapted_ingredients,
        "subrecipes": adapted_subrecipes,
    }

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
# def get_limiting_multiplier(recipe, ingredient_constraints, parent_multiplier=1.0):
#     """
#     Parcours récursivement tous les ingrédients (y compris dans les sous-recettes)
#     et retourne (multiplier, ingredient_id) du facteur le plus limitant
#     """
#     multipliers = []

#     # 1. Ingrédients directs
#     for recipe_ingredient in recipe.recipe_ingredients.all():
#         ing_id = recipe_ingredient.ingredient.id
#         if ing_id in ingredient_constraints:
#             available = ingredient_constraints[ing_id]
#             if available <= 0:
#                 raise ValidationError(f"La quantité fournie pour l’ingrédient '{recipe_ingredient.ingredient}' doit être positive.")
#             # On tient compte du parent_multiplier si besoin (ex: si une sous-recette n'est utilisée qu'à 80%)
#             multiplier = available / (recipe_ingredient.quantity * parent_multiplier)
#             multipliers.append((multiplier, ing_id))

#     # 2. Sous-recettes (récursif)
#     for main_sub in recipe.main_recipes.all():
#         # Le facteur local = la proportion de sous-recette utilisée ici (main_sub.quantity / total_recipe_quantity)
#         # Ou 1.0 si pas d'info
#         local_multiplier = 1.0
#         # Optionnel : tenir compte du ratio local si tu veux
#         sub_recipe = main_sub.sub_recipe
#         sub_multipliers = get_limiting_multiplier(sub_recipe, ingredient_constraints, parent_multiplier * local_multiplier)
#         multipliers.extend(sub_multipliers)

#     return multipliers

# def adapt_recipe_by_ingredients_constraints_recursive(recipe, ingredient_constraints: dict) -> dict:
#     """
#     Adapte toute la recette (y compris sous-recettes) selon la quantité dispo pour un ou plusieurs ingrédients.
#     """
#     multipliers = get_limiting_multiplier(recipe, ingredient_constraints)
#     if not multipliers:
#         raise ValidationError("Aucune correspondance entre les ingrédients de la recette et les contraintes fournies.")
#     # Prend le plus limitant
#     final_multiplier, limiting_ingredient_id = min(multipliers, key=lambda x: x[0])

#     # Appel du scaling global (récursif sur toute la hiérarchie)
#     result = scale_recipe_recursively(recipe, custom_multiplier=final_multiplier, scaling_origin="ingredient_constraint")
#     result["limiting_ingredient_id"] = limiting_ingredient_id
#     result["multiplier"] = final_multiplier
#     return result

def get_limiting_multiplier(recipe, ingredient_constraints):
    """
    Parcourt récursivement tous les ingrédients (dans la recette et les sous-recettes)
    et retourne le multiplicateur le plus limitant (et l'ingrédient concerné) : tuple (multiplier, ing_id).
    """
    multipliers = []

    # Ingrédients directs
    for recipe_ingredient in recipe.recipe_ingredients.all():
        ing_id = recipe_ingredient.ingredient.id
        if ing_id in ingredient_constraints:
            available = ingredient_constraints[ing_id]
            if available <= 0:
                raise ValidationError(f"La quantité fournie pour l’ingrédient '{recipe_ingredient.ingredient}' doit être positive.")
            multiplier = available / recipe_ingredient.quantity
            multipliers.append((multiplier, ing_id))

    # Sous-recettes (récursif)
    for main_sub in recipe.main_recipes.all():
        sub_recipe = main_sub.sub_recipe
        sub_multipliers = get_limiting_multiplier(sub_recipe, ingredient_constraints)
        if sub_multipliers:  # sub_mult est soit None, soit un tuple
            multipliers.append(sub_multipliers)

    if not multipliers:
        raise ValidationError("Aucune correspondance entre les ingrédients de la recette et les contraintes fournies.")

    # Facteur limitant = le plus petit multiplicateur
    return min(multipliers, key=lambda x: x[0])  # (multiplier, ing_id)
