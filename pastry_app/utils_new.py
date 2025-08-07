import math
from django.core.exceptions import ValidationError
from django.db import models as django_models
from django.db.models.functions import Abs
from .models import Pan, Recipe

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

# def get_scaling_multiplier(recipe, target_servings: int = None, target_pan = None, reference_recipe=None) -> tuple[float, str]:
#     """
#     Calcule le multiplicateur à appliquer à la recette selon le contexte cible :
#     - Priorité au pan d'origine s'il existe, sinon base servings_min/max
#     - Sinon, scaling par recette de référence si fournie
#     Retourne (multiplier, mode).
#     """
#     try:
#         source_volume, source_mode = get_source_volume(recipe)
#         if target_pan:
#             target_volume = getattr(target_pan, "volume_cm3_cache", None)
#             if not target_volume:
#                 raise ValueError("Le pan cible n'a pas de volume défini.")
#         elif target_servings:
#             target_volume = servings_to_volume(target_servings)
#         else:
#             raise Exception
#         return float(target_volume) / float(source_volume), source_mode
#     except Exception:
#         pass  # On tente ensuite la référence
    
#     # 2. Si adaptation par référence possible
#     if reference_recipe:
#         if not getattr(recipe, "total_recipe_quantity", None):
#             raise ValueError("La recette à adapter n’a pas de quantité totale définie.")
#         if not getattr(reference_recipe, "total_recipe_quantity", None):
#             raise ValueError("La recette de référence n’a pas de quantité totale définie.")
#         multiplier = reference_recipe.total_recipe_quantity / recipe.total_recipe_quantity
#         return float(multiplier), "reference_recipe"

#     # 3. Sinon, tout a échoué
#     raise ValueError("Impossible de calculer un scaling : ni pan, ni portions, ni recette de référence valide.")

def get_scaling_multiplier(recipe, target_servings: int = None, target_pan=None, reference_recipe=None) -> tuple[float, str]:
    """
    Calcule le multiplicateur à appliquer à la recette selon le contexte cible.
    - Si adaptation directe (pan/servings dispo sur la recette), l'utilise.
    - Sinon, utilise la recette de référence :
        - PAN : privilégie pan référence, sinon servings référence (convertis en volume)
        - SERVINGS : privilégie servings référence, sinon pan référence (converti en volume)
    """
    def servings_avg(rec):
        if rec.servings_min and rec.servings_max:
            return (rec.servings_min + rec.servings_max) / 2
        if rec.servings_min:
            return rec.servings_min
        if rec.servings_max:
            return rec.servings_max
        return None

    try:
        source_volume, source_mode = get_source_volume(recipe)
        if target_pan:
            target_volume = getattr(target_pan, "volume_cm3_cache", None)
            if not target_volume:
                raise ValueError("Le pan cible n'a pas de volume défini.")
        elif target_servings:
            target_volume = servings_to_volume(target_servings)
        else:
            raise Exception
        return float(target_volume) / float(source_volume), source_mode
    except Exception:
        pass  # On tente ensuite la référence

    if reference_recipe:
        if not getattr(reference_recipe, "total_recipe_quantity", None):
            raise ValueError("La recette de référence n’a pas de quantité totale définie.")
        if not getattr(recipe, "total_recipe_quantity", None):
            raise ValueError("La recette à adapter n’a pas de quantité totale définie.")

        # --- Si cible = PAN ---
        if target_pan:
            # 1. On priorise pan sur la référence
            ref_pan = reference_recipe.pan
            ref_pan_volume = getattr(ref_pan, "volume_cm3_cache", None) if ref_pan else None
            if ref_pan_volume:
                ref_volume = ref_pan_volume * (reference_recipe.pan_quantity or 1)
                ref_density = reference_recipe.total_recipe_quantity / ref_volume  # g/cm3
            else:
                # 2. Sinon, fallback sur servings de la référence
                ref_servings = servings_avg(reference_recipe)
                if not ref_servings:
                    raise ValueError("La recette de référence n’a ni pan ni servings pour adapter vers un pan.")
                ref_volume = servings_to_volume(ref_servings)
                ref_density = reference_recipe.total_recipe_quantity / ref_volume
            # Calcul du scaling
            target_volume = getattr(target_pan, "volume_cm3_cache", None)
            if not target_volume:
                raise ValueError("Le pan cible n'a pas de volume défini.")
            target_total_quantity = target_volume * ref_density
            multiplier = target_total_quantity / recipe.total_recipe_quantity
            return float(multiplier), "reference_recipe_pan"

        # --- Si cible = SERVINGS ---
        elif target_servings:
            # 1. On priorise servings sur la référence
            ref_servings = servings_avg(reference_recipe)
            if ref_servings:
                ref_volume = servings_to_volume(ref_servings)
                ref_density = reference_recipe.total_recipe_quantity / ref_volume
            else:
                # 2. Sinon, fallback sur pan de la référence
                ref_pan = reference_recipe.pan
                ref_pan_volume = getattr(ref_pan, "volume_cm3_cache", None) if ref_pan else None
                if not ref_pan_volume:
                    raise ValueError("La recette de référence n’a ni servings ni pan pour adapter vers un nombre de portions.")
                ref_volume = ref_pan_volume * (reference_recipe.pan_quantity or 1)
                ref_density = reference_recipe.total_recipe_quantity / ref_volume
            target_volume = servings_to_volume(target_servings)
            target_total_quantity = target_volume * ref_density
            multiplier = target_total_quantity / recipe.total_recipe_quantity
            return float(multiplier), "reference_recipe_servings"

        else:
            raise ValueError("Il faut préciser un pan ou un nombre de portions cible pour l’adaptation.")

    raise ValueError("Impossible de calculer un scaling : ni pan, ni portions, ni recette de référence valide.")

# ============================================================
# 3. SCALING / ADAPTATION DE RECETTE (MÉTIER)
# ============================================================

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

def suggest_recipe_reference(recipe, target_servings=None, target_pan=None, candidates=None):
    """
    Suggère les recettes de référence les plus pertinentes pour adapter une recette donnée.
    - Priorise : 
        - Recettes de référence avec pan si target_pan, ou avec servings si target_servings
        - Puis l'autre groupe en fallback
    - Applique ensuite le scoring sur matching catégorie (plus de sous-catégories et parents en commun)
    - Retourne une liste triée du plus pertinent au moins pertinent
    """
    # 1. Sélectionner les candidats (sauf la recette en cours)
    if candidates is None:
        candidates = Recipe.objects.exclude(pk=recipe.pk)

    # 2. Filtrer pour ne garder que les recettes "scalables" (pan OU servings_min/max)
    candidates = candidates.filter(
        django_models.Q(pan__isnull=False, pan__volume_cm3_cache__isnull=False) | 
        django_models.Q(servings_min__isnull=False) | 
        django_models.Q(servings_max__isnull=False)
        ).distinct()

    # 3. Préparer les catégories de la recette cible
    recipe_cats = set(recipe.categories.all())
    recipe_subcats = set(cat for cat in recipe_cats if cat.parent_category is not None)  # Sous-catégories = catégories ayant un parent
    recipe_parentcats = set(cat.parent_category for cat in recipe_cats if cat.parent_category is not None)  # Parents = parent_category de toutes les catégories de la recette cible (sans None)

    # 4. Fonction scoring pour chaque candidat
    def score(candidate):
        cand_cats = set(candidate.categories.all())
        cand_subcats = set(cat for cat in cand_cats if cat.parent_category is not None)
        cand_parentcats = set(cat.parent_category for cat in cand_cats if cat.parent_category is not None)

        # Score fort : nombre de sous-catégories en commun
        subcat_overlap = len(recipe_subcats & cand_subcats)
        # Score moyen : nombre de parent-catégories en commun
        parentcat_overlap = len(recipe_parentcats & cand_parentcats)
        # On pondère fort les sous-catégories, moins les parents
        cat_score = subcat_overlap * 100 + parentcat_overlap * 10

        # Ajoute une "priorité cible" : 1 si le candidat a pan (si target_pan), 1 si servings (si target_servings)
        has_pan = candidate.pan and getattr(candidate.pan, "volume_cm3_cache", None)
        has_servings = candidate.servings_min or candidate.servings_max

        # priorité cible = 1 si le candidat matche le mode, sinon 0
        if target_pan:
            mode_priority = 1 if has_pan else 0
        elif target_servings:
            mode_priority = 1 if has_servings else 0
        else:
            mode_priority = 0  # fallback

        # Tri principal sur la priorité cible, puis sur le score de catégories
        return (mode_priority, cat_score)

    # 5. Transformer en liste et trier par (mode_priority, cat_score) décroissants
    candidates_list = list(candidates)
    candidates_list.sort(key=score, reverse=True)

    return candidates_list  # Peut être vide si aucun candidat scalable n'existe

# ============================================================
# 5. CAS PARTICULIERS (ADAPTATION PAR CONTRAINTE)
# ============================================================

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
