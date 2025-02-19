import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

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

def validate_min_length(model, field_name, min_length, expected_error, **valid_data):
    """ Vérifie que le champ respecte une longueur minimale. """
    validate_constraint(model, field_name, "a" * (min_length - 1), expected_error, **valid_data)

def validate_unique_constraint(model, field_name, expected_error, **valid_data):
    """ Vérifie qu’un champ unique ne peut pas être dupliqué (unique=True). """
    instance = model.objects.create(**valid_data)
    # Modifier uniquement le champ testé pour forcer un doublon
    duplicate_data = valid_data.copy()
    duplicate_data[field_name] = getattr(instance, field_name)  # Même valeur
    with pytest.raises(IntegrityError, match=expected_error):
        model.objects.create(**duplicate_data)

def validate_unique_together(model, expected_error, **valid_data):
    """ Vérifie qu'une contrainte `unique_together` empêche la duplication. """
    model.objects.create(**valid_data) # Création de la première instance
    with pytest.raises(IntegrityError, match=expected_error): # Vérification que la deuxième tentative échoue avec une `IntegrityError`
        model.objects.create(**valid_data)

def validate_protected_delete(model, related_model, related_field, expected_error, **valid_data):
    """ Vérifie qu'une suppression est bloquée si `on_delete=PROTECT`. """
    obj = model.objects.create(**valid_data)
    related_obj = related_model.objects.create(**{related_field: obj})
    with pytest.raises(IntegrityError, match=expected_error):
        obj.delete()

def normalize_case(value):
    """ Applique la même normalisation (lowercase) que dans les modèles. """
    return " ".join(value.lower().strip().split()) if value else value




