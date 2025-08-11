import math
from django.core.exceptions import ValidationError
from django.db import models as django_models
from django.db.models.functions import Abs
from .models import Pan, Recipe, IngredientUnitReference

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
# 0. Gestion de la conversion des units
# ============================================================

def _get_coeff_to_grams(ingredient_id, unit, user=None, guest_id=None, cache=None):
    """
    Renvoie le poids (en grammes) correspondant à 1 <unit> pour cet ingrédient.
    Cherche d'abord la ref user/guest active, sinon fallback global active.
    """
    # 1) Pivot et échelles simples → pas de lookup
    if unit == "g":
        return 1.0
    if unit == "kg":
        return 1000.0
    if unit == "mg":
        return 0.001

    # 2) Sinon: on va chercher la ref (user/guest actif → global actif)
    if cache is None:
        cache = {}
    key = (ingredient_id, unit, user.id if user else None, guest_id)
    if key in cache:
        return cache[key]

    qs = IngredientUnitReference.objects.filter(ingredient_id=ingredient_id, unit=unit, is_hidden=False)
    ref = qs.filter(user=user, guest_id=guest_id).first() \
        or qs.filter(user__isnull=True, guest_id__isnull=True).first()

    if ref is None:
        raise ValidationError(f"Aucune référence de conversion pour l’ingrédient {ingredient_id} en unité '{unit}'.")

    cache[key] = float(ref.weight_in_grams)
    return cache[key]

def convert_amount_for_ingredient(ingredient_id, amount, from_unit, to_unit, *, user=None, guest_id=None, cache=None):
    """
    Convertit une quantité d’un ingrédient de from_unit → to_unit en passant par le pivot (grammes).
    Suppose que weight_in_grams = grammes pour 1 <unit> dans IngredientUnitReference.
    """
    if cache is None:
        cache = {}

    try:
        amount = float(amount)
    except Exception:
        raise ValidationError(f"Quantité invalide: '{amount}' (ingrédient {ingredient_id}).")

    if amount < 0:
        raise ValidationError("La quantité fournie doit être positive ou nulle.")

    if from_unit == to_unit:
        return amount

    # from_unit -> g (no lookup if from_unit == "g")
    grams_per_from = 1.0 if from_unit == "g" else _get_coeff_to_grams(ingredient_id, from_unit, user=user, guest_id=guest_id, cache=cache)
    amount_in_grams = amount * grams_per_from

    # g -> to_unit (no lookup if to_unit == "g")
    if to_unit == "g":
        return amount_in_grams

    grams_per_to = _get_coeff_to_grams(ingredient_id, to_unit, user=user, guest_id=guest_id, cache=cache)
    return amount_in_grams / grams_per_to

def normalize_constraints_for_recipe(recipe, constraints, *, user=None, guest_id=None):
    """
    constraints: dict[int, float | tuple[str, float]]
      - float/int = quantité déjà dans l’unité de la recette pour cet ingrédient
      - tuple = (unit, amount) à convertir vers l’unité de la recette

    Retourne: dict[int, float] dans l’unité du RecipeIngredient correspondant.
    Ignore les ingrédients absents de la recette.
    """
    normalized = {}
    # Map des unités cibles (celles de la recette) par ingrédient
    target_units = {ri.ingredient_id: ri.unit for ri in recipe.recipe_ingredients.all()}

    cache = {}
    for ing_id, provided in constraints.items():
        if ing_id not in target_units:
            continue  # on ignore les extras

        target_unit = target_units[ing_id]

        # Cas simple: déjà normalisé (on fait confiance à l’appelant)
        if isinstance(provided, (int, float)):
            normalized[ing_id] = float(provided)
            continue

        # Tuple (unit, amount)
        try:
            from_unit, amount = provided
        except Exception:
            raise ValidationError(
                f"Format de contrainte invalide pour l’ingrédient {ing_id}. "
                f"Attendu: nombre ou tuple (unit, amount)."
            )

        normalized[ing_id] = convert_amount_for_ingredient(ingredient_id=ing_id, amount=amount, from_unit=from_unit, to_unit=target_unit, 
                                                           user=user, guest_id=guest_id, cache=cache)

    return normalized

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
    elif pan_type == "CUSTOM":
        volume_raw = getattr(pan, 'volume_raw', None)
        if volume_raw:
            return float(volume_raw)

    raise ValueError("Impossible de déterminer le volume du moule (pan) fourni.")

def get_source_volume(recipe):
    """
    Retourne un tuple (volume_source, mode) :
        - mode = 'pan' si la base est le pan d'origine,
        - mode = 'servings' sinon.

    Si la recette possède un pan : utilise le volume du pan, et on multiplie par pan_quantity (>=1).
    Sinon : utilise la moyenne servings_min/servings_max (via serving_to_volume)
    """
    # 1) Base pan
    pan = getattr(recipe, "pan", None)
    pan_vol = getattr(pan, "volume_cm3_cache", None) if pan else None
    if pan and pan_vol:
        qty = getattr(recipe, "pan_quantity", 1) or 1
        if qty < 1:
            qty = 1
        return pan_vol * qty, "pan"
    
    # 2) Base servings
    # Si pas de pan, on tente la moyenne des servings
    servings_min = getattr(recipe, "servings_min", None)
    servings_max = getattr(recipe, "servings_max", None)
    if servings_min and servings_max:
        return servings_to_volume((servings_min + servings_max) / 2), "servings"
    if servings_min:
        return servings_to_volume(servings_min), "servings"
    if servings_max:
        return servings_to_volume(servings_max), "servings"
    
    # 3) Rien d’exploitable
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

def get_scaling_multiplier_old(recipe, target_servings: int = None, target_pan=None, reference_recipe=None) -> tuple[float, str]:
    """
    Calcule le multiplicateur à appliquer à la recette selon le contexte cible.
    Priorités de calcul (deux modes de fonctionnement) :
    - MODE par défaut (prefer_reference=False) :
        1) Adaptation directe si possible (pan/servings connus sur la recette)
        2) Sinon, adaptation via la recette de référence (si fournie)

    Paramètres:
        recipe               : recette à adapter
        target_servings (int): portions cibles (optionnel)
        target_pan           : moule cible (optionnel)

    Retour:
        (multiplier: float, mode: str)
        mode ∈ {"pan", "servings", "reference_recipe_pan", "reference_recipe_servings"}
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

def _try_direct(recipe, target_servings=None, target_pan=None):
    """
    Tente un calcul 'direct' à partir de la recette source :
    - si target_pan : utilise le volume du pan cible
    - sinon si target_servings : utilise le volume équivalent servings cible
    Nécessite que la recette source ait une info scalable (pan.volume_cm3_cache OU servings_min/max).
    Retourne (multiplier, mode) OU (None, "raison de l'échec").
    """
    try:
        source_volume, source_mode = get_source_volume(recipe)
        if not source_volume:
            return None, "La recette source n'a ni pan ni servings pour servir de base."

        if target_pan:
            target_volume = getattr(target_pan, "volume_cm3_cache", None)
            if not target_volume:
                return None, "Le pan cible n'a pas de volume défini."
        elif target_servings:
            target_volume = servings_to_volume(target_servings)
        else:
            return None, "Aucun critère direct (target_pan/target_servings) fourni."

        multiplier = float(target_volume) / float(source_volume)
        return (multiplier, source_mode), None

    except Exception as exc:
        return None, str(exc)

def _try_reference(recipe, reference_recipe, target_servings=None, target_pan=None):
    """
    Tente un calcul via une recette de référence.
    - Si target_pan : priorité au pan de la référence ; fallback aux servings de la référence.
    - Si target_servings : priorité aux servings de la référence ; fallback au pan de la référence.
    Retourne (multiplier, mode) OU (None, "raison de l'échec").
    Hypothèses métier : les deux recettes (source & référence) ont total_recipe_quantity.
    """
    try:
        if not reference_recipe:
            return None, "Aucune recette de référence fournie."
        if not getattr(recipe, "total_recipe_quantity", None):
            return None, "La recette à adapter n’a pas de quantité totale définie."
        if not getattr(reference_recipe, "total_recipe_quantity", None):
            return None, "La recette de référence n’a pas de quantité totale définie."

        def _servings_avg(r):
            if r.servings_min and r.servings_max:
                return (r.servings_min + r.servings_max) / 2
            if r.servings_min:
                return r.servings_min
            if r.servings_max:
                return r.servings_max
            return None

        # Cible = PAN
        if target_pan:
            ref_pan = reference_recipe.pan
            ref_pan_volume = getattr(ref_pan, "volume_cm3_cache", None) if ref_pan else None

            if ref_pan_volume:
                ref_volume = ref_pan_volume * (reference_recipe.pan_quantity or 1)
                ref_density = reference_recipe.total_recipe_quantity / ref_volume  # g/cm3
            else:
                ref_serv = _servings_avg(reference_recipe)
                if not ref_serv:
                    return None, "La référence n’a ni pan ni servings exploitables pour une cible pan."
                ref_volume = servings_to_volume(ref_serv)
                ref_density = reference_recipe.total_recipe_quantity / ref_volume

            target_volume = getattr(target_pan, "volume_cm3_cache", None)
            if not target_volume:
                return None, "Le pan cible n'a pas de volume défini."

            target_total_quantity = target_volume * ref_density
            multiplier = target_total_quantity / recipe.total_recipe_quantity
            return (float(multiplier), "reference_recipe_pan"), None

        # Cible = SERVINGS
        if target_servings:
            ref_serv = _servings_avg(reference_recipe)
            if ref_serv:
                ref_volume = servings_to_volume(ref_serv)
                ref_density = reference_recipe.total_recipe_quantity / ref_volume
            else:
                ref_pan = reference_recipe.pan
                ref_pan_volume = getattr(ref_pan, "volume_cm3_cache", None) if ref_pan else None
                if not ref_pan_volume:
                    return None, "La référence n’a ni servings ni pan exploitables pour une cible servings."
                ref_volume = ref_pan_volume * (reference_recipe.pan_quantity or 1)
                ref_density = reference_recipe.total_recipe_quantity / ref_volume

            target_volume = servings_to_volume(target_servings)
            target_total_quantity = target_volume * ref_density
            multiplier = target_total_quantity / recipe.total_recipe_quantity
            return (float(multiplier), "reference_recipe_servings"), None

        return None, "Aucun critère cible (pan/servings) fourni pour un mode référence."

    except Exception as exc:
        return None, str(exc)

def get_scaling_multiplier(recipe, target_servings: int = None, target_pan=None, reference_recipe=None, *, prefer_reference: bool = False
                           ) -> tuple[float, str]:
    """
    Calcule le multiplicateur global à appliquer à une recette et le 'mode' utilisé.

    Stratégies essayées dans cet ordre :
      - Si prefer_reference=True et reference_recipe fournie :
            1) via référence  →  2) direct
      - Sinon :
            1) direct         →  2) via référence

    Chaque stratégie retourne (multiplier, mode) ou None si elle n’est pas applicable.
    Si toutes échouent, on lève ValueError avec un message consolidé utile au client.

    :param recipe: recette à adapter
    :param target_servings: portions cibles (optionnel)
    :param target_pan: pan cible (optionnel)
    :param reference_recipe: recette servant de référence (optionnel)
    :param prefer_reference: si True, on tente la référence en premier
    :return: (multiplier: float, mode: str)
    """
    attempts = []
    reasons = []

    if prefer_reference and reference_recipe:
        attempts = [
            lambda: _try_reference(recipe, reference_recipe, target_servings, target_pan),
            lambda: _try_direct(recipe, target_servings, target_pan),
        ]
    else:
        attempts = [
            lambda: _try_direct(recipe, target_servings, target_pan),
            lambda: _try_reference(recipe, reference_recipe, target_servings, target_pan),
        ]

    for attempt in attempts:
        result, reason = attempt()
        if result is not None:
            return result  # (multiplier, mode)
        reasons.append(reason)

    # Rien n'a fonctionné → message consolidé (lisible pour l'API)
    consolidated = " / ".join(r for r in reasons if r)
    raise ValueError(consolidated or "Impossible de calculer un multiplicateur d’adaptation.")

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
# 5. CAS PARTICULIERS (ADAPTATION PAR CONTRAINTE)
# ============================================================

def get_limiting_multiplier(recipe, ingredient_constraints):
    """
    Parcourt récursivement tous les ingrédients (dans la recette et les sous-recettes)

    recipe : Recipe
        La recette racine à analyser.
    ingredient_constraints : dict[int, float | int]
        Dictionnaire {ingredient_id: quantité_disponible} exprimée dans **la même unité**
        que celle utilisée par la recette pour cet ingrédient (aucune conversion d’unité
        n’est effectuée ici). Par exemple, si la recette attend 3 « unit » d’œuf, la
        contrainte doit fournir un nombre d’« unit » (ex : 2), pas des grammes.

    et retourne le multiplicateur le plus limitant (et l'ingrédient concerné) sous le format : 
    (multiplier, ing_id) : tuple[float, int]
        - multiplier : le facteur maximal par lequel on peut multiplier la recette
          compte tenu des disponibilités.
        - ing_id : l’identifiant de l’ingrédient réellement limitant.
          En cas d’égalité parfaite entre plusieurs ingrédients, le premier rencontré
          (dans l’ordre d’itération) est renvoyé.
    """
    multipliers = []

    # Ingrédients directs
    for recipe_ingredient in recipe.recipe_ingredients.all():
        ing_id = recipe_ingredient.ingredient.id
        if ing_id in ingredient_constraints:
            available = float(ingredient_constraints[ing_id])
            if available <= 0:
                raise ValidationError(f"La quantité fournie pour l’ingrédient '{recipe_ingredient.ingredient}' doit être positive.")
            multiplier = available / float(recipe_ingredient.quantity)
            multipliers.append((multiplier, ing_id))

    # Sous-recettes (récursif)
    for main_sub in recipe.main_recipes.all():
        sub_multipliers = get_limiting_multiplier(main_sub.sub_recipe, ingredient_constraints)
        if sub_multipliers:  # sub_multipliers est soit None, soit un tuple
            multipliers.append(sub_multipliers)

    if not multipliers:
        raise ValidationError("Aucune correspondance entre les ingrédients de la recette et les contraintes fournies.")

    # Facteur limitant = le plus petit multiplicateur
    return min(multipliers, key=lambda x: x[0])  # (multiplier, ing_id)

# ============================================================
# 6. HELPERS : SÉLECTION DE RECETTE DE RÉFÉRENCE
# ============================================================

# 6.0 — Mini-config interne (règles, poids, seuils)
REF_SELECTION_CONFIG = {
    # RÈGLES "dures" (filtres éliminatoires)
    "require_same_parent_category": True,     # une référence doit partager >= 1 parent_category avec la recette hôte
    "fallback_allow_same_category_if_no_parent": True,  # si la recette n'a pas de parent_category, on exige au moins 1 category identique
    "disallow_standalone_for_preparation_refs": True,   # en mode préparation, la référence doit être une sous-recette d'une autre recette (pas standalone)
    "require_scalable_ref": True,             # la référence doit avoir pan(volume) ou servings_min/max

    # PONDÉRATIONS de score (plus grand = plus important)
    "min_name_token_jaccard_for_prep": 0.0,   # seuil minimum pour la similarité (proximité jaccard) de nom

    # ---- niveau recette
    "w_recipe_name_similarity": 4.0,          # similarité de nom recette↔candidat
    "w_recipe_subcat_overlap": 3.0,           # nb de sous-catégories en commun
    "w_recipe_parentcat_overlap": 1.0,        # nb de parent-catégories en commun
    "w_recipe_prep_structure_jaccard": 2.0,   # similarité structurelle des préparations (Jaccard)
    "w_recipe_mode_priority": 2.5,            # bonus si le candidat possède pan (quand target_pan) ou servings (quand target_servings)
    "w_recipe_chef_match": 1,                 # léger bonus si chef voisin/identique

    # ---- niveau préparation
    "w_prep_name_similarity": 6.0,            # similarité de nom préparation↔sous-recette dans candidat (très fort)
    "w_prep_cat_overlap": 3.0,                # overlap catégories entre préparation et sous-recette candidate
    "w_prep_host_parent_overlap": 2.0,        # overlap parent-catégories entre recettes hôtes (recette à adapter vs hôte candidate)
    "w_prep_mode_priority": 2.5,              # même idée que ci-dessus
    "w_prep_is_subrecipe": 3.0,               # bonus si le match vient bien d'une sous-recette dans le candidat

    # SEUILS
    "auto_select_threshold": 8.0,             # au-delà de ce score (normalisé), on peut auto-sélectionner niveau recette
    "suggest_threshold": 1.0,                  # sous ce score on peut ne pas proposer du tout (optionnel, ici on liste tout de même)
}

# 6.1 — Helpers utilitaires

def _name_tokens(s: str) -> set:
    """Tokenisation naïve (espaces) après normalisation."""
    return set(normalize_case(s).split())

def _jaccard(a: set, b: set) -> float:
    """Jaccard simple entre deux ensembles (0..1)."""
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def _get_recipe_categories(recipe):
    """
    Retourne un tuple (subcats, parent_roots) :
      - subcats = sous-catégories (catégories ayant un parent)
      - parent_roots = racines normalisées (cat si racine, sinon son parent)
    """
    cats = set(recipe.categories.all())
    subcats = {c for c in cats if c.parent_category is not None}
    parent_roots = {c.parent_category or c for c in cats}
    return subcats, parent_roots

def _recipe_has_scalable_info(rec) -> bool:
    """Vrai si la recette a un pan volumé ou des servings min/max."""
    has_pan = bool(getattr(rec, "pan", None) and getattr(rec.pan, "volume_cm3_cache", None))
    has_serv = bool(getattr(rec, "servings_min", None) or getattr(rec, "servings_max", None))
    return has_pan or has_serv

def _mode_tiebreaker(candidate, target_servings=None, target_pan=None) -> int:
    """
    Renvoie 1 si le candidat possède les métadonnées correspondant au critère fourni
    (moule avec volume si `target_pan`, ou portions si `target_servings`), sinon 0.
    Sert à départager des scores égaux.
    """
    has_pan = bool(candidate.pan and getattr(candidate.pan, "volume_cm3_cache", None))
    has_servings = bool(candidate.servings_min or candidate.servings_max)
    if target_pan:
        return 1 if has_pan else 0
    if target_servings:
        return 1 if has_servings else 0
    return 0

def _chef_match_bonus(base_recipe, candidate) -> float:
    """Petit bonus si même chef (ou nom très proche)."""
    w = REF_SELECTION_CONFIG
    base = normalize_case(getattr(base_recipe, "chef_name", "") or "")
    cand = normalize_case(getattr(candidate, "chef_name", "") or "")
    if not base or not cand:
        return 0.0
    return w["w_recipe_chef_match"] if base == cand else 0.0

def _prep_iter_level1(recipe):
    """
    Itère les préparations (sous-recettes) de niveau 1 : objets SubRecipe liés à `recipe`.
    Suppose la relation `recipe.main_recipes` (conforme à ton code existant).
    """
    return list(recipe.main_recipes.select_related("sub_recipe").all())

def _subrecipe_candidates_hosting_like(prep, candidates):   
    """
    Filtre des recettes candidates qui contiennent une sous-recette ressemblant à `prep.sub_recipe`.
    Si `disallow_standalone_for_preparation_refs` est actif, on exige que la correspondance
    provienne bien d'une sous-recette du candidat (pas d'une recette standalone).
    """
    w = REF_SELECTION_CONFIG
    prep_name_tokens = _name_tokens(getattr(prep.sub_recipe, "recipe_name", ""))
    jaccard_min = w.get("min_name_token_jaccard_for_prep", 0.0)  # ← seuil paramétrable
    out = []
    for cand in candidates:
        # Cherche une sous-recette dans cand dont le nom rapproche celui de prep
        matches = []
        for cand_sub in cand.main_recipes.select_related("sub_recipe").all():
            cand_tokens = _name_tokens(getattr(cand_sub.sub_recipe, "recipe_name", ""))
            if _jaccard(prep_name_tokens, cand_tokens) > jaccard_min:  # match minimal souple
                matches.append(cand_sub)
        if matches:
            out.append((cand, matches))  # conserve les matches pour le scoring
        elif not w["disallow_standalone_for_preparation_refs"]:
            # fallback possible : autoriser une référence standalone (non recommandé par défaut)
            out.append((cand, []))
    return out  # liste de tuples (recette_hôte, [sous-recettes correspondantes])

# 6.2 — Éligibilité des candidats

def _eligible_recipe_candidates(base_recipe, target_servings=None, target_pan=None, candidates=None):
    """
    Filtre "hard" pour les références niveau recette :
    - Exclut la recette elle-même
    - Exige info scalable (pan ou servings) si require_scalable_ref=True
    - Exige un minimum de proximité de catégories (parent_category prioritaire)
    """
    if candidates is None:
        candidates = Recipe.objects.exclude(pk=base_recipe.pk)
    else:
        candidates = candidates.exclude(pk=base_recipe.pk)

    w = REF_SELECTION_CONFIG
    # 1) scalable ?
    if w["require_scalable_ref"]:
        # Filtre DB si c'est un QuerySet, sinon fallback Python avec _recipe_has_scalable_info
        if hasattr(candidates, "filter"):
            candidates = candidates.filter(
                django_models.Q(pan__isnull=False, pan__volume_cm3_cache__isnull=False) |
                django_models.Q(servings_min__isnull=False) |
                django_models.Q(servings_max__isnull=False)
            )
        else:
            candidates = [c for c in candidates if _recipe_has_scalable_info(c)]

    # 2) catégories compatibles ?
    base_sub, base_parent = _get_recipe_categories(base_recipe)
    # si on exige parent commun
    if w["require_same_parent_category"]:
        if hasattr(candidates, "filter"):
            candidates = candidates.filter(categories__parent_category__in=list(base_parent)).distinct()
            if not base_parent and w["fallback_allow_same_category_if_no_parent"]:
                candidates = candidates.filter(categories__in=list(base_sub)).distinct()
        else:
            # fallback Python si 'candidates' n'est pas un QuerySet
            def has_any_parent(c):
                c_sub, c_parent = _get_recipe_categories(c)
                if base_parent:
                    return bool(c_parent & base_parent)
                if w["fallback_allow_same_category_if_no_parent"]:
                    return bool(c_sub & base_sub)
                return False
            candidates = [c for c in candidates if has_any_parent(c)]

    return candidates.distinct() if hasattr(candidates, "distinct") else candidates

def _eligible_preparation_candidates(base_recipe, target_servings=None, target_pan=None, candidates=None):
    """
    Éligibilité niveau préparation : on part des mêmes règles "dures" que niveau recette,
    car la recette de référence doit quand même être scalable et dans un contexte
    de catégories compatible avec la recette HÔTE.
    """
    return _eligible_recipe_candidates(base_recipe, target_servings, target_pan, candidates)

# 6.3 — Scoring

def _score_recipe_level(candidate, base_recipe, target_servings=None, target_pan=None) -> float:
    """
    Score pondéré pour une référence au NIVEAU RECETTE.
    Combine :
      - similarité de noms
      - overlap sous-catégories / parent-catégories
      - similarité structurelle des préparations (Jaccard)
      - bonus mode (pan/servings) + chef
    """
    w = REF_SELECTION_CONFIG
    # similarité de noms
    name_sim = _jaccard(_name_tokens(base_recipe.recipe_name), _name_tokens(candidate.recipe_name))

    # catégories
    base_sub, base_parent = _get_recipe_categories(base_recipe)
    cand_sub, cand_parent = _get_recipe_categories(candidate)
    sub_overlap = len(base_sub & cand_sub)
    parent_overlap = len(base_parent & cand_parent)

    # structure des préparations (noms des sous-recettes de niveau 1)
    def prep_name_set(rec):
        return { normalize_case(getattr(sr.sub_recipe, "recipe_name", "")) for sr in _prep_iter_level1(rec) }
    base_preps = prep_name_set(base_recipe)
    cand_preps = prep_name_set(candidate)
    prep_struct_sim = _jaccard(base_preps, cand_preps)

    # mode & chef
    chef_bonus = _chef_match_bonus(base_recipe, candidate)

    score = (
        w["w_recipe_name_similarity"] * name_sim
        + w["w_recipe_subcat_overlap"] * sub_overlap
        + w["w_recipe_parentcat_overlap"] * parent_overlap
        + w["w_recipe_prep_structure_jaccard"] * prep_struct_sim
        + chef_bonus
    )
    return float(score)

def _score_preparation_level(base_recipe, prep, host_candidate, matched_subrecipes, target_servings=None, target_pan=None) -> float:
    """
    Score pour une référence au NIVEAU PRÉPARATION.
    `matched_subrecipes` = liste des sous-recettes du candidat dont le nom matche la préparation `prep`.
    """
    w = REF_SELECTION_CONFIG

    # (1) similarité nom préparation ↔ nom des sous-recettes candidates (max)
    prep_tokens = _name_tokens(getattr(prep.sub_recipe, "recipe_name", ""))
    name_sim = 0.0
    for cand_sub in matched_subrecipes:
        cand_tokens = _name_tokens(getattr(cand_sub.sub_recipe, "recipe_name", ""))
        name_sim = max(name_sim, _jaccard(prep_tokens, cand_tokens))

    # (2) overlap catégories entre PREPARATION et la SOUS-RECETTE candidate (max)
    def cats_of_recipe(r):
        sub, parent = _get_recipe_categories(r)
        return sub, parent
    prep_sub, prep_parent = cats_of_recipe(prep.sub_recipe)

    cat_overlap = 0
    for cand_sub in matched_subrecipes:
        c_sub, c_parent = cats_of_recipe(cand_sub.sub_recipe)
        # pondération simple : 3*sub + 1*parent (comme niveau recette)
        cat_overlap = max(cat_overlap, 3 * len(prep_sub & c_sub) + 1 * len(prep_parent & c_parent))

    # (3) overlap parent-cats entre recettes HÔTES (base vs candidate)
    base_sub, base_parent = _get_recipe_categories(base_recipe)
    cand_sub, cand_parent = _get_recipe_categories(host_candidate)
    host_parent_overlap = len(base_parent & cand_parent)

    # (4) bonus "est bien une sous-recette" — seulement si autorisé ET qu’il y a un match réel
    is_sub_bonus = (
        w["w_prep_is_subrecipe"]
        if (not w["disallow_standalone_for_preparation_refs"] and matched_subrecipes)
        else 0.0
    )

    score = (
        w["w_prep_name_similarity"] * name_sim
        + w["w_prep_cat_overlap"] * cat_overlap
        + w["w_prep_host_parent_overlap"] * host_parent_overlap
        + is_sub_bonus
    )
    return float(score)

# 6.4 — Ranking + wrapper public

def _rank_recipe_level_references(recipe, target_servings=None, target_pan=None, candidates=None):
    """
    Retourne une liste de tuples (candidate, score) triée par score décroissant.
    Applique l'éligibilité + le scoring niveau recette.
    """
    cands = _eligible_recipe_candidates(recipe, target_servings, target_pan, candidates)
    scored = []
    for cand in cands:
        s = _score_recipe_level(cand, recipe, target_servings, target_pan)
        t = _mode_tiebreaker(cand, target_servings, target_pan)
        scored.append((cand, s, t))
    # Tri : score puis tiebreaker (mode)
    scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
    # On retourne comme avant (cand, score)
    return [(c, s) for (c, s, t) in scored]

def _rank_preparation_level_references(recipe, target_servings=None, target_pan=None, candidates=None):
    """
    Pour chaque préparation de niveau 1 de `recipe`, on cherche des recettes hôtes
    qui contiennent une sous-recette "proche" → score → on fusionne et on trie.
    Retourne une liste de dicts utiles pour l'UI.
    Tri principal: score décroissant.
    Égalités: tie-breaker via _mode_tiebreaker(), décroissant également.
    """
    results = []
    elig_hosts = _eligible_preparation_candidates(recipe, target_servings, target_pan, candidates)
    preps = _prep_iter_level1(recipe)

    for prep in preps:
        hosts_with_matches = _subrecipe_candidates_hosting_like(prep, elig_hosts)
        for host, matched_subs in hosts_with_matches:
            score = _score_preparation_level(recipe, prep, host, matched_subs, target_servings, target_pan)
            tie = _mode_tiebreaker(host, target_servings, target_pan)
            results.append({
                "host_recipe": host,
                "score": score,
                "preparation_id": prep.sub_recipe.id,
                "preparation_name": getattr(prep.sub_recipe, "recipe_name", ""),
                "matched_subrecipes_count": len(matched_subs),
                "tie": tie, # on garde "tie" uniquement pour trier; il sera retiré avant return
            })

    # tri par (score, tie) décroissant comme dans la proposition 2
    results.sort(key=lambda d: (d["score"], d["tie"]), reverse=True)

    # ne pas exposer "tie" à l'UI
    for d in results:
        d.pop("tie", None)

    return results

def _should_autoselect(best_score: float) -> bool:
    """Décide si l'on peut auto-sélectionner (niveau recette) sans demander l'avis utilisateur."""
    return best_score >= REF_SELECTION_CONFIG["auto_select_threshold"]

# ============================================================
# 4. SUGGESTIONS ET ESTIMATIONS
# ============================================================

def _get_servings_interval(volume_cm3: float) -> dict:
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
        servings = _get_servings_interval(pan.volume_cm3_cache)
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
            servings = _get_servings_interval(closest_pan.volume_cm3_cache)
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
    servings = _get_servings_interval(volume)

    return {
        "pan_id": pan.id,
        "pan_name": pan.pan_name,
        "volume_cm3": round(volume, 2),
        "estimated_servings_min": servings["min"],
        "estimated_servings_standard": servings["standard"],
        "estimated_servings_max": servings["max"],
    }

def suggest_recipe_reference_old(recipe, target_servings=None, target_pan=None, candidates=None):
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

def suggest_recipe_reference(recipe, target_servings=None, target_pan=None, candidates=None):
    """
    Porte d’entrée publique :
    1) Tente la référence NIVEAU RECETTE (classement + auto-select possible si score fort)
    2) Sinon, classe des références NIVEAU PRÉPARATION
    3) Retourne une structure uniforme exploitable par l’API/Front :
       {
         "auto_selected": Optional[{recipe_id, score}],
         "recipe_level": [{"recipe_id", "score"}, ...],
         "preparation_level": [{"host_recipe_id","score","preparation_id","preparation_name","matched_subrecipes_count"}, ...]
       }
    """
    # 1) Niveau recette
    ranked_recipe = _rank_recipe_level_references(recipe, target_servings, target_pan, candidates)
    payload_recipe = [{"recipe_id": r.id, "score": s} for (r, s) in ranked_recipe]
    auto_selected = None
    if ranked_recipe:
        best = ranked_recipe[0]
        if _should_autoselect(best[1]):
            auto_selected = {"recipe_id": best[0].id, "score": best[1]}

    # 2) Niveau préparation (si pas d’auto-select)
    payload_prep = []
    if auto_selected is None:
        ranked_prep = _rank_preparation_level_references(recipe, target_servings, target_pan, candidates)
        payload_prep = [{
            "host_recipe_id": d["host_recipe"].id,
            "score": d["score"],
            "preparation_id": d["preparation_id"],
            "preparation_name": d["preparation_name"],
            "matched_subrecipes_count": d["matched_subrecipes_count"],
        } for d in ranked_prep]

    return {
        "auto_selected": auto_selected,
        "recipe_level": payload_recipe,
        "preparation_level": payload_prep,
    }
