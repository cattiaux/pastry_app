from django.test import TestCase
from pastry_app.models import Ingredient, IngredientPrice
from pastry_app.tests.utils import normalize_case

class IngredientPriceModelTest(TestCase):
    """Tests unitaires du modèle IngredientPrice"""

    def setUp(self):
        """Création d’un ingrédient et d’un prix pour tester le modèle"""
        self.ingredient = Ingredient.objects.create(ingredient_name="Farine")
        self.ingredient_price = IngredientPrice.objects.create(
            ingredient=self.ingredient, store="Supermarché A", price=2.5
        )

    def test_ingredient_price_creation(self):
        """ Vérifie que l'on peut créer un objet IngredientPrice"""
        self.assertIsInstance(self.ingredient_price, IngredientPrice)
        self.assertEqual(self.ingredient_price.ingredient, self.ingredient)
        self.assertEqual(self.ingredient_price.store, normalize_case("Supermarché A"))
        self.assertEqual(self.ingredient_price.price, 2.5)

    def test_ingredient_price_str_method(self):
        """ Vérifie que `__str__()` retourne bien `Ingrédient - Magasin - Prix`"""
        expected_str = f"Farine - Supermarché A - 2.5€"
        self.assertEqual(str(self.ingredient_price), expected_str)

    def test_ingredient_price_update(self):
        """ Vérifie que l'on peut modifier un IngredientPrice"""
        self.ingredient_price.price = 3.0
        self.ingredient_price.save()
        self.ingredient_price.refresh_from_db()
        self.assertEqual(self.ingredient_price.price, 3.0)

    def test_ingredient_price_deletion(self):
        """ Vérifie que l'on peut supprimer un IngredientPrice"""
        ingredient_price_id = self.ingredient_price.id
        self.ingredient_price.delete()
        self.assertFalse(IngredientPrice.objects.filter(id=ingredient_price_id).exists())
