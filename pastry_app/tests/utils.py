import pytest, json
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework import status

# Fonctions centrales 
def validate_constraint(model, field_name, value, expected_error, **valid_data):
    """ Applique une validation sur un champ en testant si une erreur spécifique est levée. """
    valid_data[field_name] = value
    with pytest.raises(ValidationError, match=expected_error):
        obj = model(**valid_data)
        obj.full_clean() # Déclenche clean() pour vérifier la contrainte

def validate_model_str(model, expected_str, **valid_data):
    """ Vérifie que la méthode `__str__()` du modèle retourne la bonne valeur. """
    obj = model.objects.create(**valid_data)
    assert str(obj) == expected_str, f"__str__() attendu : {expected_str}, obtenu : {str(obj)}"

def create_and_verify_model_instance(model, **valid_data):
    """ Crée une instance et vérifie que ses champs sont bien enregistrés. """
    obj = model.objects.create(**valid_data)
    assert model.objects.filter(id=obj.id).exists(), "L'objet n'a pas été créé correctement."
    return obj  # Retourne l'objet pour usage dans les tests

def update_and_verify_model(obj, field_name, new_value):
    """ Met à jour un champ et vérifie que la modification est bien enregistrée. """
    setattr(obj, field_name, new_value)
    obj.save()
    obj.refresh_from_db()
    assert getattr(obj, field_name) == new_value, f"Échec de la mise à jour du champ '{field_name}'"

def validate_delete_object(model, **valid_data):
    """ Vérifie qu'un objet peut être supprimé sans contrainte. """
    obj = model.objects.create(**valid_data)
    obj.delete()
    assert not model.objects.filter(id=obj.id).exists(), "L'objet n'a pas été supprimé."

# Vérifications générales sur les champs
def validate_required_field(model, field_name, expected_error, **valid_data):
    """ Vérifie qu'un champ obligatoire ne peut pas être vide ou nul. """
    for invalid_value in [None, ""]:
        validate_constraint(model, field_name, invalid_value, expected_error, **valid_data)

def validate_required_field_api(api_client, base_url, model_name, field_name, **valid_data):
    """ Vérifie qu'un champ est obligatoire au niveau de l’API en testant `None` et `""`. """
    url = base_url(model_name)
    expected_errors = ["This field is required.", "This field may not be null.", "This field cannot be blank."]

    for invalid_value in [None, ""]:  # Teste `None` et `""`
        data = {**valid_data, field_name: invalid_value}
        response = api_client.post(url, data, format="json")
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert field_name in response.json()
        # Vérifier si l'erreur retournée correspond à l'une des erreurs attendues
        assert any(error in response.json()[field_name][0] for error in expected_errors)

def validate_min_length(model, field_name, min_length, expected_error, **valid_data):
    """ Vérifie que le champ respecte une longueur minimale. """
    validate_constraint(model, field_name, "a" * (min_length - 1), expected_error, **valid_data)

def validate_min_length_api(api_client, base_url, model_name, field_name, min_length, **valid_data):
    """ Vérifie qu'un champ respecte une longueur minimale via l’API. """
    url = base_url(model_name)
    error_message = f"doit contenir au moins {min_length} caractères."

    response = api_client.post(url, {**valid_data, field_name: "a" * (min_length - 1)})  # Trop court
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field_name in response.json()
    assert error_message in response.json()[field_name][0]

def validate_unique_constraint(model, field_name, expected_error, **valid_data):
    """ Vérifie qu’un champ unique ne peut pas être dupliqué (unique=True). """
    instance = model.objects.create(**valid_data)
    # Modifier uniquement le champ testé pour forcer un doublon
    duplicate_data = valid_data.copy()
    duplicate_data[field_name] = getattr(instance, field_name)  # Même valeur
    with pytest.raises(IntegrityError, match=expected_error):
        model.objects.create(**duplicate_data)

def validate_unique_constraint_api(api_client, base_url, model_name, field_name, **valid_data):
    """
    Vérifie qu’un champ unique ne peut pas être dupliqué via l'API.

    - `field_name` → Le champ qui doit être unique.
    - `valid_data` → Autres champs obligatoires pour éviter une erreur sur des contraintes de validation.
    """
    url = base_url(model_name)

    # Assurez-vous que le champ testé est bien dans les données envoyées
    assert field_name in valid_data, f"Le champ '{field_name}' doit être inclus dans `valid_data`"

    # Création du premier objet (OK)
    response1 = api_client.post(url, data=json.dumps(valid_data), content_type="application/json")
    assert response1.status_code == status.HTTP_201_CREATED  # Doit réussir

    # Tentative de création du doublon (DOIT ÉCHOUER)
    response2 = api_client.post(url, data=json.dumps(valid_data), content_type="application/json")
    assert response2.status_code == status.HTTP_400_BAD_REQUEST  # Doit échouer

    # Vérification du message d’erreur (gestion dynamique)
    assert field_name in response2.json()
    assert any("unique" in error.lower() for error in response2.json()[field_name])  # Vérifie l'erreur d'unicitéq

def validate_unique_together(model, expected_error, create_initial=True, **valid_data):
    """ Vérifie qu'une contrainte `unique_together` est respectée et empêche la duplication. """
    if create_initial:
        model.objects.create(**valid_data) # Création de la première instance
    with pytest.raises(ValidationError) as excinfo:  # Capture l'exception complète
        obj = model(**valid_data)
        obj.full_clean()  # Déclenche la ValidationError avant le save
        obj.save()
    assert expected_error in str(excinfo.value)  # Convertir l'erreur en string pour comparaison

def validate_unique_together_api(api_client, base_url, model_name, valid_data):
    """ Vérifie qu'une contrainte `unique_together` est respectée en API et empêche la duplication. """
    url = base_url(model_name)
    # Construire dynamiquement le message d'erreur attendu
    field_names = ", ".join(valid_data.keys())  # Ex: "store_name, city, zip_code"
    error_message = f"The fields {field_names} must make a unique set."
    # Premier enregistrement (OK)
    response1 = api_client.post(url, data=json.dumps(valid_data), content_type="application/json")
    assert response1.status_code == status.HTTP_201_CREATED  # Création réussie

    # Deuxième enregistrement (doit échouer)
    response2 = api_client.post(url, data=json.dumps(valid_data), content_type="application/json")
    assert response2.status_code == status.HTTP_400_BAD_REQUEST  # Doit échouer
    assert error_message in response2.json().get("non_field_errors", [])  # Vérifier l'erreur attendue

def validate_update_to_duplicate_api(api_client, base_url, model_name, valid_data1, valid_data2):
    """ Vérifie qu'on ne peut PAS modifier un objet pour lui donner des valeurs déjà existantes sur un autre objet. """
    url = base_url(model_name)

    # Création de deux objets distincts
    response1 = api_client.post(url, valid_data1, format="json")
    response2 = api_client.post(url, valid_data2, format="json")
    assert response1.status_code == status.HTTP_201_CREATED
    assert response2.status_code == status.HTTP_201_CREATED

    obj_id = response2.json()["id"]  # ID du second objet

    # Tenter de mettre à jour `obj2` avec les valeurs de `obj1`
    response3 = api_client.patch(f"{url}{obj_id}/", valid_data1, format="json")
    assert response3.status_code == status.HTTP_400_BAD_REQUEST  # Vérifier que la mise à jour est rejetée
    assert "non_field_errors" in response3.json()  # Vérifier l’erreur sous `non_field_errors`
    assert "must make a unique set" in response3.json()["non_field_errors"][0]

def validate_protected_delete(model, related_model, related_field, expected_error, **valid_data):
    """ Vérifie qu'une suppression est bloquée si `on_delete=PROTECT`. """
    obj = model.objects.create(**valid_data)
    related_obj = related_model.objects.create(**{related_field: obj}) # Création d'un objet lié pour bloquer la suppression de `obj`
    with pytest.raises(IntegrityError, match=expected_error):
        obj.delete()

def normalize_case(value):
    """ Applique la même normalisation (lowercase) que dans les modèles. """
    return " ".join(value.lower().strip().split()) if value else value

def validate_field_normalization(model, field_name, input_value, **valid_data):
    """ Vérifie qu’un champ est bien normalisé lors de la création. """
    valid_data[field_name] = input_value  # Injecter la valeur brute
    instance = model.objects.create(**valid_data)
    assert getattr(instance, field_name) == normalize_case(input_value)

def validate_field_normalization_api(api_client, base_url, model_name, field_name, raw_value, **valid_data):
    """ Vérifie qu’un champ est bien normalisé après création via l’API. """
    url = base_url(model_name)
    valid_data[field_name] = raw_value  # Injecter la valeur brute
    response = api_client.post(url, valid_data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()[field_name] == normalize_case(raw_value)