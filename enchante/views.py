# views.py
from rest_framework import viewsets, generics
from .models import Recipe, Ingredient, Pan#, RoundPan, SquarePan
from .serializers import RecipeSerializer, IngredientSerializer, PanSerializer#, RoundPanSerializer, SquarePanSerializer
from .utils import get_pan_model

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