# views.py
from rest_framework import viewsets, generics, status
from .models import Recipe, Ingredient, Pan, Category, Label, Store, IngredientPrice, IngredientPriceHistory
from .serializers import RecipeSerializer, IngredientSerializer, PanSerializer, CategorySerializer, LabelSerializer, StoreSerializer, IngredientPriceSerializer, IngredientPriceHistorySerializer
from .utils import get_pan_model
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from django.db.utils import IntegrityError 
from django.db.models import ProtectedError
from pastry_app.tests.utils import normalize_case

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
        """ Vérifie que l'ingrédient existe avant de créer un prix. """
        ingredient_slug = request.data.get("ingredient")

        # Convertir le slug en id
        if ingredient_slug:
            try:
                Ingredient.objects.get(ingredient_name=ingredient_slug)  # Vérification seulement, pas besoin de stocker l'id
            except Ingredient.DoesNotExist:
                return Response({"error": "Cet ingrédient n'existe pas."}, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """ Désactive la mise à jour des prix pour conserver l'historique. """
        return Response({"error": "La mise à jour des prix est interdite. Créez un nouvel enregistrement."},
                        status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def destroy(self, request, *args, **kwargs):
        """ Empêche la suppression d'un prix s'il a un historique. """
        price = self.get_object()
        if price.history.exists():
            return Response(
                {"error": "Ce prix possède un historique et ne peut pas être supprimé."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)

class IngredientPriceHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ API en lecture seule pour l'historique des prix d'ingrédients. """
    queryset = IngredientPriceHistory.objects.all()
    serializer_class = IngredientPriceHistorySerializer
    filter_backends = [SearchFilter]
    search_fields = ["ingredient_price__ingredient__ingredient_name"]

    def create(self, request, *args, **kwargs):
        """ Interdiction de créer des entrées manuelles dans l'historique. """
        return Response({"error": "L'historique des prix est généré automatiquement et ne peut pas être modifié manuellement."},
                        status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def destroy(self, request, *args, **kwargs):
        """ Interdiction de supprimer une entrée historique. """
        return Response({"error": "Les entrées de l'historique des prix ne peuvent pas être supprimées."},
                        status=status.HTTP_405_METHOD_NOT_ALLOWED)

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

    def destroy(self, request, *args, **kwargs):
        """Empêche la suppression d'une Category si elle est utilisée par un Ingredient ou par une Recipe."""
        category = self.get_object()
        try:
            category.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except IntegrityError:
            return Response(
                {"error": "Cette catégorie est utilisée par un ingrédient ou une recette et ne peut pas être supprimée."},
                status=status.HTTP_400_BAD_REQUEST
            )

    def destroy(self, request, *args, **kwargs):
        """ Empêche la suppression d'une catégorie si elle est utilisée par un ingrédient ou une recette. """
        category = self.get_object()
        try:
            self.perform_destroy(category)  # Utilisation de DRF
        except ProtectedError:  
            return Response(
                {"error": "Cette catégorie est utilisée par un ingrédient ou une recette et ne peut pas être supprimée."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

        # """
        # OLD destroy method avec SQLITE
        # Lors de la migration vers PostgreSQL, tester si `on_delete=PROTECT` fonctionne. 
        # Si PostgreSQL bloque bien la suppression, on pourra retirer cette vérification.
        # """

        # instance = self.get_object()
        # # Vérification si la catégorie est utilisée par un ingrédient, avant d'essayer de supprimer
        # if instance.ingredients.exists():
        #     return Response(
        #         {"detail": f"La catégorie '{instance.category_name}' est utilisée par des ingrédients et ne peut pas être supprimée."},
        #         status=status.HTTP_400_BAD_REQUEST
        #     )
        # # Vérification si la catégorie est utilisée par une recette, avant d'essayer de supprimer
        # if instance.recipes.exists():
        #     return Response(
        #         {"detail": f"La catégorie '{instance.category_name}' est utilisée par des recettes et ne peut pas être supprimée."},
        #         status=status.HTTP_400_BAD_REQUEST
        #     )
        # return super().destroy(request, *args, **kwargs)
        
class LabelViewSet(viewsets.ModelViewSet):
    queryset = Label.objects.all().order_by('label_name')
    serializer_class = LabelSerializer
    filter_backends = [SearchFilter]
    search_fields = ['label_name']

    def destroy(self, request, *args, **kwargs):
        """Empêche la suppression d'un Label s'il est utilisé par un Ingredient ou par une Recipe."""
        label = self.get_object()
        try:
            self.perform_destroy(label)  # Utilisation de DRF
        except ProtectedError:
            return Response(
                {"error": "Ce label est utilisé par un ingrédient ou une recette et ne peut pas être supprimé."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

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