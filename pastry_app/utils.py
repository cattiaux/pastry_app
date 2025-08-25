import math
from typing import Optional
from django.core.exceptions import ValidationError
from django.db import models as django_models
from django.db import transaction
from django.db.models.functions import Abs
from .models import Pan, Recipe, IngredientUnitReference, SubRecipe, RecipeIngredient, RecipeStep
from .text_utils import normalize_case
from .constants import SERVING_VOLUME_ML

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

def normalize_constraints_for_recipe(recipe, constraints, *, user=None, guest_id=None, cache=None):
    """
    constraints: dict[int, float | tuple[str, float]]
      - float/int = quantité déjà dans l’unité de la recette pour cet ingrédient
      - tuple = (unit, amount) à convertir vers l’unité de la recette

    Retourne: dict[int, float] dans l’unité du RecipeIngredient correspondant.
    Ignore les ingrédients absents de la recette.
    """
    if cache is None:
        cache = {}
    normalized = {}

    def _target_units_for_tree(recipe):
        # map {ingredient_id: unit_attendue_par_la_recette_ou_la_sous_recette}
        m = {ri.ingredient_id: ri.unit for ri in recipe.recipe_ingredients.all()}
        for link in recipe.main_recipes.all():              # descend récursivement
            m.update(_target_units_for_tree(link.sub_recipe))
        return m

    # Map des unités cibles (celles de la recette et de ses sous-recettes) par ingrédient
    target_units = _target_units_for_tree(recipe)

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
    return servings * SERVING_VOLUME_ML

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

def get_source_volume(recipe, prefer: Optional[str] = None):
    """
    Retourne (volume_source, mode) où mode ∈ {"pan", "servings"}.
    Si `prefer` est fourni, tente d'abord ce mode s'il est disponible,
    puis bascule sur l'autre. Fallback final: None, None.
    """
    # Pan (avec pan_quantity >= 1)
    pan = getattr(recipe, "pan", None)
    pan_vol = getattr(pan, "volume_cm3_cache", None) if pan else None
    if pan_vol:
        qty = getattr(recipe, "pan_quantity", 1) or 1
        pan_total_vol = float(pan_vol) * float(qty)
    else:
        pan_total_vol = None

    # Servings (moyenne si min & max, sinon min ou max)
    servings_min = getattr(recipe, "servings_min", None)
    servings_max = getattr(recipe, "servings_max", None)
    servings_avg = None
    if servings_min and servings_max:
        servings_avg = (float(servings_min) + float(servings_max)) / 2.0
    elif servings_min:
        servings_avg = float(servings_min)
    elif servings_max:
        servings_avg = float(servings_max)

    servings_vol = servings_to_volume(servings_avg) if servings_avg else None

    # 1) Respecte la préférence si possible
    if prefer == "servings" and servings_vol:
        return servings_vol, "servings"
    if prefer == "pan" and pan_total_vol:
        return pan_total_vol, "pan"

    # 2) Fallback: pan sinon servings (ancien comportement)
    if pan_total_vol:
        return pan_total_vol, "pan"
    if servings_vol:
        return servings_vol, "servings"

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

def _try_direct(recipe, target_servings=None, target_pan=None):
    """
    Tente un calcul 'direct' à partir de la recette source :
    - si target_pan : utilise le volume du pan cible
    - sinon si target_servings : utilise le volume équivalent servings cible
    Nécessite que la recette source ait une info scalable (pan.volume_cm3_cache OU servings_min/max).
    Retourne (multiplier, mode) OU (None, "raison de l'échec").
    """
    try:
        prefer = "servings" if (target_servings is not None and target_pan is None) else \
                 "pan" if (target_pan is not None and target_servings is None) else None

        source_volume, source_mode = get_source_volume(recipe, prefer=prefer)
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
                print("Reference pan volume:", ref_pan_volume)  # Debug log
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

def scale_recipe_globally(recipe, multiplier, *, user=None, guest_id=None, cache=None, return_warnings: bool=False):
    """
    Adapte récursivement une recette entière (ingrédients ET sous-recettes) avec un multiplicateur global.

    Cas d’usage
    -----------
    - Changer le nombre de portions
    - Changer de moule
    - Contraindre un ingrédient limitant
    - Appliquer un scaling homogène sur toute la recette

    Algorithme
    ----------
    1) Ingrédients DIRECTS de `recipe` :
       - Quantités × `multiplier` (unité inchangée).

    2) Pour chaque sous-recette (lien SubRecipe : A→B) :
       a) Quantité utilisée après scaling global :
            used_qty = SubRecipe.quantity * multiplier
       b) Conversion de `used_qty` en grammes via `_sub_used_grams(main_sub, sub_recipe)` :
            - mg/g/kg → g (direct)
            - ml/cl/l → g via densité de B :
                densité (g/cm³) = total_preparation_g / volume_preparation_cm3
                volume fourni par `get_source_volume(B)` ; 1 ml = 1 cm³
            - autres unités (ex. "portion", "QS") → conversion non définie ici → None
       c) Multiplicateur local appliqué aux ingrédients de B :
            local_multiplier = used_qty_g / total_preparation_g
          Si `used_qty_g` ou `total_preparation_g` manquent → fallback :
            local_multiplier = multiplier  (ancien comportement conservé)

    3) Calcul de `total_preparation_g` si nécessaire :
       - Appel non persistant : `compute_and_set_total_quantity(force=False, save=False, user, guest_id, cache)`
       - Règles internes de conversion vers g :
           * mg/g/kg directs
           * Références IngredientUnitReference (user/guest > global)
           * Fallback volumique : 1 ml = 1 g ; 1 cl = 10 g ; 1 L = 1000 g
           * QS :
               - override par-ingredient si fourni
               - sinon IUR(unit='QS')
               - sinon 0 g (ignoré dans le total)
         Avertissements collectables si l’option est activée.

    Propriétés
    ----------
    - Aucune écriture en base.
    - Utilise `cache` pour mémoïser les recherches d’unités (IUR).
    - Les avertissements (ex. conversions manquantes, QS non mappé) peuvent être collectés via `return_warnings=True`.

    Paramètres
    ----------
    recipe : Recipe
        Recette racine à adapter.
    multiplier : float
        Coefficient global de scaling.
    user, guest_id :
        Contexte pour les correspondances d’unités (IUR spécifiques puis globales).
    cache : dict | None
        Cache optionnel partagé lors de l’adaptation.
    return_warnings : bool
        False (défaut) → sortie inchangée. True → ajoute une clé "warnings" détaillant les notes de conversion.

    Retour
    ------
    dict
        {
          "recipe_id", "recipe_name", "scaling_multiplier",
          "ingredients": [...],
          "subrecipes": [...],
          # présent si return_warnings=True
          "warnings": [ {recipe_id, recipe_name, message}, ... ]
        }
    """
    warnings = []

    def _total_with_notes(rec):
        """
        Renvoie la masse totale (g) de la recette `rec` sans écriture en base.

        Rôle
        ----
        - Si `return_warnings` (portée englobante) est True : appelle
        `rec.compute_and_set_total_quantity(force=False, save=False, user=user, guest_id=guest_id, cache=cache, collect_warnings=True)`
        puis agrège chaque note dans la liste `warnings` (portée englobante) avec le contexte recette.
        - Sinon : appelle la même méthode avec `collect_warnings=False` et renvoie le float.

        Entrées
        -------
        rec : Recipe
            Préparation pour laquelle on souhaite `total_recipe_quantity`.

        Contexte capturé (portée englobante)
        ------------------------------------
        user, guest_id : sélection des IUR spécifiques (user/guest) puis globales.
        cache : dict partagé pour mémoïsation IUR.
        return_warnings : bool
        warnings : list[dict] accumulatrice (remplie seulement si `return_warnings=True`).

        Conversion (déléguée à `compute_and_set_total_quantity`)
        --------------------------------------------------------
        - mg/g/kg massiques directs
        - IUR (IngredientUnitReference) user/guest > global
        - fallback volumique : ml = 1 g, cl = 10 g, L = 1000 g
        - QS : override > IUR(QS) > 0 g par défaut

        Effets / erreurs
        ----------------
        - Aucune écriture DB (`save=False`).
        - Pas d’exception levée en mode non strict ; les unités non convertibles sont ignorées avec note.
        - Réutilise `cache` pour limiter les requêtes.

        Retour
        ------
        float
            Total en grammes calculé (ou réutilisé si déjà présent et `force=False`).
        """
        if return_warnings:
            total, notes = rec.compute_and_set_total_quantity(
                force=False, user=user, guest_id=guest_id, save=False, cache=cache, collect_warnings=True
            )
            # contexte
            for msg in notes:
                warnings.append({"recipe_id": rec.id, "recipe_name": getattr(rec, "recipe_name", ""), "message": msg})
            return total
        # mode legacy
        return rec.compute_and_set_total_quantity(
            force=False, user=user, guest_id=guest_id, save=False, cache=cache
        )
    
    # --- Helper interne : convertit la quantité utilisée d'une sous-recette en grammes ---
    def _sub_used_grams(main_sub, sub_recipe):
        """
        Convertit la quantité utilisée de `sub_recipe` (après scaling global) en grammes.

        Entrées
        -------
        main_sub : SubRecipe
            Lien A→B. `main_sub.quantity` exprimée dans `main_sub.unit`.
        sub_recipe : Recipe
            Recette B (préparation) utilisée par la recette hôte.

        Règles de conversion
        --------------------
        1) Unités massiques : conversion directe
        - mg → /1000
        - g  → ×1
        - kg → ×1000

        2) Unités volumiques : conversion via densité de la sous-recette
        - Nécessite :
            * masse totale de B en g : `total_preparation_g`
            (si absente, tentative via `sub_recipe.compute_and_set_total_quantity(force=False, save=False)`)
            * volume de B en cm³ : `get_source_volume(sub_recipe)`  (1 ml = 1 cm³)
        - Densité : `density_g_per_cm3 = total_preparation_g / volume_sub_cm3`
        - Quantité utilisée convertie en cm³ :
            ml → ml
            cl → ×10
            l  → ×1000
        - Grammes = cm³ × densité

        3) Autres unités (ex. "portion", "QS") : non converties ici → retour `None`
        (le code appelant applique alors le fallback: `local_multiplier = multiplier`).

        Sortie
        ------
        float | None
            Grammes calculés ou `None` si la conversion est impossible
            (densité indisponible ou unité non massique/volumique).

        Effets de bord
        --------------
        - Aucun write DB. Pas d’exception levée.
        - Les avertissements éventuels sont gérés au niveau appelant si activés.
        """
        used_qty = float(main_sub.quantity) * float(multiplier)
        used_unit = main_sub.unit

        # Massique
        if used_unit == "g":
            return used_qty
        if used_unit == "mg":
            return used_qty / 1000.0
        if used_unit == "kg":
            return used_qty * 1000.0

        # Volumique → nécessite densité de B (total / volume)
        if used_unit in ("ml", "cl", "l"):
            # Masse totale (g) de la préparation
            total_preparation_g = getattr(sub_recipe, "total_recipe_quantity", None)
            if total_preparation_g is None:
                total_preparation_g = _total_with_notes(sub_recipe)

            # volume de B en cm³ (1 ml = 1 cm³)
            volume_cm3, _ = get_source_volume(sub_recipe)
            if not (total_preparation_g and volume_cm3):
                if return_warnings:
                    warnings.append({
                        "recipe_id": sub_recipe.id, "recipe_name": getattr(sub_recipe, "recipe_name", ""),
                        "message": "Densité indisponible (total/volume manquant). Fallback multiplicateur global."
                    })
                return None

            density_g_per_cm3 = float(total_preparation_g) / float(volume_cm3)  # g / cm³
            qty_cm3 = used_qty if used_unit == "ml" else used_qty * 10.0 if used_unit == "cl" else used_qty * 1000.0  # l → ml/cm³
            return qty_cm3 * density_g_per_cm3

        # Unité inattendue (devrait être filtrée par le modèle/serializer)
        return None
    
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
    for main_sub in recipe.main_recipes.all():  # <- lien SubRecipe (dans la recette hôte)
        sub_recipe = main_sub.sub_recipe    # <- la recette utilisée comme préparation

        # La quantité de sous-recette utilisée est scaled globalement (toujours dans l’unité d’origine de la liaison)
        scaled_quantity = float(main_sub.quantity) * float(multiplier)

        # conversion en g + total de la préparation
        used_qty_g = _sub_used_grams(main_sub, sub_recipe)
        total_preparation_g = getattr(sub_recipe, "total_recipe_quantity", None)
        if total_preparation_g is None:
            total_preparation_g = _total_with_notes(sub_recipe)

        # multiplicateur local
        if used_qty_g is not None and total_preparation_g:
            local_multiplier = float(used_qty_g) / float(total_preparation_g)
        else:
            local_multiplier = float(multiplier)  # fallback: ancien comportement

        # Récursivité : adapte la sous-recette avec le multiplicateur local calculé
        adapted_sub = scale_recipe_globally(sub_recipe, local_multiplier, user=user, guest_id=guest_id, cache=cache, return_warnings=return_warnings)
        if return_warnings and "warnings" in adapted_sub:
            warnings.extend(adapted_sub["warnings"])

        adapted_subrecipes.append({
            "sub_recipe_id": sub_recipe.id,
            "sub_recipe_name": getattr(sub_recipe, "recipe_name", ""),
            "original_quantity": main_sub.quantity,
            "quantity": round(scaled_quantity, 2),
            "unit": main_sub.unit,
            "ingredients": adapted_sub["ingredients"],      # déjà scaled
            "subrecipes": adapted_sub["subrecipes"],        # récursivité profonde
            "scaling_multiplier": local_multiplier,
        })

    # 3. Structure de retour
    out = {
        "recipe_id": recipe.id,
        "recipe_name": getattr(recipe, "recipe_name", ""),
        "scaling_multiplier": multiplier,
        "ingredients": adapted_ingredients,
        "subrecipes": adapted_subrecipes,
    }
    if return_warnings:
        out["warnings"] = warnings
    return out

# ============================================================
# 4. CAS PARTICULIERS (ADAPTATION PAR CONTRAINTE)
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

    # Sous-recettes (récursif) — on NE propage PAS l'erreur "aucune correspondance"
    for main_sub in recipe.main_recipes.all():
        try :
            sub_multipliers = get_limiting_multiplier(main_sub.sub_recipe, ingredient_constraints)
        except ValidationError as e:
            sub_multipliers = None  # pas de match dans cette branche
        if sub_multipliers:  # sub_multipliers est soit None, soit un tuple
            multipliers.append(sub_multipliers)

    if not multipliers:
        raise ValidationError("Aucune correspondance entre les ingrédients de la recette et les contraintes fournies.")

    # Facteur limitant = le plus petit multiplicateur
    return min(multipliers, key=lambda x: x[0])  # (multiplier, ing_id)

# ============================================================
# 5. HELPERS : SÉLECTION DE RECETTE DE RÉFÉRENCE
# ============================================================

# 5.0 — Mini-config interne (règles, poids, seuils)
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

# 5.1 — Helpers utilitaires

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

# 5.2 — Éligibilité des candidats
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
            candidates = candidates.filter(
                django_models.Q(categories__parent_category__in=list(base_parent)) |
                django_models.Q(categories__in=list(base_parent))
            ).distinct()            
            # candidates = candidates.filter(categories__parent_category__in=list(base_parent)).distinct()
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

# 5.3 — Scoring

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

# 5.4 — Ranking + wrapper public

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

def taxonomy_score(host, wanted_category_ids=None, wanted_label_ids=None, wanted_tags=None):
    """
    Calcule un score purement taxonomique pour classer un usage 'as_preparation'.
    - host: recette hôte (obj Recipe) dans laquelle la préparation est utilisée.
    - wanted_category_ids: iterable[int] de catégories à favoriser (peut être None).
    - wanted_label_ids: iterable[int] de labels à favoriser (peut être None).
    - wanted_tags: iterable[str] de tags à favoriser (peut être None).
    Règles:
      +3 si l'hôte possède ≥1 des catégories voulues
      +2 par label commun
      +1 par tag commun
      +0.5 si l'hôte a un pan
      +0.5 si l'hôte a des servings (min ou max)
    Retourne: float (score). N’utilise pas le volume ni la popularité.
    """
    score = 0.0
    if wanted_category_ids:
        if host.categories.filter(id__in=wanted_category_ids).exists():
            score += 3.0
    if wanted_label_ids:
        score += 2.0 * host.labels.filter(id__in=wanted_label_ids).count()
    if wanted_tags:
        host_tags = set(host.tags or [])
        score += 1.0 * len(host_tags.intersection(set(wanted_tags)))
    if host.pan_id:
        score += 0.5
    if host.servings_min or host.servings_max:
        score += 0.5
    return score

# ============================================================
# 6. SUGGESTIONS ET ESTIMATIONS
# ============================================================

def _get_servings_interval(volume_cm3: float) -> dict:
    """
    Calcule un intervalle réaliste de portions (min, standard, max) basé sur le volume.
    Utilisé dans la suggestion et l’estimation de moules/servings.
    Hypothèse standard : 150ml = portion standard (constante SERVING_VOLUME_ML)
    """
    if volume_cm3 <= 0:
        raise ValueError("Volume invalide pour estimer les portions.")

    standard = round(volume_cm3 / SERVING_VOLUME_ML)

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
    target_volume = target_servings * SERVING_VOLUME_ML

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
    Règle :
    - On classe d’abord au NIVEAU RECETTE.
    - Si le meilleur match dépasse le seuil d’auto-select → on marque l’item correspondant avec selected=True,
      et on NE calcule pas le niveau préparation.
    - Sinon, on renvoie aussi le NIVEAU PRÉPARATION (items "level": "preparation").
    - La recette hôte est exclue des résultats.

    Retourne une LISTE d'items prêts pour le front (format plat et stable) :
    [
      {
        "id": <recipe_id>,
        "recipe_name": <str>,
        "total_recipe_quantity": <float|null>,
        "category": <str|null>,
        "parent_category": <str|null>,
        "score": <float|null>,
        "level": "recipe" | "preparation",
        "selected": <bool>,                   # True si auto-select
        # champs optionnels utiles en niveau préparation :
        "preparation_id": <int|None>,
        "preparation_name": <str|None>,
        "matched_subrecipes_count": <int|None>,
      },
      ...
    ]
    """
    # --------- helpers locaux (inline, pas de fonctions globales) ---------
    def _str_or_none(obj):
        return str(obj) if obj is not None else None

    def _flat_from_recipe(r, *, score=None, level="recipe", selected=False,
                          preparation_id=None, preparation_name=None, matched_subrecipes_count=None):
        cat = getattr(r, "category", None)
        parent_cat = getattr(cat, "parent_category", None) if cat else None
        return {
            "id": r.id,
            "recipe_name": getattr(r, "recipe_name", None),
            "total_recipe_quantity": getattr(r, "total_recipe_quantity", None),
            "category": _str_or_none(cat),
            "parent_category": _str_or_none(parent_cat),
            "score": float(score) if score is not None else None,
            "level": level,
            "selected": bool(selected),
            "preparation_id": preparation_id,
            "preparation_name": preparation_name,
            "matched_subrecipes_count": matched_subrecipes_count,
        }
    
    # 1) Niveau recette
    ranked_recipe = _rank_recipe_level_references(recipe, target_servings, target_pan, candidates=candidates) or []

    auto_selected_id = None
    if ranked_recipe:
        top_r, top_s = ranked_recipe[0]
        if _should_autoselect(top_s):
            auto_selected_id = top_r.id

    items = []
    for r, s in ranked_recipe:
        if r.id == recipe.id:
            continue  # exclure la recette courante
        items.append(_flat_from_recipe(r, score=s, level="recipe", selected=(r.id == auto_selected_id)))

    # 2) Niveau préparation (si pas d’auto-select)
    if auto_selected_id is None:
        ranked_prep = _rank_preparation_level_references(
            recipe, target_servings=target_servings, target_pan=target_pan, candidates=candidates
        ) or []
        for d in ranked_prep:
            host = d["host_recipe"]
            if host.id == recipe.id:
                continue
            items.append(_flat_from_recipe(
                host,
                score=d.get("score"),
                level="preparation",
                selected=False,
                preparation_id=d.get("preparation_id"),
                preparation_name=d.get("preparation_name"),
                matched_subrecipes_count=d.get("matched_subrecipes_count"),
            ))

    return items

# ============================================================
# 7. HELPERS : SÉLECTION DE RECETTE DE RÉFÉRENCE
# ============================================================

def clone_recipe_for_host(source: Recipe, host: Recipe, *, user=None, guest_id=None, name_suffix=None) -> Recipe:
    """Clone `source` en variante possédée par `host` (parent=source, owned_by_recipe=host).
       Réutilise la variante existante si déjà créée."""
    with transaction.atomic():
        existing = Recipe.objects.filter(parent_recipe=source, owned_by_recipe=host).first()
        if existing:
            return existing

        variant = Recipe.objects.create(
            recipe_name=f"{source.recipe_name} [usage: {host.recipe_name}]" if not name_suffix else f"{source.recipe_name} {name_suffix}",
            chef_name=source.chef_name or "",
            recipe_type="VARIATION",
            pan=source.pan, pan_quantity=source.pan_quantity,
            servings_min=source.servings_min, servings_max=source.servings_max,
            total_recipe_quantity=source.total_recipe_quantity,
            user=host.user or source.user, guest_id=host.guest_id or source.guest_id,
            visibility="private", is_default=False,
            parent_recipe=source, owned_by_recipe=host,
            context_name=(source.context_name or "") 
        )
        # Ingrédients
        for ri in source.recipe_ingredients.all():
            RecipeIngredient.objects.create(recipe=variant, ingredient=ri.ingredient, quantity=ri.quantity, unit=ri.unit, display_name=ri.display_name)
        # Étapes
        for st in source.steps.all():
            RecipeStep.objects.create(recipe=variant, step_number=st.step_number, instruction=st.instruction, trick=st.trick)
        # Sous-recettes (liaisons)
        for sr in source.main_recipes.all():
            SubRecipe.objects.create(recipe=variant, sub_recipe=sr.sub_recipe, quantity=sr.quantity, unit=sr.unit)
        # M2M
        variant.categories.set(source.categories.all())
        variant.labels.set(source.labels.all())
        return variant

def create_variant_for_host_and_rewire(subrecipe: SubRecipe, host: Recipe, *, user=None, guest_id=None) -> Recipe:
    """Si subrecipe.sub_recipe n’est pas encore une variante pour `host`, créer/brancher la variante et retourner la cible."""
    target = subrecipe.sub_recipe
    if target.owned_by_recipe_id == host.id:
        return target
    variant = clone_recipe_for_host(target, host, user=user, guest_id=guest_id)
    subrecipe.sub_recipe = variant
    subrecipe.save(update_fields=["sub_recipe"])
    return variant

# ============================================================
# 8. UTILS FRONT : CREATION TREE
# ============================================================

def build_tree_from_db(recipe):
    """
    Construit l’arbre hiérarchique d’une recette depuis l’ORM.
    Utilise:
      - Recipe.recipe_ingredients (quantity, unit, display_name)
      - Recipe.steps (step_number, instruction, trick)
      - Recipe.main_recipes → SubRecipe (sub_recipe, quantity, unit)
    Retour:
      {
        "recipe_id": int,
        "recipe_name": str|None,
        "ingredients": [{"ri_id": int, "ingredient_id": int, "display_name": str|None,
                         "original_quantity": float, "quantity": float, "unit": str}],
        "steps": [{"step_id": int, "step_number": int|None, "instruction": str, "trick": str|None}],
        "subrecipes": [ {**<noeud enfant>, "link_quantity": float, "link_unit": str} ]
      }
    """
    node = {
        "recipe_id": recipe.id,
        "recipe_name": getattr(recipe, "recipe_name", None),
        "ingredients": [
            {
                "ri_id": ri.id,
                "ingredient_id": ri.ingredient_id,
                "display_name": getattr(ri, "display_name", None),
                "original_quantity": ri.quantity,
                "quantity": ri.quantity,  # non-scalé
                "unit": ri.unit,
            }
            for ri in recipe.recipe_ingredients.select_related("ingredient").all()
        ],
        "steps": [
            {
                "step_id": s.id,
                "step_number": s.step_number,
                "instruction": s.instruction,
                "trick": getattr(s, "trick", None),
            }
            for s in recipe.steps.order_by("step_number", "id").all()
        ],
        "subrecipes": [],
    }

    # Liens vers sous-recettes avec méta du lien (quantity, unit)
    for link in recipe.main_recipes.select_related("sub_recipe").all():
        child = build_tree_from_db(link.sub_recipe)
        child["link_quantity"] = link.quantity
        child["link_unit"] = link.unit
        node["subrecipes"].append(child)

    return node

def build_tree_from_scaled(scaled_node):
    """
    Normalise un nœud déjà scalé en structure uniforme.
    Tolère:
      - clés 'subrecipes' ou 'children'
      - steps avec 'step_number' OU 'order' (fallback)
      - ingrédients avec 'scaled_quantity' OU 'quantity'
      - méta de lien: 'link_quantity', 'link_unit' si présents
    """
    # steps normalisés
    steps_src = scaled_node.get("steps") or []
    norm_steps = []
    for s in steps_src:
        norm_steps.append({
            "step_id": s.get("step_id") or s.get("id"),
            "step_number": s.get("step_number", s.get("order")),
            "instruction": s.get("instruction") or s.get("text"),
            "trick": s.get("trick"),
        })

    # ingrédients normalisés
    ings_src = scaled_node.get("ingredients") or []
    norm_ings = []
    for i in ings_src:
        norm_ings.append({
            "ri_id": i.get("ri_id") or i.get("id"),
            "ingredient_id": i.get("ingredient_id"),
            "display_name": i.get("display_name"),
            "original_quantity": i.get("original_quantity"),
            "quantity": i.get("scaled_quantity", i.get("quantity")),
            "unit": i.get("unit"),
        })

    # enfants
    children = scaled_node.get("subrecipes") or scaled_node.get("children") or []
    norm_children = []
    for ch in children:
        child = build_tree_from_scaled(ch)
        # propage éventuelle méta de lien si déjà présente
        if "link_quantity" in ch:
            child["link_quantity"] = ch["link_quantity"]
        if "link_unit" in ch:
            child["link_unit"] = ch["link_unit"]
        norm_children.append(child)

    return {
        "recipe_id": scaled_node.get("recipe_id") or scaled_node.get("id"),
        "recipe_name": scaled_node.get("recipe_name") or scaled_node.get("name"),
        "ingredients": norm_ings,
        "steps": norm_steps,
        "subrecipes": norm_children,
    }

def flatten_ingredients(tree):
    """
    Aplati l’arbre en liste d’ingrédients avec provenance.
    Ajoute:
      - source_recipe_id: id du nœud contenant l’ingrédient
      - source_path: chemin depuis la racine [{id,name}, ...]
      - link_quantity/link_unit si le nœud provient d’un lien SubRecipe
    """
    out = []

    def walk(n, path, edge_meta=None):
        cur = path + (
            [{"id": n.get("recipe_id"), "name": n.get("recipe_name")}]
            if n.get("recipe_id") or n.get("recipe_name") else []
        )
        for i in n.get("ingredients", []):
            row = {
                "ri_id": i["ri_id"],
                "ingredient_id": i["ingredient_id"],
                "display_name": i["display_name"],
                "quantity": i["quantity"],
                "original_quantity": i.get("original_quantity"),
                "unit": i["unit"],
                "source_recipe_id": n.get("recipe_id"),
                "source_path": cur,
            }
            if edge_meta:
                row["link_quantity"] = edge_meta.get("link_quantity")
                row["link_unit"] = edge_meta.get("link_unit")
            out.append(row)

        for ch in n.get("subrecipes", []):
            ch_meta = {
                "link_quantity": ch.get("link_quantity"),
                "link_unit": ch.get("link_unit"),
            }
            walk(ch, cur, ch_meta)

    walk(tree, [], None)
    return out

def flatten_steps(tree):
    """
    Aplati l’arbre en liste d’étapes avec provenance.
    Ajoute:
      - source_recipe_id
      - source_path
      - link_quantity/link_unit si le nœud provient d’un lien SubRecipe
    """
    out = []

    def walk(n, path, edge_meta=None):
        cur = path + (
            [{"id": n.get("recipe_id"), "name": n.get("recipe_name")}]
            if n.get("recipe_id") or n.get("recipe_name") else []
        )
        for s in n.get("steps", []):
            row = {
                "step_id": s["step_id"],
                "step_number": s.get("step_number"),
                "instruction": s.get("instruction"),
                "trick": s.get("trick"),
                "source_recipe_id": n.get("recipe_id"),
                "source_path": cur,
            }
            if edge_meta:
                row["link_quantity"] = edge_meta.get("link_quantity")
                row["link_unit"] = edge_meta.get("link_unit")
            out.append(row)

        for ch in n.get("subrecipes", []):
            ch_meta = {
                "link_quantity": ch.get("link_quantity"),
                "link_unit": ch.get("link_unit"),
            }
            walk(ch, cur, ch_meta)

    walk(tree, [], None)
    return out

def compose_full(recipe, scaled_data=None):
    """
    Compose le payload front-ready.
    - Si scaled_data est fourni: normalise via build_tree_from_scaled().
    - Sinon: construit via build_tree_from_db().
    Retourne:
      {
        "recipe_id": int, "recipe_name": str|None,
        "tree": <noeud>,
        "flat_ingredients": [..], "flat_steps": [..]
      }
    """
    tree = build_tree_from_scaled(scaled_data) if scaled_data else build_tree_from_db(recipe)
    return {
        "recipe_id": recipe.id,
        "recipe_name": getattr(recipe, "recipe_name", None),
        "tree": tree,
        "flat_ingredients": flatten_ingredients(tree),
        "flat_steps": flatten_steps(tree),
    }
