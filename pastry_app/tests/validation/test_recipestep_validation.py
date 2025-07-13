import pytest
from rest_framework import status
from pastry_app.models import Recipe, RecipeStep
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import *

# Définir model_name pour les tests de RecipeStep
model_name = "recipesteps"
pytestmark = pytest.mark.django_db

@pytest.fixture
def recipe():
    """Crée une recette par défaut pour tester les RecipeStep."""
    return Recipe.objects.create(recipe_name="Tarte aux fraises", chef_name="Martin")

@pytest.fixture
def recipestep(recipe):
    """ Crée un RecipeStep de test associé à une recette existante. """
    return RecipeStep.objects.create(recipe=recipe, step_number=1, instruction="Mélanger la farine et le sucre.")

@pytest.mark.parametrize("field_name", ["recipe", "instruction"])
def test_required_fields_recipestep_api(admin_client, base_url, field_name, recipestep):
    """ Vérifie que les champs obligatoires sont bien requis via l'API """
    expected_errors = ["This field is required.", "This field may not be null.", "This field cannot be blank.", "This field may not be blank."]
    valid_data = {"recipe": recipestep.recipe.id, "step_number": recipestep.step_number, "instruction": recipestep.instruction}  # Valeurs valides par défaut
    # test de la chaîne vide ""
    valid_data[field_name] = ""  # Remplace par une valeur invalide
    validate_constraint_api(admin_client, base_url, model_name, field_name, expected_errors, **valid_data)
    # test du champ manquant
    valid_data.pop(field_name)  # Supprimer le champ en cours de test des valeurs valides
    validate_constraint_api(admin_client, base_url, model_name, field_name, expected_errors, **valid_data)

@pytest.mark.parametrize("field_name", ["step_number"])
def test_unique_value_api(api_client, base_url, field_name, recipestep):
    """ Vérifie que `step_number` doit être unique pour une même recette via l’API. """
    valid_data = {"recipe": recipestep.recipe.id, "step_number": recipestep.step_number, "instruction": recipestep.instruction}
    response = validate_unique_constraint_api(api_client, base_url, model_name, field_name, **valid_data)
    assert "step_number" in response.json(), f"L'erreur d'unicité n'a pas été détectée : {response.json()}"
    assert "Ce numéro d'étape existe déjà pour cette recette." in response.json()["step_number"][0], (
        f"Message d'erreur attendu non trouvé dans {response.json()['step_number']}"
    )

@pytest.mark.parametrize("field_name, invalid_value", [("step_number", 0), ("step_number", -1)])
def test_step_number_must_start_at_1_api(api_client, base_url, field_name, invalid_value, recipe):
    """ Vérifie que `step_number` doit être >= 1 via l'API """
    expected_errors = ["Step number must start at 1.", "Ensure this value is greater than or equal to 1."]
    valid_data = {"recipe": recipe.id, "step_number": invalid_value, "instruction": "Étape invalide."}
    validate_constraint_api(api_client, base_url, model_name, field_name, expected_errors, **valid_data)

@pytest.mark.parametrize("field_name", ["instruction"])
def test_min_length_fields_recipestep_api(api_client, base_url, field_name, recipestep):
    """ Vérifie que `instruction` doit avoir une longueur minimale """
    valid_data = {"recipe": recipestep.recipe.id, "step_number": recipestep.step_number, "instruction": recipestep.instruction}  # Valeurs valides par défaut
    valid_data.pop(field_name)  # Supprimer le champ en cours de test des valeurs valides
    min_length = 5
    error_message = f"doit contenir au moins {min_length} caractères."
    validate_constraint_api(api_client, base_url, model_name, field_name, error_message, **valid_data, **{field_name: "a" * (min_length - 1)})

@pytest.mark.parametrize("field_name", ["trick"])
def test_trick_is_optional_api(api_client, base_url, field_name, recipestep):
    """ Vérifie que `trick` est un champ optionnel dans l'API """
    url = base_url(model_name)  

    for i, value in enumerate([None, ""]):
        valid_data = {"recipe": recipestep.recipe.id, "step_number": recipestep.step_number + i + 1, "instruction": recipestep.instruction, 
                      field_name: value}
        response = api_client.post(url, valid_data, format="json")
        assert response.status_code == status.HTTP_201_CREATED, (f"Erreur : {response.status_code}, réponse : {response.json()}")
        assert response.json()[field_name] == value, (f"Erreur sur {field_name}: attendu `{value}`, obtenu `{response.json()[field_name]}`")

def test_create_step_auto_increment_api(api_client, base_url, recipestep):
    """ Vérifie que `step_number` est auto-incrémenté s’il est omis """
    url = base_url(model_name)
    step2_data = {"recipe": recipestep.recipe.id, "instruction": "Étape 2"}  # Pas de `step_number`
    response2 = api_client.post(url, step2_data, format="json")
    assert response2.status_code == status.HTTP_201_CREATED
    assert response2.json()["step_number"] == 2  # Vérifie auto-incrémentation

def test_cannot_delete_last_recipestep_api(api_client, base_url, recipestep):
    """ Vérifie qu'on ne peut pas supprimer le dernier `RecipeStep` d'une recette """
    url = base_url(model_name)
    delete_response = api_client.delete(f"{url}{recipestep.id}/")
    print(delete_response.json())
    assert delete_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Une recette doit contenir au moins une étape." in delete_response.json()["detail"]

def test_step_number_must_be_strictly_increasing_api(api_client, base_url, recipestep):
    """Vérifie que `step_number` doit être strictement croissant via l’API."""
    expected_errors = ["Step numbers must be consecutive."]
    # Tentative de création d'un RecipeStep avec un step_number non consécutif
    valid_data = {"recipe": recipestep.recipe.id, "step_number": recipestep.step_number + 5, "instruction": "Étape non consécutive."}
    validate_constraint_api(api_client, base_url, model_name, "step_number", expected_errors, **valid_data)



def test_api_patch_step_number_to_null_forbidden(api_client, base_url, recipestep):
    """On ne peut pas PATCH une étape pour rendre son step_number null."""
    url = f"{base_url(model_name)}{recipestep.id}/"
    response = api_client.patch(url, {"step_number": None}, format="json")
    assert response.status_code == 400
    assert "this field may not be null" in str(response.data).lower()

@pytest.mark.parametrize("step_number, instruction, expected_status", [
    (None, "Étape correcte", 201),          # auto-incrément
    (1, "Étape manuelle", 201),             # ok explicite
    (0, "Étape nulle", 400),                # interdit < 1
    (None, "Non", 400),                     # instruction trop courte
])
def test_api_step_number_and_instruction(api_client, base_url, recipe, step_number, instruction, expected_status):
    """API : test divers cas création/validation RecipeStep."""
    url = base_url(model_name)
    payload = {"recipe": recipe.id, "instruction": instruction}
    if step_number is not None:
        payload["step_number"] = step_number
    resp = api_client.post(url, payload, format="json")
    assert resp.status_code == expected_status