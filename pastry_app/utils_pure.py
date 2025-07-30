from django.core.exceptions import ValidationError

def normalize_case(value):
    """ Normalise une chaîne en supprimant les espaces superflus et en la mettant en minuscule. """
    if isinstance(value, str):  # Vérifie que c'est bien une chaîne
        return " ".join(value.strip().lower().split())  
    return value  # Retourne la valeur telle quelle si ce n'est pas une chaîne

def calculate_quantity_multiplier(from_volume_cm3: float, to_volume_cm3: float) -> float:
    """
    Calcule le multiplicateur de quantité nécessaire pour passer d’un volume source à un volume cible.
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

def scale_sub_recipe(sub_recipe, required_quantity):
    # Get the default quantity of the sub-recipe
    default_quantity = sub_recipe.quantity

    # Calculate the scaling factor
    scaling_factor = required_quantity / default_quantity

    # Scale the quantities of the ingredients
    for recipe_ingredient in sub_recipe.recipeingredient_set.all():
        recipe_ingredient.quantity *= scaling_factor
        recipe_ingredient.save()

def get_servings_interval(volume_cm3: float) -> dict:
    """
    Calcule un intervalle réaliste de portions (min, standard, max) basé sur le volume.
    Hypothèse : 150ml = portion standard
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

def adapt_recipe_by_ingredients_constraints(recipe, ingredient_constraints: dict) -> dict:
    """
    Adapte une recette en fonction des quantités disponibles pour un ou plusieurs ingrédients.

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