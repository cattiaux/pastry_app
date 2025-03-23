import pytest
from django.core.exceptions import ValidationError
from math import isclose
from pastry_app.models import Pan
from pastry_app.tests.utils import *

model_name = "pans"

@pytest.mark.django_db
def test_create_roundpan_db():
    """ Vérifie la création d'un Pan de type ROUND avec volume calculé """
    pan = Pan.objects.create(pan_type="ROUND", diameter=16, height=5)
    assert pan.volume_cm3 is not None
    assert isclose(pan.volume_cm3, 1005.3, abs_tol=1)

@pytest.mark.django_db
def test_create_rectanglepan_db():
    """ Vérifie la création d'un Pan de type RECTANGLE avec volume calculé """
    pan = Pan.objects.create(pan_type="RECTANGLE", length=20, width=10, rect_height=4)
    assert pan.volume_cm3 == 800

@pytest.mark.django_db
def test_create_custom_pan_cm3_db():
    """ Vérifie la création d'un Pan de type CUSTOM avec volume saisi en cm3 """
    pan = Pan.objects.create(pan_type="CUSTOM", volume_raw=1000, unit="cm3")
    assert pan.volume_cm3 == 1000

@pytest.mark.django_db
def test_create_custom_pan_liters_db():
    """ Vérifie la conversion correcte du volume L → cm³ """
    pan = Pan.objects.create(pan_type="CUSTOM", volume_raw=1.4, unit="L")
    assert isclose(pan.volume_cm3, 1400, abs_tol=0.1)

@pytest.mark.django_db
def test_generate_default_name_round_db():
    """ Vérifie que pan_name est généré automatiquement si absent """
    pan = Pan.objects.create(pan_type="ROUND", diameter=18, height=4)
    assert pan.pan_name.startswith("cercle")
    assert "18x4" in pan.pan_name

@pytest.mark.django_db
def test_str_pan():
    """ Vérifie le rendu de la méthode __str__ """
    pan = Pan.objects.create(pan_type="RECTANGLE", length=20, width=10, rect_height=4)
    assert str(pan) == f"{pan.pan_name} (RECTANGLE)"

@pytest.mark.django_db
def test_brand_is_optional_and_normalized_db():
    """ Vérifie que la marque est optionnelle et normalisée """
    pan = Pan.objects.create(pan_type="CUSTOM", volume_raw=1000, unit="cm3", pan_brand="   Debuyer ")
    assert pan.pan_brand == normalize_case("Debuyer")

@pytest.mark.django_db
@pytest.mark.parametrize("invalid_type", ["circle", "SQUARE", "random", 123])
def test_invalid_pan_type_choices_db(invalid_type):
    """Vérifie qu’un `pan_type` invalide déclenche une ValidationError"""
    pan = Pan(pan_type=invalid_type, diameter=10, height=3)
    with pytest.raises(ValidationError, match="is not a valid choice"):
        pan.full_clean()

@pytest.mark.django_db
def test_pan_type_required_db():
    """Vérifie que `pan_type` est requis"""
    pan = Pan(diameter=16, height=5)
    with pytest.raises(ValidationError, match="type de moule.*requis"):
        pan.full_clean()

@pytest.mark.django_db
@pytest.mark.parametrize("pan_type, field_missing, expected_error", [
    ("ROUND", {"height": 5}, "diamètre"),
    ("ROUND", {"diameter": 16}, "hauteur"),
    ("RECTANGLE", {"width": 10, "rect_height": 4}, "longueur"),
    ("RECTANGLE", {"length": 20, "rect_height": 4}, "largeur"),
    ("RECTANGLE", {"length": 20, "width": 10}, "hauteur"),
    ("CUSTOM", {"unit": "cm3"}, "volume saisi"),
    ("CUSTOM", {"volume_raw": 500}, "unité du volume"),
])
def test_missing_required_fields_db(pan_type, field_missing, expected_error):
    """Vérifie que les champs obligatoires selon pan_type sont bien requis (logique clean())"""
    base_fields = {"pan_type": pan_type}
    base_fields.update(field_missing)
    pan = Pan(**base_fields)
    with pytest.raises(ValidationError, match=expected_error):
        pan.full_clean()

@pytest.mark.django_db
def test_delete_pan_db():
    """ Vérifie qu'on peut supprimer un moule """
    pan = Pan.objects.create(pan_type="CUSTOM", volume_raw=500, unit="cm3")
    pan_id = pan.id
    pan.delete()
    assert not Pan.objects.filter(id=pan_id).exists()

@pytest.mark.django_db
def test_pan_name_is_unique_db():
    """Vérifie que `pan_name` est unique, même après normalisation"""
    Pan.objects.create(pan_type="CUSTOM", volume_raw=1000, unit="cm3", pan_name="Mon Moule")
    with pytest.raises(ValidationError):
        pan2 = Pan(pan_type="CUSTOM", volume_raw=800, unit="cm3", pan_name="mon moule")  # casse différente
        pan2.full_clean()

@pytest.mark.django_db
@pytest.mark.parametrize("field_name", ["pan_name", "pan_brand"])
def test_min_length_fields_db(field_name):
    """Vérifie que `pan_name` et `pan_brand` doivent avoir au moins 2 caractères s’ils sont renseignés"""
    expected_errors = ["au moins 2 caractères", "at least 2 characters", "This field cannot be blank."]
    for short_value in ["", " ", "a"]:
        validate_constraint(Pan, field_name, short_value, expected_errors, pan_type="CUSTOM", volume_raw=1000, unit="cm3")

@pytest.mark.django_db
@pytest.mark.parametrize("pan_type, extra_fields, expected_error", [
    ("ROUND", {"volume_raw": 1000}, "ne doit pas contenir de.*volume"),
    ("ROUND", {"length": 10}, "rectangulaires"),
    ("RECTANGLE", {"diameter": 10}, "ne doit pas contenir de.*rondes"),
    ("RECTANGLE", {"volume_raw": 500}, "volume personnalisé"),
    ("CUSTOM", {"diameter": 16}, "ne doit pas contenir de dimensions"),
    ("CUSTOM", {"length": 20}, "ne doit pas contenir de dimensions"),
])
def test_pan_type_exclusive_fields_model(pan_type, extra_fields, expected_error):
    """Vérifie qu’un Pan ne peut pas avoir des champs d'autres types (validation clean)"""
    base_fields = {"ROUND": {"diameter": 16, "height": 5}, 
                   "RECTANGLE": {"length": 10, "width": 5, "rect_height": 3}, 
                   "CUSTOM": {"volume_raw": 1000, "unit": "cm3"}
                   }[pan_type].copy()
    base_fields.update(extra_fields)
    pan = Pan(pan_type=pan_type, **base_fields)
    with pytest.raises(ValidationError, match=expected_error):
        pan.full_clean()

@pytest.mark.django_db
@pytest.mark.parametrize("value", [0, -1])
def test_number_of_pans_must_be_positive(value):
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        pan = Pan(pan_type="CUSTOM",volume_raw=1000, unit="cm3", number_of_pans=value)
        pan.full_clean()

@pytest.mark.django_db
def test_default_number_of_pans():
    pan = Pan.objects.create(pan_type="CUSTOM", volume_raw=800, unit="cm3")
    assert pan.number_of_pans == 1