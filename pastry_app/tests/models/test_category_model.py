from pastry_app.models import Category
from pastry_app.tests.utils import normalize_case
import pytest
from pastry_app.constants import CATEGORY_NAME_CHOICES

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
