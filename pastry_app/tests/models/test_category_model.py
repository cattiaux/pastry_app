import pytest
from pastry_app.models import Category
from pastry_app.tests.utils import *

# Définir model_name pour les tests de Category
model_name = "categories"

pytestmark = pytest.mark.django_db

@pytest.fixture()
def category():
    """Créer plusieurs catégories de test pour assurer la cohérence des tests."""
    Category.objects.create(category_name="Desserts", category_type="both")  # Ajout d'une autre catégorie
    Category.objects.create(category_name="Fruit à coque", category_type="ingredient")
    return Category.objects.get(category_name="fruit à coque")  # Retourne une catégorie pour le test

def test_category_creation(category):
    """ Vérifie que l'on peut créer un objet Category"""
    assert isinstance(category, Category)
    assert category.category_name == normalize_case(category.category_name)  # Vérifie la normalisation en minuscule

def test_category_str_method(category):
    """ Vérifie que `__str__()` retourne bien le `category_name`"""
    assert str(category) == f"{normalize_case(category.category_name)} [{normalize_case(category.category_type)}]"  # Vérifie que la méthode __str__ retourne le nom de la catégorie en minuscule

def test_category_update(category):
    """ Vérifie que `category_name` peut être modifié uniquement vers une nouvelle valeur et que `category_type` ne change pas automatiquement. """
    new_category_name = "Nouvelle Catégorie"
    old_category_type = category.category_type

    category.category_name = new_category_name
    category.save()
    category.refresh_from_db()
    assert category.category_name == normalize_case(new_category_name)
    assert category.category_type == old_category_type  # Vérification que `category_type` reste inchangé

    # Vérifier qu'on ne peut pas mettre à jour vers un `category_name` existant   
    category.category_name = "Desserts"
    with pytest.raises(ValidationError, match="Une catégorie avec ce nom existe déjà."):
        category.save()

    # Vérifier qu'on ne peut pas mettre un `category_type` invalide
    category.category_type = "invalid_value"
    with pytest.raises(ValidationError, match="`category_type` doit être l'une des valeurs suivantes: ingredient, recipe, both."):
        category.save()

def test_category_deletion(category):
    """ Vérifie que l'on peut supprimer une Category"""
    category_id = category.id
    category.delete()
    assert not Category.objects.filter(id=category_id).exists()

@pytest.mark.parametrize("field_name", ["category_name", "category_type"])
def test_required_fields_category(field_name, category):
    """ Vérifie que les champs obligatoires ne peuvent pas être vides """
    expected_error = ["field cannot be null", "This field cannot be blank."]
    for invalid_value in [None, "", "   "]:
        validate_constraint(Category, field_name, invalid_value, expected_error, category_type=category.category_type)

@pytest.mark.parametrize("field_name", ["category_name"])
def test_unique_constraint_category(field_name, category):
    """Vérifie que deux Category ne peuvent pas avoir le même `category_name`."""
    valid_data = {"category_name": category.category_name, "category_type": category.category_type}
    expected_error_1 = "Une catégorie avec ce nom existe déjà."
    expected_error_2 = "Category with this Category_name already exists."
    with pytest.raises(ValidationError) as exc_info:
        validate_unique_constraint(Category, field_name, expected_error_1, instance=category, **valid_data)
    # Vérifier que l'un des messages attendus est bien présent
    error_messages = str(exc_info.value)
    assert expected_error_1 in error_messages or expected_error_2 in error_messages

@pytest.mark.parametrize("invalid_category_type", ["invalid", "123"])
def test_category_type_must_be_valid_choice(invalid_category_type):
    """Vérifie qu'une erreur est levée si `category_type` contient une valeur non autorisée."""
    category = Category(category_name="TestCat", category_type=invalid_category_type)
    with pytest.raises(ValidationError, match="Value .* is not a valid choice."):
        category.full_clean()

def test_parent_category_is_optional(category):
    """Vérifie que `parent_category` est un champ optionnel en base de données."""
    # Vérifie que parent_category est bien NULL par défaut
    assert category.parent_category is None   
    
    # Vérifie que l'on peut attribuer une catégorie parente.
    parent_category = Category.objects.filter(category_name="desserts").first() # Récupère la catégorie "desserts" si elle existe en base
    assert parent_category is not None, "La catégorie 'desserts' n'existe pas en base."
    category.parent_category = parent_category  # lui donner une vraie valeur de Category existante en base
    category.save()
    category.refresh_from_db()
    assert category.parent_category == parent_category 

    # Vérifie qu'on peut détacher une sous-catégorie de son parent.
    category.parent_category = None
    category.save()
    category.refresh_from_db()
    assert category.parent_category is None  # Vérifie que la catégorie n’a plus de parent

def test_delete_category_with_subcategories_model():
    """Vérifie que la suppression d'une catégorie met bien à NULL ses sous-catégories en base de données."""
    parent = Category.objects.create(category_name="Parent", category_type="recipe")
    child = Category.objects.create(category_name="Child", category_type="recipe", parent_category=parent)
    
    assert child.parent_category == parent  # Vérifie que la relation parent -> enfant existe bien avant suppression
    parent.delete()  # Supprime la catégorie parente
    child.refresh_from_db()  # Recharge la sous-catégorie depuis la base
    assert child.parent_category is None  # Vérifie que `parent_category` est bien mis à NULL

@pytest.mark.parametrize(
    "parent_type,child_type,should_pass",
    [
        ("ingredient", "ingredient", True),
        ("ingredient", "recipe", False),
        ("ingredient", "both", False),
        ("recipe", "recipe", True),
        ("recipe", "ingredient", False),
        ("recipe", "both", False),
        ("both", "ingredient", True),
        ("both", "recipe", True),
        ("both", "both", True),
        ("none", "ingredient", True),
        ("none", "recipe", True),
        ("none", "both", True),
    ]
)
def test_category_parent_type_model(parent_type, child_type, should_pass):
    parent = None
    if parent_type != "none":
        parent = Category.objects.create(category_name=f"Parent {parent_type}", category_type=parent_type)
    child = Category(category_name=f"Child {child_type}", category_type=child_type, parent_category=parent)
    if should_pass:
        child.full_clean()
    else:
        with pytest.raises(ValidationError):
            child.full_clean()