"""
URL configuration for pastry_app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from enchante.views import RecipeViewSet, IngredientViewSet, IngredientDeleteView, RecipeDeleteView, PanViewSet, PanDeleteView
from rest_framework.routers import DefaultRouter
from django.contrib import admin

router = DefaultRouter()
router.register(r'recipes', RecipeViewSet)
router.register(r'ingredients', IngredientViewSet)
router.register(r'pans', PanViewSet, basename='pans')
# router.register(r'roundpans', RoundPanViewSet)
# router.register(r'squarepans', SquarePanViewSet) 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(router.urls)),
    path('ingredients/<int:pk>/delete/', IngredientDeleteView.as_view(), name='ingredient_delete'),
    path('recipes/<int:pk>/delete/', RecipeDeleteView.as_view(), name='recipe_delete'),
    path('pans/<int:pk>/delete/', PanDeleteView.as_view(), name='pan_delete'),
]


