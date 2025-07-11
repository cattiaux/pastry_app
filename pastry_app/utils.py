import math
from rest_framework import serializers
from django.shortcuts import get_object_or_404
from django.db import models as django_models
from django.db.models.functions import Abs
from .models import Recipe, Pan
from .utils_pure import *

def get_suggested_pans(volume_target: float) -> list[dict]:
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

def adapt_recipe_with_target_volume(recipe: Recipe, volume_target: float, volume_source: float = None) -> dict:
    """
    Fonction centrale d’adaptation d’une recette vers un volume cible donné.
    Utilisable avec un volume provenant d’un moule ou d’un nombre de portions.

    - Calcule le multiplicateur à partir du volume source (soit moule soit fourni manuellement)
    - Applique ce multiplicateur aux ingrédients
    - Estime un intervalle réaliste de portions sur le volume cible
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

def adapt_recipe_pan_to_pan(recipe: Recipe, target_pan: Pan) -> dict:
    """
    Adapte une recette d’un moule vers un autre moule.
    """
    if not target_pan.volume_cm3_cache:
        raise ValueError("Le volume du moule cible est inconnu.")

    return adapt_recipe_with_target_volume(recipe, target_pan.volume_cm3_cache)

def adapt_recipe_servings_to_volume(recipe: Recipe, target_servings: int) -> dict:
    """
    Adapte une recette à un nombre de portions cible (volume déduit via le pan de la recette).
    """
    if target_servings <= 0:
        raise ValueError("Le nombre de portions cible doit être supérieur à 0.")

    volume_target = target_servings * 150
    base_data = adapt_recipe_with_target_volume(recipe, volume_target)

    base_data["suggested_pans"] = get_suggested_pans(volume_target)
    return base_data

def adapt_recipe_servings_to_servings(recipe: Recipe, target_servings: int) -> dict:
    """
    Adapte une recette à un nombre de portions cible,
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

def estimate_servings_from_pan(pan: Pan = None, pan_type: str = None, diameter: float = None, height: float = None, length: float = None, 
                               width: float = None, rect_height: float = None, volume_raw: float = None) -> dict:
    """
    Estime le volume et l’intervalle de portions à partir d’un pan existant
    ou de dimensions fournies.
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
    Propose des moules adaptés à un nombre de portions cible,
    sans passer par une recette.
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





def update_related_instances(instance, related_data, related_set, related_model, related_serializer, instance_field_name):
    """
    This function updates related instances of a given instance.

    Parameters:
    - instance: The instance whose related instances are to be updated.
    - related_data: The validated data for the related instances.
    - related_set: The name of the related set on the instance.
    - related_model: The model class of the related instances.
    - related_serializer: The serializer class for the related instances.
    - instance_field_name: The name of the field on the related model that refers to the instance.
    """
    # Get the ids of the related instances to update or create
    update_ids = [data.get('id') for data in related_data if data.get('id') is not None]

    # Delete related instances that are not included in the update_ids
    for related_instance in getattr(instance, related_set).all():
        if related_instance.id not in update_ids:
            related_instance.delete()

    # Update existing related instances and create new ones
    for data in related_data:
        data_id = data.get('id', None)
        if data_id:
            related_instance = get_object_or_404(related_model, id=data_id, **{instance_field_name: instance})
            # Ensure the related field is a primary key, not a model instance
            for field, value in data.items():
                if isinstance(value, django_models.Model):
                    data[field] = value.id
            serializer = related_serializer(data=data, instance=related_instance)
            if serializer.is_valid():
                serializer.save()
            else:
                raise serializers.ValidationError(serializer.errors)
        else:
            related_model.objects.create(**{instance_field_name: instance}, **data)

MODEL_TO_URL_MAPPING = {
    "store": "stores",
    "ingredient": "ingredients",
    "category": "categories",
    "label": "labels",
    "ingredient_price": "ingredient_prices",
    # Ajoute d'autres modèles ici au besoin
}

def get_api_url_name(model_name):
    """ Renvoie le nom utilisé dans l'URL d'API pour un modèle donné. """
    return MODEL_TO_URL_MAPPING.get(model_name, f"{model_name}s")  # Fallback en ajoutant "s"

