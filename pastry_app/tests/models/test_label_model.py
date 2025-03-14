import pytest
from pastry_app.models import Label
from pastry_app.tests.utils import *
from pastry_app.constants import LABEL_NAME_CHOICES

# Définir model_name pour les tests de Label
model_name = "labels"

@pytest.fixture(params=LABEL_NAME_CHOICES)
def label(request):
    """Création d’un label avant chaque test (dynamique), parmi les choix disponibles de LABEL_NAME_CHOICES"""
    return Label.objects.create(label_name=request.param)

@pytest.mark.django_db
def test_label_creation(label):
    """ Vérifie que l'on peut créer un objet Label"""
    assert isinstance(label, Label)
    assert label.label_name == normalize_case(label.label_name)

@pytest.mark.django_db
def test_label_str_method(label):
    """ Vérifie que `__str__()` retourne bien le `label_name`"""
    assert str(label) == normalize_case(label.label_name)

@pytest.mark.django_db
def test_label_update(label):
    """ Vérifie que l'on peut modifier une Label"""
    # Sélectionner un label différent de `label`
    label_name = next((name for name in LABEL_NAME_CHOICES if name != label.label_name), None)
    if not label_name:
        pytest.skip("Pas assez de labels disponibles pour le test.")

    label.label_name = label_name
    label.save()
    label.refresh_from_db()
    assert label.label_name == normalize_case(label_name)

@pytest.mark.django_db
def test_label_deletion(label):
    """ Vérifie que l'on peut supprimer un Label"""
    label_id = label.id
    label.delete()
    assert not Label.objects.filter(id=label_id).exists()

@pytest.mark.parametrize("field_name", ["label_name"])
@pytest.mark.django_db
def test_required_fields_label(field_name):
    """ Vérifie que les champs obligatoires ne peuvent pas être vides """
    expected_error = ["field cannot be null", "This field cannot be blank."]
    for invalid_value in [None, "", "   "]:
        validate_constraint(Label, field_name, invalid_value, expected_error)

@pytest.mark.parametrize("field_names", [["label_name"]])
@pytest.mark.django_db
def test_unique_constraint_label(field_names, label):
    """Vérifie que deux Label ne peuvent pas avoir le même `label_name`."""
    # Construire `valid_data` avec TOUS les champs listés dans `field_names`
    valid_data = {field: getattr(label, field) for field in field_names}
    field_labels = [Label._meta.get_field(field).verbose_name.capitalize() for field in field_names] # Récupérer le verbose_name avec majuscule
    expected_error = f"Label with this {', '.join(field_labels)} already exists."
    validate_unique_together(Label, expected_error, **valid_data)
