import pytest, json, importlib
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework import status, serializers

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
    assert response.status_code == status.HTTP_400_BAD_REQUEST, f"Attendu 400, obtenu {response.status_code} : {response.json()}" # Vérifier que l'API renvoie bien une erreur 400
    assert field_name in response.json(), f"L'erreur pour `{field_name}` n'a pas été trouvée dans la réponse : {response.json()}" # Vérifier que l'erreur est bien retournée sur le bon champ
    
    # Vérifier si au moins UNE des erreurs attendues est présente
    actual_error = response.json()[field_name][0]
    if isinstance(expected_errors, list):  # Plusieurs erreurs possibles
        assert any(error in actual_error for error in expected_errors), f"Aucune des erreurs attendues `{expected_errors}` ne correspond à `{actual_error}`"
    else:  # Une seule erreur attendue
        assert expected_errors in actual_error, f"Erreur attendue `{expected_errors}`, mais obtenue `{actual_error}`"

def validate_model_str(model, expected_str, create_initial=True, **valid_data):
    """ Vérifie que la méthode `__str__()` du modèle retourne la bonne valeur. """
    if create_initial : 
        print(valid_data)
        obj = model(**valid_data)
    else:
        obj = model.objects.create(**valid_data)
    print("instance : ", obj)
    obj.full_clean()
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

def validate_unique_together(model, expected_error, **valid_data):
    """ Vérifie qu'une contrainte `unique_together` est respectée et empêche la duplication. """
    # Vérifier si un objet existe déjà en base
    existing_object = model.objects.filter(**valid_data).exists()
    if not existing_object: # Si aucun objet n'existe et qu'on doit en créer un premier, on le fait
        model.objects.create(**valid_data)  

    # Tenter de créer un deuxième objet identique et s'assurer que l'erreur est levée
    with pytest.raises(ValidationError) as excinfo:
        obj = model(**valid_data)
        obj.full_clean()  # Déclenche la ValidationError avant le save
        obj.save()
    assert expected_error in str(excinfo.value), f"Erreur attendue '{expected_error}' non trouvée dans '{excinfo.value}'" # Vérifier que l'erreur attendue est bien levée

def validate_unique_together_api(api_client, base_url, model_name, valid_data):
    """ Vérifie qu'une contrainte `unique_together` est respectée en API et empêche la duplication. """
    url = base_url(model_name)
    # Construire dynamiquement le message d'erreur attendu
    error_message = "must make a unique set."
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
    print("response1 : ", response1.json())
    print("response2 : ", response2.json())
    assert response1.status_code == status.HTTP_201_CREATED
    assert response2.status_code == status.HTTP_201_CREATED

    obj_id = response2.json()["id"]  # ID du second objet

    # Tenter de mettre à jour `obj2` avec les valeurs de `obj1`
    response3 = api_client.patch(f"{url}{obj_id}/", valid_data1, format="json")
    print("response3 : ", response3.json())
    print("response3 : ", response3)
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
    print("valid_data : ", valid_data)
    response = api_client.post(url, valid_data, format="json")
    print("json response : ", response.json())
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()[field_name] == normalize_case(raw_value)

def validate_optional_field_value_db(model, field_name, **valid_data):
    """
    Vérifie qu'un champ optionnel peut être `""` ou `None` en base de données.

    - `model` → Le modèle Django à tester.
    - `field_name` → Le champ à tester.
    - `valid_data` → Autres champs obligatoires pour créer l'objet.
    """
    for value in ["", None]:  # Tester `""` et `None`
        valid_data[field_name] = value
        obj = model.objects.create(**valid_data)
        obj.refresh_from_db()
        assert getattr(obj, field_name) == (value if value is not None else ""), f"Erreur sur {field_name}: attendu `{value}`, obtenu `{getattr(obj, field_name)}`"

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
