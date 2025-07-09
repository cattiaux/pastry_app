import pytest
from pastry_app.models import Label
from pastry_app.tests.utils import *

# Définir model_name pour les tests de Label
model_name = "labels"

pytestmark = pytest.mark.django_db

@pytest.fixture()
def label():
    """Créer plusieurs labels de test pour assurer la cohérence des tests."""
    Label.objects.create(label_name="Bio", label_type="recipe")  # Ajout d'un autre label
    Label.objects.create(label_name="Label Rouge", label_type="ingredient")
    return Label.objects.get(label_name="bio")  # Retourne un label pour le test

def test_label_creation(label):
    """ Vérifie que l'on peut créer un objet Label"""
    assert isinstance(label, Label)
    assert label.label_name == normalize_case(label.label_name)  # Vérifie la normalisation en minuscule

def test_label_str_method(label):
    """ Vérifie que `__str__()` retourne bien le `label_name`"""
    assert str(label) == f"{normalize_case(label.label_name)} [{normalize_case(label.label_type)}]"  # Vérifie que la méthode __str__ retourne le nom du label en minuscule

def test_label_update(label):
    """ Vérifie que `label_name` peut être modifié uniquement vers une nouvelle valeur et que `label_type` ne change pas automatiquement. """
    new_label_name = "Nouveau Label"
    old_label_type = label.label_type

    label.label_name = new_label_name
    label.save()
    label.refresh_from_db()
    assert label.label_name == normalize_case(new_label_name)
    assert label.label_type == old_label_type  # Vérification que `label_type` reste inchangé

    # Vérifier qu'on ne peut pas mettre à jour vers un `label_name` existant   
    label.label_name = "Label Rouge"
    with pytest.raises(ValidationError, match="Un label avec ce nom existe déjà."):
        label.save()

    # Vérifier qu'on ne peut pas mettre un `label_type` invalide
    label.label_type = "invalid_value"
    with pytest.raises(ValidationError, match="`label_type` doit être l'une des valeurs suivantes: ingredient, recipe, both."):
        label.save()

def test_label_deletion(label):
    """ Vérifie que l'on peut supprimer un Label"""
    label_id = label.id
    label.delete()
    assert not Label.objects.filter(id=label_id).exists()

@pytest.mark.parametrize("field_name", ["label_name", "label_type"])
def test_required_fields_label(field_name, label):
    """ Vérifie que les champs obligatoires ne peuvent pas être vides """
    expected_error = ["field cannot be null", "This field cannot be blank."]
    for invalid_value in [None, "", "   "]:
        validate_constraint(Label, field_name, invalid_value, expected_error, label_type=label.label_type)

@pytest.mark.parametrize("field_name", ["label_name"])
def test_unique_constraint_label(field_name, label):
    """Vérifie que deux Label ne peuvent pas avoir le même `label_name`."""
    valid_data = {"label_name": label.label_name, "label_type": label.label_type}
    expected_error_1 = "Un label avec ce nom existe déjà."
    expected_error_2 = "label with this label_name already exists."
    with pytest.raises(ValidationError) as exc_info:
        validate_unique_constraint(Label, field_name, expected_error_1, instance=label, **valid_data)
    # Vérifier que l'un des messages attendus est bien présent
    error_messages = str(exc_info.value)
    assert expected_error_1 in error_messages or expected_error_2 in error_messages

@pytest.mark.parametrize("invalid_label_type", ["invalid", "123"])
def test_label_type_must_be_valid_choice(invalid_label_type):
    """Vérifie qu'une erreur est levée si `label_type` contient une valeur non autorisée."""
    label = Label(label_name="TestLabel", label_type=invalid_label_type)
    with pytest.raises(ValidationError, match="Value .* is not a valid choice."):
        label.full_clean()


