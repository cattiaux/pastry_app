from pastry_app.models import Label
from rest_framework import status
from django.core.exceptions import ValidationError
import pytest, json
from pastry_app.tests.base_api_test import api_client, base_url
from pastry_app.tests.utils import normalize_case
from pastry_app.constants import LABEL_NAME_CHOICES, LABEL_DEFINITIONS

# Définir model_name pour les tests de Label
model_name = "labels"

@pytest.mark.django_db
def test_create_label_without_name(api_client, base_url):
    """Vérifie qu'on ne peut PAS créer un Label sans `label_name` via l'API"""
    url = base_url(model_name)
    response = api_client.post(url, {})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "label_name" in response.json()

@pytest.mark.django_db
def test_create_duplicate_label(api_client, base_url):
    """Vérifie qu'on ne peut PAS créer deux Labels avec le même `label_name` via l'API, peu importe la casse"""
    url = base_url(model_name)

    # Création du premier label via l'API
    response1 = api_client.post(url, data=json.dumps({"label_name": LABEL_NAME_CHOICES[0]}), content_type="application/json")
    assert response1.status_code == status.HTTP_201_CREATED  # Vérifie que la première création réussit

    # Essayer de créer un deuxième label avec le même nom via l'API (avec la même casse ou différente)
    response2 = api_client.post(url, data=json.dumps({"label_name": normalize_case(LABEL_NAME_CHOICES[0])}), content_type="application/json")

    # Vérifier que l'API refuse le doublon avec un code 400
    assert response2.status_code == status.HTTP_400_BAD_REQUEST
    assert "label_name" in response2.json()

@pytest.mark.django_db
def test_create_label_invalid_name(api_client, base_url):
    """ Vérifie qu'on ne peut PAS créer un Label avec un `label_name` invalide """
    url = base_url(model_name)

    response = api_client.post(url, data={"label_name": "azerty"})  # "azerty" n'est pas dans `LABEL_NAME_CHOICES`
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "label_name" in response.json()  # Vérifie que l'API bloque bien

@pytest.mark.django_db
def test_label_name_cannot_be_empty():
    """Vérifie qu'on ne peut pas créer un label avec un nom vide."""
    with pytest.raises(ValidationError):
        label = Label(label_name="")
        label.full_clean()

@pytest.mark.django_db
def test_label_name_is_normalized():
    """Vérifie que le `label_name` est bien normalisé (minuscule, sans espaces inutiles)."""
    label = Label.objects.create(label_name=f"  {LABEL_NAME_CHOICES[0].upper()}  ")
    assert label.label_name == LABEL_NAME_CHOICES[0]

# 🔴 Attention : Ce test d'unicité (test_update_label_to_duplicate) fonctionnent UNIQUEMENT si `unique=True` est retiré du modèle.
# Si `unique=True`, Django bloque la validation AVANT que l'API ne réponde -> `IntegrityError`
# Solution recommandée :
# 1️. Tester l'unicité dans l'API avec `validate_label_name()` dans `serializers.py` (sans `unique=True`).
# 2️. En production, remettre `unique=True` dans `models.py` pour sécuriser la base, mais NE PAS tester cela avec pytest.
# Si ces tests échouent avec `unique=True`, c'est normal et tu peux ignorer l'erreur !
@pytest.mark.django_db
def test_update_label_to_duplicate(api_client, base_url):
    """Vérifie qu'on ne peut PAS modifier un Label pour lui donner un `label_name` déjà existant"""
    url = base_url(model_name)

    # Sélectionner deux labels distincts dynamiquement
    label_names = LABEL_NAME_CHOICES[:2]  # Prend les deux premiers labels disponibles
    if len(label_names) < 2:
        pytest.skip("Pas assez de labels disponibles pour ce test.")

    label1, label2 = label_names  # Assigne deux labels différents

    # Créer deux labels différents
    response1 = api_client.post(url, {"label_name": label1})
    response2 = api_client.post(url, {"label_name": label2})

    assert response1.status_code == status.HTTP_201_CREATED
    assert response2.status_code == status.HTTP_201_CREATED
    # Vérification que la réponse contient bien l'ID
    label_id = response2.json()["id"]

    # Essayer de renommer "Viennoiseries" en "Desserts"
    response3 = api_client.patch(f"{url}{label_id}/", {"label_name": label1})

    # Vérifier que l'API refuse la modification
    assert response3.status_code == status.HTTP_400_BAD_REQUEST
    assert "label_name" in response3.json()

def test_label_type_choices():
    """Vérifie que les choix pour `label_type` sont correctement définis à partir de LABEL_DEFINITIONS."""
    valid_types = {c_type for _, _, c_type in LABEL_DEFINITIONS}  # Récupère les types uniques
    assert "ingredient" in valid_types
    assert "recipe" in valid_types
    assert "both" in valid_types