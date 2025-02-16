# views.py
from rest_framework import viewsets, generics, status
from .models import Recipe, Ingredient, Pan, Category, Label
from .serializers import RecipeSerializer, IngredientSerializer, PanSerializer, CategorySerializer, LabelSerializer
from .utils import get_pan_model
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from django.db.utils import IntegrityError 
from django.db.models import ProtectedError

class PanDeleteView(generics.DestroyAPIView):
    queryset = Pan.objects.all()
    serializer_class = PanSerializer

class IngredientDeleteView(generics.DestroyAPIView):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer

class RecipeDeleteView(generics.DestroyAPIView):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer

class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer

class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer

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