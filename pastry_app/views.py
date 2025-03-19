# views.py
from rest_framework import viewsets, generics, status
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from django.db.utils import IntegrityError 
from django.db.models import ProtectedError
from django.core.exceptions import ValidationError
from pastry_app.tests.utils import normalize_case
from .utils import get_pan_model
from .models import Recipe, RecipeStep, Ingredient, Pan, Category, Label, Store, IngredientPrice, IngredientPriceHistory
from .serializers import *

class PanDeleteView(generics.DestroyAPIView):
    queryset = Pan.objects.all()
    serializer_class = PanSerializer

class IngredientDeleteView(generics.DestroyAPIView):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer

class RecipeDeleteView(generics.DestroyAPIView):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer

class StoreViewSet(viewsets.ModelViewSet):
    """ API CRUD pour gérer les magasins. """
    queryset = Store.objects.all()
    serializer_class = StoreSerializer

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
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer

class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer

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
    filter_backends = [SearchFilter]
    search_fields = ['category_name']
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
    filter_backends = [SearchFilter]
    search_fields = ['label_name']
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
    queryset = RecipeStep.objects.all()
    serializer_class = RecipeStepSerializer

    def destroy(self, request, *args, **kwargs):
        """ Empêche la suppression du dernier `RecipeStep` et réorganise les numéros d'étapes après suppression. """
        instance = self.get_object()

        try:
            instance.delete()
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)

class RecipeIngredientViewSet(viewsets.ModelViewSet):
    """ API CRUD pour la gestion des ingrédients dans les recettes. """
    queryset = RecipeIngredient.objects.all()
    serializer_class = RecipeIngredientSerializer

    def destroy(self, request, *args, **kwargs):
        """ Empêche la suppression du dernier ingrédient en capturant `ValidationError`. """
        instance = self.get_object()
        try:
            instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PanViewSet(viewsets.ModelViewSet):
    queryset = Pan.objects.none()
    serializer_class = PanSerializer

    def get_queryset(self):
        pan_type = self.request.query_params.get('pan_type', None)
        if pan_type is not None:
            pan_model = get_pan_model(pan_type)
            return pan_model.objects.all()
        else:
            return Pan.objects.all()

    def get_serializer_class(self):
        pan_type = self.request.query_params.get('pan_type', None)
        if pan_type is not None:
            pan_model = get_pan_model(pan_type)
            return globals()[pan_model.__name__ + 'Serializer']
        else:
            return PanSerializer

# class PanViewSet(viewsets.ModelViewSet):
#     queryset = Pan.objects.all()
#     serializer_class = PanSerializer

# class RoundPanViewSet(viewsets.ModelViewSet):
#     queryset = RoundPan.objects.all()
#     serializer_class = RoundPanSerializer

# class SquarePanViewSet(viewsets.ModelViewSet):
#     queryset = SquarePan.objects.all()
#     serializer_class = SquarePanSerializer