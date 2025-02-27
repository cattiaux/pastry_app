import pytest, json, importlib
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.apps import apps
from rest_framework import status, serializers
# from pastry_app.serializers import IngredientSerializer, IngredientPriceSerializer, StoreSerializer

# Fonctions centrales 
def validate_constraint(model, field_name, value, expected_error, **valid_data):
    """ Applique une validation sur un champ en testant si une erreur spécifique est levée. """
    valid_data[field_name] = value
    with pytest.raises(ValidationError, match=expected_error):
        obj = model(**valid_data)
        obj.full_clean() # Déclenche clean() pour vérifier la contrainte

def validate_constraint_api(api_client, base_url, model_name, field_name, expected_errors, **valid_data):
    """
    Teste qu'une contrainte sur un champ (`field_name`) est bien appliquée via l'API.

    - `api_client` : Client de test DRF.
    - `base_url` : Fonction qui retourne l'URL de l'API.
    - `model_name` : Nom du modèle utilisé dans l'API.
    - `field_name` : Champ à tester.
    - `expected_errors` peut être un `str` (un seul message) ou une `list` (plusieurs erreurs possibles).
    - `valid_data` : Données valides par défaut.
    """
    url = base_url(model_name)  # Récupérer l'URL de création de l'objet
    response = api_client.post(url, valid_data, format="json")  # Envoyer la requête POST

    # Vérifier que l'API renvoie bien une erreur 400
    assert response.status_code == status.HTTP_400_BAD_REQUEST, f"Attendu 400, obtenu {response.status_code} : {response.json()}"
    # Vérifier que l'erreur est bien retournée sur le bon champ
    assert field_name in response.json(), f"L'erreur pour `{field_name}` n'a pas été trouvée dans la réponse : {response.json()}"
    # Vérifier si au moins UNE des erreurs attendues est présente
    actual_error = response.json()[field_name][0]
    if isinstance(expected_errors, list):  # Plusieurs erreurs possibles
        assert any(error in actual_error for error in expected_errors), f"Aucune des erreurs attendues `{expected_errors}` ne correspond à `{actual_error}`"
    else:  # Une seule erreur attendue
        assert expected_errors in actual_error, f"Erreur attendue `{expected_errors}`, mais obtenue `{actual_error}`"

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
# def validate_required_field(model, field_name, expected_error, **valid_data):
#     """ Vérifie qu'un champ obligatoire ne peut pas être vide ou nul. """
#     for invalid_value in [None, ""]:
#         validate_constraint(model, field_name, invalid_value, expected_error, **valid_data)

# def validate_required_field_api(api_client, base_url, model_name, field_name, **valid_data):
#     """ Vérifie qu'un champ est obligatoire au niveau de l’API en testant `None` et `""`. """
#     expected_errors = ["This field is required.", "This field may not be null.", "This field cannot be blank."]
#     for invalid_value in [None, ""]:  # Teste `None` et `""`
#         validate_constraint_api(api_client, base_url, model_name, field_name, expected_errors, **valid_data, **{field_name: invalid_value})

# def validate_min_length(model, field_name, min_length, expected_error, **valid_data):
#     """ Vérifie que le champ respecte une longueur minimale. """
#     validate_constraint(model, field_name, "a" * (min_length - 1), expected_error, **valid_data)

# def validate_min_length_api(api_client, base_url, model_name, field_name, min_length, **valid_data):
#     """ Vérifie qu'un champ respecte une longueur minimale via l’API. """
#     error_message = f"doit contenir au moins {min_length} caractères."
#     validate_constraint_api(api_client, base_url, model_name, field_name, error_message, **valid_data, **{field_name: "a" * (min_length - 1)})

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
    """ Normalise une chaîne en supprimant les espaces superflus et en la mettant en minuscule. """
    if isinstance(value, str):  # Vérifie que c'est bien une chaîne
        return " ".join(value.strip().lower().split())  
    return value  # Retourne la valeur telle quelle si ce n'est pas une chaîne

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

def validate_optional_field_value_api(api_client, base_url, model_name, field_name, mode="both", **valid_data):
    """
    Vérifie qu'un champ optionnel peut être vide (`""`) ou `None`, en fonction du `mode`.
    
    - `mode="empty"` → Teste uniquement `""`
    - `mode="none"` → Teste uniquement `None`
    - `mode="both"` → Teste `""` et `None`
    """
    url = base_url(model_name)

    test_values = []
    if mode in ["both", "empty"]:
        test_values.append("")
    if mode in ["both", "none"]:
        test_values.append(None)

    for value in test_values:
        valid_data[field_name] = value
        response = api_client.post(url, valid_data, format="json")
        
        assert response.status_code == status.HTTP_201_CREATED  # Doit réussir
        assert response.json()[field_name] == (value if value is not None else "")  # Vérification

def get_serializer_for_model(model_name):
    """ Récupère dynamiquement le serializer correspondant au modèle donné, sans import direct. """
    serializers_module = importlib.import_module("pastry_app.serializers")  # Charger le module des serializers
    serializer_map = {"ingredients": "IngredientSerializer", "ingredient_prices": "IngredientPriceSerializer", "stores": "StoreSerializer"}

    serializer_class_name = serializer_map.get(model_name)
    if serializer_class_name:
        return getattr(serializers_module, serializer_class_name, None)

    return None  # Retourne None si le serializer n'existe pas

def get_field_type(serializer, field_name):
    """ Détermine le type attendu pour un champ relationnel dans un serializer. """
    field = serializer.fields.get(field_name)
    if isinstance(field, serializers.PrimaryKeyRelatedField):
        return "id", None
    elif isinstance(field, serializers.SlugRelatedField):
        return "slug", field.slug_field # On retourne aussi le slug_field défini
    elif isinstance(field, serializers.ModelSerializer) or isinstance(field, serializers.ListSerializer):
        return "json", None
    return "unknown"

def create_related_models_api(api_client, base_url, related_models):
    """ 
    Crée dynamiquement des objets liés.
    
    - `related_models` → Liste de tuples contenant :
        (nom du modèle lié (pluriel), serializer, dict des relations, données associées).
    """
    created_instances = {}  # Stocke les objets créés

    for related_model_name, serializer_class, relation_mapping, related_data in related_models:
        serializer = serializer_class()  # Serializer associé au modèle

        # Associer dynamiquement les champs relationnels en fonction de leur type
        for field, related_model in relation_mapping.items():
            if related_model in created_instances:  # Vérifier si l'instance liée existe déjà
                expected_type, slug_field = get_field_type(serializer, field)

                if expected_type == "id":
                    related_data[field] = created_instances[related_model]["id"]
                elif expected_type == "slug":
                    related_data[field] = created_instances[related_model][slug_field]
                elif expected_type == "json":
                    related_data[field] = created_instances[related_model]
                else:
                    raise ValueError(f"Type inconnu '{expected_type}' pour {field} dans {related_model_name}")

        # Création via API
        related_url = base_url(related_model_name)
        response = api_client.post(related_url, related_data, format="json")
        assert response.status_code == status.HTTP_201_CREATED, f"Erreur lors de la création de {related_model_name}: {response.json()}"

        # Stocker l'objet créé
        created_instances[related_model_name] = response.json()

    return created_instances

def validate_protected_delete_api(api_client, base_url, main_model_name, related_models, expected_error):
    """
    Vérifie qu'un objet ne peut pas être supprimé via l'API s'il est référencé dans un ou plusieurs modèles.

    - `main_model_name` → Nom du modèle principal (pluriel).
    - `related_models` → Liste de tuples contenant :
        (nom du modèle lié (pluriel), serializer, dict des relations, données associées).
    - `expected_error` → Message d'erreur attendu.
    """
    # Étape 1 : Création de l'objet principal et des objets liés
    created_instances = create_related_models_api(api_client, base_url, related_models)

    # Étape 2 : Récupération de l'objet principal
    main_obj_id = created_instances[main_model_name]["id"] # Récupération de l'ID du modèle principal
    main_url = f"{base_url(main_model_name)}{main_obj_id}/"

    # Étape 3 : Tentative de suppression de l'objet principal
    response_delete = api_client.delete(main_url)
    assert response_delete.status_code == status.HTTP_400_BAD_REQUEST, (f"La suppression de {main_model_name} aurait dû être interdite, mais a réussi !")
    assert expected_error in response_delete.json().get("error", ""), (f"Le message d'erreur attendu ('{expected_error}') n'a pas été trouvé dans {response_delete.json()}.")
