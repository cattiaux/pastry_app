# views.py
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.utils import IntegrityError 
from django.db.models import ProtectedError
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from .tests.utils import normalize_case
from .utils import (servings_to_volume, get_suggested_pans, adapt_recipe_pan_to_pan, adapt_recipe_servings_to_volume, adapt_recipe_with_target_volume, 
                    adapt_recipe_servings_to_servings, estimate_servings_from_pan, suggest_pans_for_servings, adapt_recipe_by_ingredients_constraints)
from .models import *
from .serializers import *

class StoreViewSet(viewsets.ModelViewSet):
    """ API CRUD pour gérer les magasins. """
    queryset = Store.objects.all().order_by('store_name', 'city')
    serializer_class = StoreSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["city", "zip_code", "store_name"]
    search_fields = ["store_name", "city", "zip_code"]
    ordering_fields = ["store_name", "city", "zip_code"]
    ordering = ["store_name", "city"]

    def create(self, request, *args, **kwargs):
        """ Vérifie que le magasin n'existe pas avant de le créer. """
        store_name = normalize_case(request.data.get("store_name", ""))
        city = request.data.get("city")
        city = city.strip() if city else ""  # Si 'city' est None alors on transforme None en ""
        zip_code = request.data.get("zip_code")
        zip_code = zip_code.strip() if zip_code else ""  # Si 'zip_code' est None alors on transforme None en ""

        if Store.objects.filter(store_name=store_name, city=city, zip_code=zip_code).exists():
            return Response({"error": "Ce magasin existe déjà."}, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """ Empêche la suppression d'un magasin s'il est utilisé dans des prix. """
        store = self.get_object()
        if store.prices.exists():
            return Response(
                {"error": "Ce magasin est associé à des prix d'ingrédients et ne peut pas être supprimé."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)

class IngredientPriceViewSet(viewsets.ModelViewSet):
    """ API CRUD pour gérer les prix des ingrédients. """
    queryset = IngredientPrice.objects.all()
    serializer_class = IngredientPriceSerializer

    def create(self, request, *args, **kwargs):
        """ Vérifie l'existence de l'ingrédient, gère l'historique et crée un prix d'ingrédient. """
        ingredient_slug = request.data.get("ingredient")

        # Vérifier si l'ingrédient existe et récupérer son objet
        if ingredient_slug:
            try:
                ingredient = Ingredient.objects.get(ingredient_name=ingredient_slug)
                request.data["ingredient"] = ingredient.ingredient_name  # Assurer un slug et non un ID
            except Ingredient.DoesNotExist:
                return Response({"ingredient": ["Cet ingrédient n'existe pas."]}, status=status.HTTP_400_BAD_REQUEST)

        # Laisser DRF gérer la validation avec le serializer
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # Déclenche les erreurs standards DRF

        # Extraire les données validées après la validation
        validated_data = serializer.validated_data
        store = validated_data.get("store")
        brand_name = validated_data.get("brand_name", "")
        quantity = validated_data.get("quantity")
        unit = validated_data.get("unit")
        new_price = validated_data.get("price")
        new_is_promo = validated_data.get("is_promo", False)
        new_promo_end_date = validated_data.get("promotion_end_date")

        # Vérifier si un `IngredientPrice` existe déjà pour cet ingrédientPrice (combinaison unique)
        existing_price = IngredientPrice.objects.filter(ingredient=ingredient, store=store, brand_name=brand_name, 
                                                        quantity=quantity, unit=unit).first()

        if existing_price:  # L’objet existait déjà → Vérifier s’il faut l’archiver
            # Si le prix ou is_promo change, l'archivage est géré par `save()`
            if existing_price.price != new_price or existing_price.is_promo != new_is_promo:
                # Archiver l'ancien prix
                IngredientPriceHistory.objects.create(ingredient=existing_price.ingredient, store=existing_price.store, 
                                                      brand_name=existing_price.brand_name, quantity=existing_price.quantity, unit=existing_price.unit, date=existing_price.date, 
                                                      price=existing_price.price, is_promo=existing_price.is_promo, promotion_end_date=existing_price.promotion_end_date)
               
                # Supprimer l'ancien prix pour éviter `UniqueConstraint`
                existing_price.delete()  

                # Créer un nouveau IngredientPrice
                request.data["ingredient"] = ingredient.ingredient_name
                return super().create(request, *args, **kwargs)

            # Si seule la `promotion_end_date` change, on met à jour directement
            elif existing_price.promotion_end_date != new_promo_end_date:
                existing_price.promotion_end_date = new_promo_end_date
                existing_price.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            
            else:
                return Response({"non_field_errors": ["Un prix identique existe déjà."]}, status=status.HTTP_400_BAD_REQUEST)
            
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """ Désactive la mise à jour des prix pour conserver l'historique. """
        return Response({"error": "La mise à jour des prix est interdite. Créez un nouvel enregistrement."},
                        status=status.HTTP_405_METHOD_NOT_ALLOWED)

class IngredientPriceHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ API en lecture seule pour l'historique des prix d'ingrédients. """
    queryset = IngredientPriceHistory.objects.all()
    serializer_class = IngredientPriceHistorySerializer
    filter_backends = [SearchFilter]
    search_fields = ["ingredient__ingredient_name"]
    
class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()\
        .prefetch_related("categories", "labels", "recipe_ingredients", "steps", "main_recipes")\
        .select_related("pan", "parent_recipe")\
        .order_by("recipe_name", "chef_name")
    serializer_class = RecipeSerializer
    permission_classes = [AllowAny]

    filter_backends = [SearchFilter, DjangoFilterBackend, OrderingFilter]
    search_fields = ["recipe_name", "chef_name", "context_name"]
    filterset_fields = ["recipe_type", "chef_name", "categories", "labels", "pan"]
    ordering_fields = ["recipe_name", "chef_name", "recipe_type", "created_at"]
    ordering = ["recipe_name", "chef_name"]

    def destroy(self, request, *args, **kwargs):
        """ Empêche la suppression d'une recette utilisée comme sous-recette """
        instance = self.get_object()
        try:
            instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response({"error": "Cannot delete this recipe because it is used in another recipe."}, status=status.HTTP_400_BAD_REQUEST)

class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all().order_by('ingredient_name')
    serializer_class = IngredientSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["categories", "labels"]
    search_fields = ["ingredient_name"]
    ordering_fields = ["ingredient_name"]
    ordering = ["ingredient_name"]

    def create(self, request, *args, **kwargs):
        """ Normaliser le nom de l'ingrédient et empêcher les doublons """
        data = request.data.copy()  # On crée une copie modifiable de request.data
        ingredient_name = normalize_case(data.get("ingredient_name", ""))

        # Vérifier si l'ingrédient existe déjà AVANT toute validation
        if Ingredient.objects.filter(ingredient_name__iexact=ingredient_name).exists():
            return Response({"ingredient_name": "Cet ingrédient existe déjà."}, status=status.HTTP_400_BAD_REQUEST)

        # Normalisation du nom de l'ingrédient
        data["ingredient_name"] = normalize_case(ingredient_name)

        # Création de l'ingrédient avec le serializer
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
    
        try:
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except IntegrityError:  # Sécurité supplémentaire en cas de requête concurrente
            return Response({"error": "Erreur d'intégrité en base de données."}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """ Empêcher la suppression d'un ingrédient s'il est utilisé dans une recette """
        ingredient = self.get_object()
        try:
            self.perform_destroy(ingredient)
        except ProtectedError:
            return Response(
                {"error": "Cet ingrédient est utilisé dans une recette et ne peut pas être supprimé."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('category_name')
    serializer_class = CategorySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["category_name", "parent_category"]
    search_fields = ['category_name']
    ordering_fields = ["category_name", "parent_category"]
    ordering = ["category_name"]  # ordre par défaut
    permission_classes = []  # On définit les permissions dans `get_permissions`

    def get_permissions(self):
        """Définit les permissions selon l'action."""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]  # Seuls les admins peuvent modifier/supprimer
        return [AllowAny()]  # Autoriser la lecture à tout le monde

    def destroy(self, request, *args, **kwargs):
        """Gère la suppression d'une Category avec une option pour supprimer ou non ses sous-catégories."""
        category = self.get_object()
        subcategories = Category.objects.filter(parent_category=category)

        # Vérification admin (double sécurité en plus de `permission_classes`)
        if not request.user.is_staff:
            return Response({"error": "Seuls les administrateurs peuvent supprimer des catégories."}, status=status.HTTP_403_FORBIDDEN)

        # Vérifier si la catégorie est utilisée par une recette ou un ingrédient
        if category.recipecategory_set.exists() or category.ingredientcategory_set.exists():
            return Response(
                {"error": "Cette catégorie est utilisée par un ingrédient ou une recette et ne peut pas être supprimée."},
                status=status.HTTP_400_BAD_REQUEST)

        # Vérifier l'option delete_subcategories
        delete_subcategories = request.query_params.get("delete_subcategories", "false").lower() == "true"

        try:
            if subcategories.exists():
                if delete_subcategories:
                    subcategories.delete()  # Supprime toutes les sous-catégories
                else:
                    subcategories.update(parent_category=None)  # Délie les sous-catégories

            # Suppression sécurisée          
            category.delete()
            return Response({"message": "Catégorie supprimée avec succès."}, status=status.HTTP_204_NO_CONTENT)

        except IntegrityError:
            return Response({"error": "Erreur lors de la suppression de la catégorie."}, status=status.HTTP_400_BAD_REQUEST)

class LabelViewSet(viewsets.ModelViewSet):
    queryset = Label.objects.all().order_by('label_name')
    serializer_class = LabelSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["label_type"]
    search_fields = ['label_name']
    ordering_fields = ["label_name", "label_type"]
    ordering = ["label_name"]
    permission_classes = []  # On définit les permissions dans `get_permissions`

    def get_permissions(self):
        """Définit les permissions selon l'action."""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]  # Seuls les admins peuvent modifier/supprimer
        return [AllowAny()]  # Autoriser la lecture à tout le monde

    def destroy(self, request, *args, **kwargs):
        """Gère la suppression d'un Label."""
        label = self.get_object()

        # Vérification admin (double sécurité en plus de `permission_classes`)
        if not request.user.is_staff:
            return Response({"error": "Seuls les administrateurs peuvent supprimer des labels."}, status=status.HTTP_403_FORBIDDEN)

        # Vérifier si le label est utilisé par une recette ou un ingrédient
        if label.recipelabel_set.exists() or label.ingredientlabel_set.exists():
            return Response(
                {"error": "Ce label est utilisé par un ingrédient ou une recette et ne peut pas être supprimée."},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            label.delete()
            return Response({"message": "Label supprimé avec succès."}, status=status.HTTP_204_NO_CONTENT)
        except IntegrityError:
            return Response({"error": "Erreur lors de la suppression du label."}, status=status.HTTP_400_BAD_REQUEST)

class RecipeStepViewSet(viewsets.ModelViewSet):
    """ API CRUD pour gérer les étapes d'une recette. """
    queryset = RecipeStep.objects.all().order_by('recipe', 'step_number')
    serializer_class = RecipeStepSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["recipe"]
    ordering_fields = ["step_number", "recipe"]
    ordering = ["recipe", "step_number"]

    def get_queryset(self):
        recipe_pk = self.kwargs.get("recipe_pk")
        if recipe_pk:
            return RecipeStep.objects.filter(recipe_id=recipe_pk)
        return RecipeStep.objects.all()

    def perform_create(self, serializer):
        recipe_pk = self.kwargs.get("recipe_pk")
        # injecte recipe uniquement si recipe_pk est présent dans l’URL.
        if recipe_pk:
            recipe = get_object_or_404(Recipe, pk=recipe_pk)
            serializer.save(recipe=recipe)
        else:
            serializer.save()

    def destroy(self, request, *args, **kwargs):
        """ Empêche la suppression de la dernière `RecipeStep` d'une recette. """
        instance = self.get_object()
        recipe = instance.recipe
        if recipe.steps.count() <= 1:
            return Response({"detail": "Une recette doit contenir au moins une étape."}, status=status.HTTP_400_BAD_REQUEST)

        return super().destroy(request, *args, **kwargs)

class RecipeIngredientViewSet(viewsets.ModelViewSet):
    """ API CRUD pour la gestion des ingrédients dans les recettes. """
    queryset = RecipeIngredient.objects.all().order_by('recipe', 'ingredient')
    serializer_class = RecipeIngredientSerializer

    def get_queryset(self):
        recipe_pk = self.kwargs.get("recipe_pk")
        if recipe_pk:
            return RecipeIngredient.objects.filter(recipe_id=recipe_pk)
        return RecipeIngredient.objects.all()

    def perform_create(self, serializer):
        recipe_pk = self.kwargs.get("recipe_pk")
        if recipe_pk:
            recipe = get_object_or_404(Recipe, pk=recipe_pk)
            serializer.save(recipe=recipe)
        else:
            serializer.save()

    def destroy(self, request, *args, **kwargs):
        """ Empêche la suppression du dernier ingrédient en capturant `ValidationError`. """
        instance = self.get_object()
        try:
            instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DjangoValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class SubRecipeViewSet(viewsets.ModelViewSet):
    """ API CRUD pour gérer les sous-recettes """
    queryset = SubRecipe.objects.all()
    serializer_class = SubRecipeSerializer

    def get_queryset(self):
        recipe_pk = self.kwargs.get("recipe_pk")
        if recipe_pk:
            return SubRecipe.objects.filter(recipe_id=recipe_pk)
        return SubRecipe.objects.all()

    def perform_create(self, serializer):
        recipe_pk = self.kwargs.get("recipe_pk")
        if recipe_pk:
            recipe = get_object_or_404(Recipe, pk=recipe_pk)
            serializer.save(recipe=recipe)
        else:
            serializer.save()

    def destroy(self, request, *args, **kwargs):
        """ Empêche la suppression si la recette est utilisée ailleurs """
        instance = self.get_object()
        try:
            instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DjangoValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PanViewSet(viewsets.ModelViewSet):
    queryset = Pan.objects.all().order_by('pan_name')
    serializer_class = PanSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['pan_type', 'pan_brand']  # autorise le filtre ?pan_type=ROUND&pan_brand=DeBuyer
    search_fields = ["pan_name", "pan_brand"]
    ordering_fields = ["pan_name", "pan_type", "pan_brand"]
    ordering = ["pan_name"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
        except (DjangoValidationError, DRFValidationError) as e:
            return Response({"detail": e.messages if hasattr(e, 'messages') else str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_update(serializer)
        except (DjangoValidationError, DRFValidationError) as e:
            return Response({"detail": e.messages if hasattr(e, 'messages') else str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.data)
    
class RecipeAdaptationAPIView(APIView):
    """API permettant d'adapter une recette à un nouveau contexte (moule ou portions)."""

    def post(self, request, *args, **kwargs):
        """
        Permet d’adapter une recette à un autre moule ou à un nombre de portions cible.

        Les cas supportés :
        - Cas 1 : Adaptation entre moule source et moule cible
        - Cas 2 : Adaptation depuis un nombre de portions initial vers un moule
        - Cas 3 : Adaptation depuis un moule source vers un nombre de portions cible
        - Cas 4 : Adaptation d’un nombre de portions connu (servings_min/max) vers un autre nombre
        """
        # Extraction des paramètres du corps de la requête
        recipe_id = request.data.get("recipe_id")
        source_pan_id = request.data.get("source_pan_id")
        target_pan_id = request.data.get("target_pan_id")
        initial_servings = request.data.get("initial_servings")
        target_servings = request.data.get("target_servings")

        if not recipe_id:
            return Response({"error": "recipe_id est requis"}, status=status.HTTP_400_BAD_REQUEST)

        # Chargement de la recette
        recipe = get_object_or_404(Recipe, pk=recipe_id)

        try:
            # Cas 1 : pan → pan
            if source_pan_id and target_pan_id:
                if not recipe.pan or recipe.pan.id != int(source_pan_id):
                    return Response({"error": "Le moule source de la recette ne correspond pas."}, status=status.HTTP_400_BAD_REQUEST)
                target_pan = get_object_or_404(Pan, pk=target_pan_id)
                data = adapt_recipe_pan_to_pan(recipe, target_pan)

            # Cas 2 : servings → pan
            elif initial_servings and target_pan_id:
                target_pan = get_object_or_404(Pan, pk=target_pan_id)
                volume_target = target_pan.volume_cm3_cache
                volume_source = servings_to_volume(int(initial_servings))
                data = adapt_recipe_with_target_volume(recipe, volume_target, volume_source)
                data["suggested_pans"] = get_suggested_pans(volume_target)

            # Cas 3 : pan → servings
            elif source_pan_id and target_servings:
                if not recipe.pan or recipe.pan.id != int(source_pan_id):
                    return Response({"error": "Le moule source de la recette ne correspond pas."}, status=status.HTTP_400_BAD_REQUEST)
                data = adapt_recipe_servings_to_volume(recipe, int(target_servings))

            # Cas 4 : servings min/max → servings cible
            elif target_servings and recipe.servings_min:
                data = adapt_recipe_servings_to_servings(recipe, int(target_servings))

            else:
                return Response({"error": "Combinaison de paramètres invalide."}, status=status.HTTP_400_BAD_REQUEST)

            return Response(data, status=status.HTTP_200_OK)
    
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PanEstimationAPIView(APIView):
    """
    API permettant d’estimer le volume et le nombre de portions
    d’un moule (pan), à partir d’un moule existant ou de dimensions fournies.
    """

    def post(self, request):
        serializer = PanEstimationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        pan = None
        if data.get("pan_id"):
            pan = get_object_or_404(Pan, pk=data["pan_id"])

        try:
            estimation = estimate_servings_from_pan(
                pan=pan,
                pan_type=data.get("pan_type"),
                diameter=data.get("diameter"),
                height=data.get("height"),
                length=data.get("length"),
                width=data.get("width"),
                rect_height=data.get("rect_height"),
                volume_raw=data.get("volume_raw")
            )
            return Response(estimation, status=200)

        except ValueError as e:
            return Response({"error": str(e)}, status=400)

class PanSuggestionAPIView(APIView):
    """
    API permettant de suggérer des moules en fonction d’un nombre de portions cible,
    sans passer par une recette.
    """

    def post(self, request):
        serializer = PanSuggestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = suggest_pans_for_servings(target_servings=serializer.validated_data["target_servings"])
            return Response(result, status=200)

        except ValueError as e:
            return Response({"error": str(e)}, status=400)

class RecipeAdaptationByIngredientAPIView(APIView):
    """
    API pour adapter une recette en fonction des quantités disponibles
    d’un ou plusieurs ingrédients.
    """

    def post(self, request):
        serializer = RecipeAdaptationByIngredientSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recipe = get_object_or_404(Recipe, pk=serializer.validated_data["recipe_id"])
        # Conversion des clés en entier pour correspondre aux IDs en base
        ingredient_constraints = {
            int(k): v for k, v in serializer.validated_data["ingredient_constraints"].items()
        }

        try:
            result = adapt_recipe_by_ingredients_constraints(recipe, ingredient_constraints)
            return Response(result, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
