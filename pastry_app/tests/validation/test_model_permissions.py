import pytest
from rest_framework import status
from pastry_app.tests.base_api_test import api_client, base_url
from django.contrib.auth import get_user_model
from pastry_app.models import Recipe, Ingredient, RecipeStep, RecipeIngredient, Pan, Store
from pastry_app.tests.utils import normalize_case

User = get_user_model()

def base_recipe_data(**overrides):
    """Données minimales valides pour créer une recette (avec au moins un ingrédient)."""
    ingredient = Ingredient.objects.get_or_create(ingredient_name="Pommes")[0]
    data = {
        "recipe_name": "Test Recette",
        "chef_name": "Test Chef",
        "recipe_type": "BASE",
        "servings_min": 2,
        "servings_max": 4,
        "steps": [{"step_number": 1, "instruction": "Test step"}],
        "ingredients": [{"ingredient": ingredient.pk, "quantity": 300, "unit": "g"}],
        "pan_quantity": 1,
        "visibility": "private",
    }
    data.update(overrides)
    return data

def create_instance_with_related(model_cls, data):
    """Crée un objet avec gestion spéciale pour Recipe (steps, ingredients)."""
    if model_cls.__name__ == "Recipe":
        steps = data.pop("steps", [])
        ingredients = data.pop("ingredients", [])
        obj = model_cls.objects.create(**data)
        for step in steps:
            RecipeStep.objects.create(recipe=obj, **step)
        for ing in ingredients:
            # Gestion intelligente : accepter ingredient pk ou instance
            ingredient_obj = ing["ingredient"]
            if not isinstance(ingredient_obj, Ingredient):
                ingredient_obj = Ingredient.objects.get(pk=ingredient_obj)
            RecipeIngredient.objects.create(recipe=obj, ingredient=ingredient_obj,
                                            quantity=ing["quantity"], unit=ing["unit"])
        return obj
    else:
        return model_cls.objects.create(**data)
    
@pytest.mark.parametrize("model_name, base_data_func, name_field, model_cls", [
    ("recipes", base_recipe_data, "recipe_name", Recipe),
    ("ingredients", lambda **over: {"ingredient_name": "Vanille", "visibility": "private", "is_default": False, **over}, "ingredient_name", Ingredient),
    ("stores", lambda **over: {"store_name": "Monoprix", "city": "Paris", "zip_code": "75001", "visibility": "private", "is_default": False, **over}, "store_name", Store),
    ("pans", lambda **over: {"pan_name": "Cercle 18cm", "pan_type": "ROUND", "diameter": 18, "height": 4, "units_in_mold": 1, "visibility": "private", "is_default": False, **over}, "pan_name", Pan),
])
@pytest.mark.django_db
class TestGenericPermissions:
    @pytest.fixture
    def guest_id(self):
        return "test-guest-id-123"

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="user1", password="testpass123")

    @pytest.fixture
    def other_user(self):
        return User.objects.create_user(username="user2", password="testpass456")
    
    # --- TESTS GUEST (invité) ---

    def test_guest_can_create_object(self, api_client, base_url, model_name, base_data_func, guest_id, name_field, model_cls):
        url = base_url(model_name)
        data = base_data_func()
        response = api_client.post(url, data, format="json", HTTP_X_GUEST_ID=guest_id)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["guest_id"] == guest_id
        assert response.json()["user"] is None

    def test_guest_can_modify_own_object(self, api_client, base_url, model_name, base_data_func, guest_id, name_field, model_cls):
        url = base_url(model_name)
        # Création
        response = api_client.post(url, base_data_func(), format="json", HTTP_X_GUEST_ID=guest_id)
        obj_id = response.json()["id"]
        patch_url = f"{url}{obj_id}/"
        # Modification par le même guest_id
        response2 = api_client.patch(patch_url, {"visibility": "public"}, format="json", HTTP_X_GUEST_ID=guest_id)
        assert response2.status_code == 200
        assert response2.json()["visibility"] == "public"

    def test_guest_cannot_modify_others_object(self, api_client, base_url, model_name, base_data_func, guest_id, name_field, model_cls):
        url = base_url(model_name)
        # Création (invité A)
        response = api_client.post(url, base_data_func(), format="json", HTTP_X_GUEST_ID=guest_id)
        obj_id = response.json()["id"]
        patch_url = f"{url}{obj_id}/"
        # Tentative (invité B)
        response2 = api_client.patch(patch_url, {"visibility": "public"}, format="json", HTTP_X_GUEST_ID="other-guest")
        # En cas de tentative de modification d'une recette appartenant à un autre guest,
        # DRF retourne "404 Not Found" (sécurité : ne pas révéler l'existence de la ressource).
        assert response2.status_code in [403, 404]

    def test_guest_can_delete_own_object(self, api_client, base_url, model_name, base_data_func, guest_id, name_field, model_cls):
        """ Vérifie qu'un invité peut supprimer son propre objet (recette, ingrédient, pan, store...). """
        url = base_url(model_name)
        response = api_client.post(url, base_data_func(), format="json", HTTP_X_GUEST_ID=guest_id)
        obj_id = response.json()["id"]
        del_url = f"{url}{obj_id}/"
        response2 = api_client.delete(del_url, HTTP_X_GUEST_ID=guest_id)
        assert response2.status_code in [204, 200, 202]

    def test_guest_cannot_delete_others_object(self, api_client, base_url, model_name, base_data_func, guest_id, name_field, model_cls):
        url = base_url(model_name)
        response = api_client.post(url, base_data_func(), format="json", HTTP_X_GUEST_ID=guest_id)
        obj_id = response.json()["id"]
        del_url = f"{url}{obj_id}/"
        response2 = api_client.delete(del_url, HTTP_X_GUEST_ID="other-guest")
        # En cas de tentative de modification d'une recette appartenant à un autre guest,
        # DRF retourne "404 Not Found" (sécurité : ne pas révéler l'existence de la ressource).
        assert response2.status_code in [403, 404]

    def test_guest_sees_public_and_default_objects(self, api_client, base_url, user, model_name, base_data_func, name_field, model_cls):
        url = base_url(model_name)
        # Crée un objet public et un privé via user
        api_client.force_authenticate(user=user)
        api_client.post(url, base_data_func(**{name_field: "Publique", "visibility": "public"}), format="json")
        api_client.post(url, base_data_func(**{name_field: "Privée", "visibility": "private"}), format="json")
        # Crée un objet de base (is_default)
        create_instance_with_related(model_cls, base_data_func(**{name_field: "Base", "visibility": "public", "is_default": True}))
        api_client.force_authenticate(user=None)
        # L'invité consulte la liste
        response = api_client.get(url)
        names = [normalize_case(r[name_field]) for r in response.json()]
        assert normalize_case("Publique") in names
        assert normalize_case("Base") in names
        assert normalize_case("Privée") not in names

    def test_guest_does_not_see_private_user_objects(self, api_client, base_url, user, model_name, base_data_func, name_field, model_cls):
        url = base_url(model_name)
        api_client.force_authenticate(user=user)
        api_client.post(url, base_data_func(**{name_field: "PriveeUser", "visibility": "private"}), format="json")
        api_client.force_authenticate(user=None)
        response = api_client.get(url)
        names = [normalize_case(r[name_field]) for r in response.json()]
        assert normalize_case("PriveeUser") not in names

    # --- TESTS USER AUTH ---

    def test_user_can_create_object(self, api_client, base_url, user, model_name, base_data_func, name_field, model_cls):
        url = base_url(model_name)
        api_client.force_authenticate(user=user)
        response = api_client.post(url, base_data_func(), format="json")
        assert response.status_code == 201
        assert response.json()["user"] == user.id
        assert response.json()["guest_id"] is None

    def test_user_can_modify_own_object(self, api_client, base_url, user, model_name, base_data_func, name_field, model_cls):
        """ Vérifie qu'un utilisateur authentifié peut modifier son propre objet (recette, ingrédient, pan, store...). """
        url = base_url(model_name)
        api_client.force_authenticate(user=user)
        obj_id = api_client.post(url, base_data_func(), format="json").json()["id"]
        patch_url = f"{url}{obj_id}/"
        response = api_client.patch(patch_url, {name_field: "New Name"}, format="json")
        assert response.status_code == 200
        assert response.json()[name_field] == normalize_case("New Name")

    def test_user_cannot_modify_others_object(self, api_client, base_url, model_name, base_data_func, user, other_user, name_field, model_cls):
        url = base_url(model_name)
        api_client.force_authenticate(user=user)
        obj_id = api_client.post(url, base_data_func(), format="json").json()["id"]
        patch_url = f"{url}{obj_id}/"
        api_client.force_authenticate(user=other_user)
        response = api_client.patch(patch_url, {name_field: "Hack"}, format="json")
        # En cas de tentative de modification d'une recette appartenant à un autre guest,
        # DRF retourne "404 Not Found" (sécurité : ne pas révéler l'existence de la ressource).
        assert response.status_code in [403, 404]

    def test_user_can_delete_own_object(self, api_client, base_url, model_name, base_data_func, user, name_field, model_cls):
        url = base_url(model_name)
        api_client.force_authenticate(user=user)
        obj_id = api_client.post(url, base_data_func(), format="json").json()["id"]
        del_url = f"{url}{obj_id}/"
        response = api_client.delete(del_url)
        assert response.status_code in [204, 200, 202]

    def test_user_cannot_delete_others_object(self, api_client, base_url, model_name, base_data_func, user, other_user, name_field, model_cls):
        url = base_url(model_name)
        api_client.force_authenticate(user=user)
        obj_id = api_client.post(url, base_data_func(), format="json").json()["id"]
        del_url = f"{url}{obj_id}/"
        api_client.force_authenticate(user=other_user)
        response = api_client.delete(del_url)
        # En cas de tentative de modification d'une recette appartenant à un autre guest,
        # DRF retourne "404 Not Found" (sécurité : ne pas révéler l'existence de la ressource).
        assert response.status_code in [403, 404]

    def test_user_sees_public_and_default_and_own_objects(self, api_client, base_url, model_name, base_data_func, user, other_user, name_field, model_cls):
        url = base_url(model_name)
        # User crée une publique et une privée
        api_client.force_authenticate(user=user)
        api_client.post(url, base_data_func(**{name_field: "PubliqueU", "visibility": "public"}), format="json")
        api_client.post(url, base_data_func(**{name_field: "PriveeU", "visibility": "private"}), format="json")
        # Other user crée une privée
        api_client.force_authenticate(user=other_user)
        api_client.post(url, base_data_func(**{name_field: "PriveeOther", "visibility": "private"}), format="json")
        # Objet de base (is_default)
        create_instance_with_related(model_cls, base_data_func(**{name_field: "DefautU", "visibility": "public", "is_default": True}))
        # User consulte
        api_client.force_authenticate(user=user)
        response = api_client.get(url)
        names = [r[name_field] for r in response.json()]
        assert normalize_case("PubliqueU") in names
        assert normalize_case("PriveeU") in names
        assert normalize_case("DefautU") in names
        assert normalize_case("PriveeOther") not in names

    def test_user_does_not_see_private_others_objects(self, api_client, base_url, model_name, user, other_user, name_field, model_cls):
        url = base_url(model_name)
        api_client.force_authenticate(user=other_user)
        api_client.post(url, base_recipe_data(recipe_name="PriveeOther", visibility="private"), format="json")
        api_client.force_authenticate(user=user)
        response = api_client.get(url)
        names = [r[name_field] for r in response.json()]
        assert normalize_case("PriveeOther") not in names

    def test_user_does_not_see_private_others_objects(self, api_client, base_url, model_name, base_data_func, user, other_user, name_field, model_cls):
        url = base_url(model_name)
        api_client.force_authenticate(user=other_user)
        api_client.post(url, base_data_func(**{name_field: "PriveeOther", "visibility": "private"}), format="json")
        api_client.force_authenticate(user=user)
        response = api_client.get(url)
        names = [r[name_field] for r in response.json()]
        assert normalize_case("PriveeOther") not in names

    # --- TESTS RECETTES DE BASE (is_default) ---

    @pytest.fixture
    def default_object(db, model_cls, name_field, base_data_func):
        """
        Crée un objet "de base" (is_default=True), compatible avec Recipe et tous les autres modèles.
        - Pour Recipe : ajoute steps et ingredients à part.
        """
        data = base_data_func(**{name_field: "ObjetBase", "visibility": "public", "is_default": True})

        # Pour Recipe, gère steps et ingredients séparément
        if model_cls.__name__ == "Recipe":
            steps = data.pop("steps", [])
            ingredients = data.pop("ingredients", [])
            obj = model_cls.objects.create(**data)
            for step in steps:
                RecipeStep.objects.create(recipe=obj, **step)
            for ing in ingredients:
                # Convertit le PK en instance
                ingredient_id = ing["ingredient"]
                ingredient_instance = Ingredient.objects.get(pk=ingredient_id)
                data_ing = dict(ing)
                data_ing["ingredient"] = ingredient_instance
                RecipeIngredient.objects.create(recipe=obj, **data_ing)
            return obj

        # Pour tous les autres modèles, création simple
        return model_cls.objects.create(**data)

    def test_default_object_is_readonly(self, api_client, base_url, model_name, default_object, user, name_field, model_cls):
        url = base_url(model_name) + f"{default_object.id}/"
        # Invité : interdit
        response = api_client.patch(url, {name_field: "NOPE"})
        assert response.status_code == 403
        # Utilisateur connecté : interdit aussi
        api_client.force_authenticate(user=user)
        response2 = api_client.patch(url, {name_field: "NOPE2"})
        assert response2.status_code == 403
        # DELETE interdit
        response3 = api_client.delete(url)
        assert response3.status_code == 403

    def test_default_object_is_visible(self, api_client, base_url, model_name, default_object, name_field, model_cls):
        url = base_url(model_name)
        response = api_client.get(url)
        assert any(r[name_field] == normalize_case("ObjetBase") for r in response.json())

    # --- TESTS VISIBILITY ---

    def test_guest_can_create_public_object(self, api_client, base_url, model_name, base_data_func, guest_id, name_field, model_cls):
        url = base_url(model_name)
        data = base_data_func(visibility="public")
        response = api_client.post(url, data, format="json", HTTP_X_GUEST_ID=guest_id)
        assert response.status_code == 201
        assert response.json()["visibility"] == "public"
        assert normalize_case(base_data_func(visibility="public")[name_field]) == normalize_case(response.json()[name_field])

    def test_user_can_create_public_object(self, api_client, base_url, model_name, base_data_func, user, name_field, model_cls):
        url = base_url(model_name)
        data = base_data_func(visibility="public")
        api_client.force_authenticate(user=user)
        response = api_client.post(url, data, format="json")
        assert response.status_code == 201
        assert response.json()["visibility"] == "public"
        assert normalize_case(data[name_field]) == normalize_case(response.json()[name_field])
