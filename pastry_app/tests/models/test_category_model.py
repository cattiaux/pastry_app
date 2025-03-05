import pytest
from pastry_app.models import Category
from pastry_app.tests.utils import *

# Définir model_name pour les tests de Category
model_name = "categories"

@pytest.fixture()
def category():
    """Création d’une catégorie de test."""
    return Category.objects.create(category_name="Fruit à coque", category_type="ingredient")

@pytest.mark.django_db
def test_category_creation(category):
    """ Vérifie que l'on peut créer un objet Category"""
    assert isinstance(category, Category)
    assert category.category_name == normalize_case(category.category_name)  # Vérifie la normalisation en minuscule

@pytest.mark.django_db
def test_category_str_method(category):
    """ Vérifie que `__str__()` retourne bien le `category_name`"""
    assert str(category) == normalize_case(category.category_name)

@pytest.mark.django_db
def test_category_update(category):
    """ Vérifie que l'on peut modifier une Category et que `category_type` est recalculé si le nom change. """
    new_category_name = "Desserts"
    category.category_name = new_category_name
    category.save()
    category.refresh_from_db()
    assert category.category_name == normalize_case(new_category_name)
    assert category.category_type == "recipe"

    # Vérifier qu'un update vers un category_name inconnu nécessite aussi un category_type valide
    category.category_name = "Catégorie Inconnue"
    category.category_type = None  # On simule un oubli de category_type
    with pytest.raises(ValidationError, match="Le champ `category_type` est obligatoire et doit être spécifié à la création."):
        category.save()

@pytest.mark.django_db
def test_category_deletion(category):
    """ Vérifie que l'on peut supprimer une Category"""
    category_id = category.id
    category.delete()
    assert not Category.objects.filter(id=category_id).exists()

@pytest.mark.parametrize("field_name", ["category_name"])
@pytest.mark.django_db
def test_required_fields_category(field_name, category):
    """ Vérifie que les champs obligatoires ne peuvent pas être vides """
    expected_error = ["field cannot be null", "This field cannot be blank."]
    for invalid_value in [None, "", "   "]:
        validate_constraint(Category, field_name, invalid_value, expected_error, category_type=category.category_type)

@pytest.mark.django_db
def test_category_type_is_mandatory_on_creation():
    """Vérifie qu'une catégorie ne peut pas être créée sans `category_type`."""
    with pytest.raises(ValidationError, match="Le champ `category_type` est obligatoire et doit être spécifié à la création."):
        Category.objects.create(category_name="TestCat")  # Manque `category_type`

@pytest.mark.parametrize("field_name", ["category_name"])
@pytest.mark.django_db
def test_unique_constraint_category(field_name, category):
    """Vérifie que deux Category ne peuvent pas avoir le même `category_name`."""
    valid_data = {"catgory_name": category.category_name, "category_type": category.category_type}
    field_label = Category._meta.get_field(field_name).verbose_name.capitalize() # Récupérer le verbose_name avec majuscule
    expected_error = f"Category with this {field_label} already exists."
    validate_unique_constraint(Category, field_name, expected_error, **valid_data)

@pytest.mark.django_db
@pytest.mark.parametrize("invalid_category_type", ["invalid", "123", "", None])
def test_category_type_must_be_valid_choice(invalid_category_type):
    """Vérifie qu'une erreur est levée si `category_type` contient une valeur non autorisée."""
    with pytest.raises(ValidationError, match="is not a valid choice"):
        Category.objects.create(category_name="TestCat", category_type=invalid_category_type)

@pytest.mark.django_db
def test_parent_category_is_optional(category):
    """Vérifie que `parent_category` est un champ optionnel en base de données."""
    # Vérifie que parent_category est bien NULL par défaut
    assert category.parent_category is None   
    
    # Vérifie que l'on peut attribuer une catégorie parente.
    category["parent_category"] = "Fruits"  # lui donner une vraie valeur de Category existante en base
    category.save()
    category.refresh_from_db()
    assert category.parent_category == "fruits"  # Vérifie l'attribution correcte avec normalisation

    # Vérifie qu'on peut détacher une sous-catégorie de son parent.
    category.parent_category = None
    category.save()
    category.refresh_from_db()
    assert category.parent_category is None  # Vérifie que la catégorie n’a plus de parent

