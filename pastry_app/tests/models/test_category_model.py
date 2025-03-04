import pytest
from pastry_app.models import Category
from pastry_app.constants import CATEGORY_NAME_CHOICES
from pastry_app.tests.utils import *

# Définir model_name pour les tests de Category
model_name = "categories"

@pytest.fixture(params=CATEGORY_NAME_CHOICES)
def category(request):
    """Création d’une catégorie avant chaque test (dynamique), parmi les choix disponibles de CATEGORY_NAME_CHOICES"""
    return Category.objects.create(category_name=request.param)

@pytest.mark.django_db
def test_category_creation(category):
    """ Vérifie que l'on peut créer un objet Category"""
    assert isinstance(category, Category)
    assert category.category_name == normalize_case(category.category_name)

@pytest.mark.django_db
def test_category_str_method(category):
    """ Vérifie que `__str__()` retourne bien le `category_name`"""
    assert str(category) == normalize_case(category.category_name)

@pytest.mark.django_db
def test_category_update(category):
    """ Vérifie que l'on peut modifier une Category"""
    # Sélectionner une catégorie différente de `setup_category`
    category_name = next((name for name in CATEGORY_NAME_CHOICES if name != category.category_name), None)
    if not category_name:
        pytest.skip("Pas assez de catégories disponibles pour le test.")

    category.category_name = category_name
    category.save()
    category.refresh_from_db()
    assert category.category_name == normalize_case(category_name)

@pytest.mark.django_db
def test_category_deletion(category):
    """ Vérifie que l'on peut supprimer une Category"""
    category_id = category.id
    category.delete()
    assert not Category.objects.filter(id=category_id).exists()

@pytest.mark.parametrize("field_name", ["category_name"])
@pytest.mark.django_db
def test_required_fields_category(field_name):
    """ Vérifie que les champs obligatoires ne peuvent pas être vides """
    expected_error = ["field cannot be null", "This field cannot be blank."]
    for invalid_value in [None, "", "   "]:
        validate_constraint(Category, field_name, invalid_value, expected_error)

@pytest.mark.parametrize("field_names", [["category_name"]])
@pytest.mark.django_db
def test_unique_constraint_category(field_names, category):
    """Vérifie que deux Category ne peuvent pas avoir le même `category_name`."""
    # Construire `valid_data` avec TOUS les champs listés dans `field_names`
    valid_data = {field: getattr(category, field) for field in field_names}
    field_labels = [Category._meta.get_field(field).verbose_name.capitalize() for field in field_names] # Récupérer le verbose_name avec majuscule
    expected_error = f"Category with this {', '.join(field_labels)} already exists."
    validate_unique_together(Category, expected_error, **valid_data)

@pytest.mark.django_db
def test_category_parent_category_is_optional(category):
    """Vérifie que `parent_category` est un champ optionnel en base de données."""
    # Sélectionner un category_name différent de celui utilisé par la fixture
    category_name = next(name for name in CATEGORY_NAME_CHOICES if name != category.category_name)
    # Création d'une catégorie SANS parent_category
    category_without_parent = Category.objects.create(category_name=category_name)
    # Vérifie que parent_category est bien NULL par défaut
    assert category_without_parent.parent_category is None

