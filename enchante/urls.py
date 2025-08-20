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
from django.contrib import admin
from django.urls import path, include
from pastry_app.views import *
from rest_framework_nested.routers import DefaultRouter, NestedDefaultRouter

router = DefaultRouter()
router.register(r'recipes', RecipeViewSet)
router.register(r"recipesteps", RecipeStepViewSet)
router.register(r"sub_recipes", SubRecipeViewSet)
router.register(r'ingredients', IngredientViewSet)
router.register(r'ingredient_prices', IngredientPriceViewSet)
router.register(r'ingredient_prices_history', IngredientPriceHistoryViewSet)
router.register(r'recipe_ingredients', RecipeIngredientViewSet)
router.register(r'pans', PanViewSet)
router.register(r'categories', CategoryViewSet) 
router.register(r'labels', LabelViewSet) 
router.register(r'stores', StoreViewSet) 
router.register(r'ingredient_unit_references', IngredientUnitReferenceViewSet)

# Router imbriqué
recipes_router = NestedDefaultRouter(router, r"recipes", lookup="recipe")
recipes_router.register(r"steps", RecipeStepViewSet, basename="recipe-steps")
ingredients_router = NestedDefaultRouter(router, r"recipes", lookup="recipe")
ingredients_router.register(r"ingredients", RecipeIngredientViewSet, basename="recipe-ingredients")
subrecipes_router = NestedDefaultRouter(router, r"recipes", lookup="recipe")
subrecipes_router.register(r"sub-recipes", SubRecipeViewSet, basename="recipe-subrecipes")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/', include(recipes_router.urls)),
    path('api/', include(ingredients_router.urls)),
    path('api/', include(subrecipes_router.urls)),
    path("api/search/", SearchAPIView.as_view(), name="omnibox-search"),
    path('categories/<int:pk>/delete-subcategories/', CategoryViewSet.as_view({"delete": "delete_subcategories"}), name="delete_subcategories"),
    path("api/recipes-adapt/", RecipeAdaptationAPIView.as_view(), name="adapt-recipe"),
    path("api/recipes-adapt/by-ingredient/", RecipeAdaptationByIngredientAPIView.as_view(), name="adapt-recipe-by-ingredient"),
    path("api/pan-estimation/", PanEstimationAPIView.as_view(), name="estimate-pan"),
    path("api/pan-suggestion/", PanSuggestionAPIView.as_view(), name="suggest-pans"),
]


