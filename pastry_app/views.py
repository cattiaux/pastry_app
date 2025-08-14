# views.py
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from .permissions import *
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.utils import IntegrityError 
from django.db.models import ProtectedError
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as filters
from django.shortcuts import get_object_or_404
from .utils import *
from .text_utils import *
from .models import *
from .serializers import *
from .mixins import *

class RecipeFilter(filters.FilterSet):
    """
    FilterSet personnalisé pour le modèle Recipe, permettant de filtrer
    sur le champ tags (ArrayField). Supporte la recherche de plusieurs tags à la fois
    via un paramètre de requête séparé par des virgules (ex: ?tags=vegan,healthy).

    L'intérêt est de pouvoir utiliser l'API pour retourner toutes les recettes qui
    contiennent tous les tags recherchés.
    """
    tags = filters.CharFilter(method='filter_tags')

    class Meta:
        model = Recipe
        fields = ['recipe_type', 'chef_name', 'categories', 'labels', 'pan', 'parent_recipe', 'tags']

    def filter_tags(self, queryset, name, value):
        """
        Permet de filtrer les recettes qui contiennent TOUS les tags donnés dans le paramètre.
        Exemple : ?tags=vegan,healthy retournera les recettes qui ont au moins 'vegan' ET 'healthy' dans leur liste tags.
        """
        tags_list = [tag.strip() for tag in value.split(',') if tag.strip()]
        for tag in tags_list:
            queryset = queryset.filter(**{f"{name}__contains": [tag]})
        return queryset

class StoreViewSet(GuestUserRecipeMixin, viewsets.ModelViewSet):
    """ API CRUD pour gérer les magasins. """
    queryset = Store.objects.all().order_by('store_name', 'city')
    serializer_class = StoreSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["city", "zip_code", "store_name"]
    search_fields = ["store_name", "city", "zip_code"]
    ordering_fields = ["store_name", "city", "zip_code"]
    ordering = ["store_name", "city"]
    permission_classes = [IsOwnerOrGuestOrReadOnly, IsNotDefaultInstance]

    def create(self, request, *args, **kwargs):
        """ Vérifie que le magasin n'existe pas avant de le créer. """
        store_name = normalize_case(request.data.get("store_name", ""))
        city = request.data.get("city")
        city = city.strip() if city else ""  # Si 'city' est None alors on transforme None en ""
        zip_code = request.data.get("zip_code")
        zip_code = zip_code.strip() if zip_code else ""  # Si 'zip_code' est None alors on transforme None en ""

        # # Vérifier si un magasin avec le même nom, ville et code postal existe déjà -> DEJA FAIT DANS LE SERIALIZER
        # if Store.objects.filter(store_name=store_name, city=city, zip_code=zip_code).exists():
        #     return Response({"error": "Ce magasin existe déjà."}, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """ Empêche la suppression d'un magasin s'il est utilisé dans des prix. """
        store = self.get_object()
        if store.prices.exists():
            return Response({"error": "Ce magasin est associé à des prix d'ingrédients et ne peut pas être supprimé."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

class IngredientPriceViewSet(viewsets.ModelViewSet):
    """ API CRUD pour gérer les prix des ingrédients. """
    queryset = IngredientPrice.objects.all()
    serializer_class = IngredientPriceSerializer

    def create(self, request, *args, **kwargs):
        """ Vérifie l'existence de l'ingrédient, et refuse la création si le tuple unique existe déjà. """
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

        # # Vérifie si un IngredientPrice existe déjà pour ce tuple -> DEJA FAIT DANS LE SERIALIZER
        # exists = IngredientPrice.objects.filter(ingredient=ingredient, store=store, brand_name=brand_name, quantity=quantity, unit=unit).exists()
        # if exists:
        #     return Response(
        #         {"error": "Un prix existe déjà pour ce tuple. Veuillez le modifier plutôt que d’en créer un nouveau."}, status=status.HTTP_400_BAD_REQUEST)
            
        return super().create(request, *args, **kwargs)

class IngredientPriceHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ API en lecture seule pour l'historique des prix d'ingrédients. """
    queryset = IngredientPriceHistory.objects.all()
    serializer_class = IngredientPriceHistorySerializer
    filter_backends = [SearchFilter]
    search_fields = ["ingredient__ingredient_name"]
    
class RecipeViewSet(GuestUserRecipeMixin, viewsets.ModelViewSet):
    """
    - Lecture pour tous
    - Modification/suppression :
        - pour le propriétaire (user ou guest_id)
        - INTERDIT pour les recettes de base (is_default=True)
    """
    queryset = Recipe.objects.all()\
        .prefetch_related("categories", "labels", "recipe_ingredients", "steps", "main_recipes")\
        .select_related("pan", "parent_recipe", "owned_by_recipe")\
        .order_by("recipe_name", "chef_name")
    serializer_class = RecipeSerializer
    permission_classes = [CanSoftHideRecipeOrIsOwnerOrGuest]

    filterset_class = RecipeFilter
    filter_backends = [SearchFilter, DjangoFilterBackend, OrderingFilter]
    search_fields = ["recipe_name", "chef_name", "context_name", "tags"]
    filterset_fields = ["recipe_type", "chef_name", "categories", "labels", "pan", "parent_recipe", "tags"]
    ordering_fields = ["recipe_name", "chef_name", "recipe_type", "created_at", "parent_recipe"]
    ordering = ["recipe_name", "chef_name"]

    @action(detail=True, methods=["post"], url_path="adapt", permission_classes=[AllowAny])
    @transaction.atomic  # Pour que tout soit fait ou rien si une étape échoue
    def adapt_recipe(self, request, pk=None):
        """
        Clone une recette existante (VARIATION) :
        - Attribue parent_recipe
        - Copie tous les ingrédients/étapes/sous-recettes
        - Bypasse la validation "au moins un ingrédient/sous-recette" au moment du .save()
        - Si la cible est déjà une adaptation, rattache automatiquement à la recette mère.
        """
        original = self.get_object()
       # Si on adapte déjà une adaptation, on remonte à la mère
        mother = original
        while mother.parent_recipe:
            mother = mother.parent_recipe

        # Récupère les données de la recette d'origine
        data = RecipeSerializer(original).data
        data.pop("id", None)
        # Lien de parenté et type d'adaptation
        data["parent_recipe"] = mother.id
        data["recipe_type"] = "VARIATION"
        # Propriétaire (user ou invité)
        data["user"] = request.user.id if request.user.is_authenticated else None
        data["guest_id"] = request.headers.get("X-Guest-Id") if not request.user.is_authenticated else None
        # Champs personnalisables par l'utilisateur
        data["recipe_name"] = request.data.get("recipe_name", f"Adaptation de {original.recipe_name}")
        data["adaptation_note"] = request.data.get("adaptation_note", "")
        data["visibility"] = "private"  # L'adaptation est toujours privée à la création
        data["is_default"] = False      # Jamais recette de base

        # Exclure les relations complexes (étapes, ingrédients, sous-recettes)
        data.pop("ingredients", None)
        data.pop("steps", None)
        data.pop("sub_recipes", None)

        # Crée la nouvelle recette d'adaptation (flag spécial pour éviter l’erreur de validation sur les ingrédients à ce stade)
        context = self.get_serializer_context()
        context["is_adapt_recipe"] = True
        user = request.user if request.user.is_authenticated else None
        guest_id = request.headers.get("X-Guest-Id") if not user else None
        serializer = self.get_serializer(data=data, context=context)        
        serializer.is_valid(raise_exception=True)
        new_recipe = serializer.save(user=user, guest_id=guest_id)

        # Copie les ingrédients (RecipeIngredient)
        for ri in original.recipe_ingredients.all():
            ri.__class__.objects.create(
                recipe=new_recipe,
                ingredient=ri.ingredient,
                quantity=ri.quantity,
                unit=ri.unit,
                display_name=ri.display_name,
            )

        # Copie les étapes
        for step in original.steps.all():
            step.__class__.objects.create(
                recipe=new_recipe,
                step_number=step.step_number,
                instruction=step.instruction,
                trick=step.trick,
            )

        # Copie les sous-recettes
        for sr in original.main_recipes.all():
            new_recipe.main_recipes.create(
                sub_recipe=sr.sub_recipe,
                quantity=sr.quantity,
                unit=sr.unit,
            )

        # Copie les M2M (categories, labels, etc.)
        new_recipe.categories.set(original.categories.all())
        new_recipe.labels.set(original.labels.all())

        return Response(self.get_serializer(new_recipe).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="reference-suggestions")
    def reference_suggestions(self, request, pk=None):
        """
        Suggère une ou plusieurs recettes de référence pertinentes et scalables pour la recette courante.
        - Priorité : catégorie(s) identique(s), puis parent(s), puis fallback sur tout "recipe"/"both".
        - Exclut les recettes qui n'ont ni pan ni servings renseigné.
        - Structure de réponse : {"reference_recipes": [...]}
        """
        recipe = self.get_object()

        target_pan = None
        target_servings = None

        target_pan_id = request.query_params.get("target_pan_id")
        if target_pan_id is not None:
            try:
                target_pan = get_object_or_404(Pan, pk=int(target_pan_id))
            except (TypeError, ValueError):
                return Response({"error": "target_pan_id doit être un entier."}, status=status.HTTP_400_BAD_REQUEST)

        raw_serv = request.query_params.get("target_servings")
        if raw_serv is not None:
            try:
                target_servings = int(raw_serv)
            except (TypeError, ValueError):
                return Response({"error": "target_servings doit être un entier."}, status=status.HTTP_400_BAD_REQUEST)

        recipes_to_suggest = suggest_recipe_reference(recipe, target_servings=target_servings, target_pan=target_pan)

        # Si la première entrée ressemble à notre format plat, on passe tel quel
        items = recipes_to_suggest
        if isinstance(recipes_to_suggest, list) and recipes_to_suggest:
            first = recipes_to_suggest[0]
            is_flat = isinstance(first, dict) and {"id","recipe_name","total_recipe_quantity","category","parent_category"} <= set(first.keys())
            if not is_flat:
                # Fallback: ancien retour (list de Recipe) -> sérialiser
                serializer = RecipeReferenceSuggestionSerializer(recipes_to_suggest, many=True)
                items = serializer.data
                
        # on renvoie aussi les critères pour traçabilité côté front
        return Response({
            "criteria": {
                "target_pan_id": int(target_pan_id) if target_pan_id is not None else None,
                "target_servings": target_servings
            },
            "reference_recipes": items
        })

    @action(detail=True, methods=["post"], url_path=r"subrecipes/(?P<sub_id>\d+)/ingredients/bulk-edit")
    @transaction.atomic
    def bulk_edit_subrecipe_ingredients(self, request, pk=None, sub_id=None):
        """
        Édite en une fois plusieurs ingrédients d'une sous-recette liée à l'hôte `pk` (copy-on-write automatique).
        Body:
          {
            "updates": [
              {"ingredient_id": 123, "quantity": 75, "unit": "g", "display_name": "farine T55"},
              ...
            ],
            "multiplier": 1.0   # optionnel, pour recalcul de l'aperçu
          }
        """
        host: Recipe = self.get_object()  # A (main recipe)
        try:
            link: SubRecipe = host.main_recipes.get(pk=sub_id)  # lien A→B
        except SubRecipe.DoesNotExist:
            return Response({"detail": "Sous-recette introuvable sur cet hôte."}, status=status.HTTP_404_NOT_FOUND)

        user = request.user if request.user.is_authenticated else None
        guest_id = request.headers.get("X-Guest-Id") if not user else None

        # Assurer la variante (copy-on-write)
        target_variant = create_variant_for_host_and_rewire(link, host, user=user, guest_id=guest_id)

        updates = request.data.get("updates", [])
        if not isinstance(updates, list) or not updates:
            return Response({"detail": "Champ 'updates' requis (liste non vide)."}, status=status.HTTP_400_BAD_REQUEST)

        # Index des RecipeIngredient de la variante par ingredient_id
        ri_by_ing = {ri.ingredient_id: ri for ri in target_variant.recipe_ingredients.select_related("ingredient")}

        changed = 0
        for u in updates:
            try:
                ing_id = int(u["ingredient_id"])
            except Exception:
                return Response({"detail": "Chaque update doit contenir 'ingredient_id' entier."}, status=status.HTTP_400_BAD_REQUEST)

            ri = ri_by_ing.get(ing_id)
            if not ri:
                return Response({"detail": f"Ingrédient {ing_id} absent de la préparation."}, status=status.HTTP_400_BAD_REQUEST)

            # Appliquer les champs fournis
            if "quantity" in u:
                ri.quantity = float(u["quantity"])
            if "unit" in u and u["unit"]:
                ri.unit = u["unit"]
            if "display_name" in u:
                ri.display_name = u["display_name"]
            ri.save()
            changed += 1

        # Recalcul d'aperçu
        m = float(request.data.get("multiplier", 1.0))
        out = scale_recipe_globally(host, m, user=user, guest_id=guest_id)
        return Response({"changed": changed, "recipe": out}, status=status.HTTP_200_OK)

    def get_queryset(self):
        """
        Retourne les recettes visibles pour l'utilisateur courant (connecté ou invité).
        - Filtre de base : recettes accessibles selon GuestUserRecipeMixin (user, guest_id, visibilité, is_default).
        - Exclut les recettes masquées pour l'utilisateur courant (UserRecipeVisibility).
        - Si query param `parent_recipe`, filtre uniquement les adaptations de cette recette mère.
        """
        # Étape 1 : Récupère le queryset de base (incluant user/guest_id/public/de base)
        qs = super().get_queryset()
        user = self.request.user

        guest_id = (
            self.request.headers.get("X-Guest-Id")
            or self.request.headers.get("X-GUEST-ID")
            or self.request.data.get("guest_id")
            or self.request.query_params.get("guest_id")
        )

        # Étape 2 : Exclure les recettes explicitement masquées par ce user ou guest_id
        if user.is_authenticated:
            hidden_ids = UserRecipeVisibility.objects.filter(user=user, visible=False).values_list("recipe_id", flat=True)
            qs = qs.exclude(id__in=hidden_ids)
        elif guest_id:
            hidden_ids = UserRecipeVisibility.objects.filter(guest_id=guest_id, visible=False).values_list("recipe_id", flat=True)
            qs = qs.exclude(id__in=hidden_ids)

        # Étape 3 : Si on filtre sur une recette mère, ne garder que ses adaptations (variations)
        parent_recipe = self.request.query_params.get("parent_recipe")
        if parent_recipe:
            qs = qs.filter(parent_recipe=parent_recipe)

        return qs
        
    def destroy(self, request, *args, **kwargs):
        """
        - Empêche la suppression d'une recette mère si elle a des adaptations (versions) ou si elle est utilisée comme sous-recette.
        - Pour les recettes de base (is_default=True), ne les supprime jamais vraiment, mais les masque pour le user ou guest_id courant ("soft-hide").
        - Retourne une erreur métier explicite.
        """
        instance = self.get_object()
        # Cas 1 : Recette de base → soft-hide pour ce user ou guest_id
        if instance.is_default:
            user = request.user if request.user.is_authenticated else None
            guest_id = (
                request.headers.get("X-Guest-Id")
                or request.headers.get("X-GUEST-ID")
                or request.data.get("guest_id")
                or request.query_params.get("guest_id")
            )
            if not user and not guest_id:
                # Anonyme non identifié : refuse la suppression/masquage
                return Response({"detail": "Authentication required for this action."}, status=status.HTTP_403_FORBIDDEN)

            # Soft-hide = ajoute/maj entrée UserRecipeVisibility pour ce user/guest_id et cette recette
            obj, created = UserRecipeVisibility.objects.get_or_create(user=user, guest_id=guest_id, recipe=instance, defaults={"visible": False})
            if not created and obj.visible:
                obj.visible = False
                obj.save()
            # Succès : la recette est masquée pour ce user/invité uniquement
            return Response(status=status.HTTP_204_NO_CONTENT)

        # Cas 2 : Blocage si adaptations (versions)
        if instance.versions.exists():
            return Response({"detail": "Impossible de supprimer cette recette : au moins une adaptation existe."}, status=status.HTTP_400_BAD_REQUEST)

        # Cas 3 : Blocage si utilisée comme sous-recette (intégrité)
        try:
            self.perform_destroy(instance)

        except ProtectedError:
            return Response({"detail": "Cannot delete this recipe because it is used in another recipe."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Cas normal : suppression réussie
        return Response(status=status.HTTP_204_NO_CONTENT)

class IngredientViewSet(GuestUserRecipeMixin, viewsets.ModelViewSet):
    queryset = Ingredient.objects.all().order_by('ingredient_name')
    serializer_class = IngredientSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["categories", "labels"]
    search_fields = ["ingredient_name"]
    ordering_fields = ["ingredient_name"]
    ordering = ["ingredient_name"]
    permission_classes = [IsOwnerOrGuestOrReadOnly & IsNotDefaultInstance]

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

class PanViewSet(GuestUserRecipeMixin, viewsets.ModelViewSet):
    queryset = Pan.objects.all().order_by('pan_name')
    serializer_class = PanSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['pan_type', 'pan_brand']  # autorise le filtre ?pan_type=ROUND&pan_brand=DeBuyer
    search_fields = ["pan_name", "pan_brand"]
    ordering_fields = ["pan_name", "pan_type", "pan_brand"]
    ordering = ["pan_name"]
    permission_classes = [IsOwnerOrGuestOrReadOnly, IsNotDefaultInstance]

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
    
class IngredientUnitReferenceViewSet(OverridableReferenceQuerysetMixin, GuestUserReferenceMixin, viewsets.ModelViewSet):
    """
    ViewSet CRUD complet pour gérer le mapping d'unités en API.
    Limité aux admins (modifiable selon tes besoins).
    """
    queryset = IngredientUnitReference.objects.all().select_related('ingredient')
    serializer_class = IngredientUnitReferenceSerializer
    filterset_fields = ['unit', 'ingredient']
    search_fields = ['ingredient__ingredient_name', 'ingredient__slug', 'notes']
    ordering_fields = ['ingredient', 'unit', 'weight_in_grams']
    ordering = ['ingredient', 'unit']
    permission_classes = [CanForkOrIsOwnerOrGuest]
    
    def get_queryset(self):
        base_queryset = super().get_queryset()
        qs = self.get_user_overridable_queryset(base_queryset)
        return qs.filter(is_hidden=False)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user if request.user.is_authenticated else None
        guest_id = (request.session.get('guest_id') or request.headers.get("X-Guest-Id") or request.data.get("guest_id") or request.query_params.get("guest_id"))
        # Si global, on duplique en privé ou update le privé
        if instance.user is None and instance.guest_id is None:
            # Vérifie si privé existe déjà
            private_qs = IngredientUnitReference.objects.filter(ingredient=instance.ingredient, unit=instance.unit, 
                                                                user=user, guest_id=guest_id)
            if private_qs.exists():
                private_instance = private_qs.first()
                return super().update(request, pk=private_instance.pk)
            else:
                # Créer copie privée
                data = request.data.copy()
                data['ingredient'] = instance.ingredient.ingredient_name 
                data['unit'] = instance.unit
                serializer = self.get_serializer(data=data)
                serializer.is_valid(raise_exception=True)
                serializer.save(user=user, guest_id=guest_id)
                return Response(serializer.data)
        else:
            # Comportement standard
            return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user if request.user.is_authenticated else None
        guest_id = (request.session.get('guest_id') or request.headers.get("X-Guest-Id") or request.data.get("guest_id") or request.query_params.get("guest_id"))
        if instance.user is None and instance.guest_id is None:
            if not user and not guest_id:
                raise PermissionDenied("Vous devez être authentifié ou avoir un guest_id pour masquer une référence.")

            # "Suppression" = créer version privée qui surchargera la globale (fork privé/"tombstone")
            obj, created = IngredientUnitReference.objects.get_or_create(
                ingredient=instance.ingredient,
                unit=instance.unit,
                user=user,
                guest_id=guest_id,
                defaults={'weight_in_grams': instance.weight_in_grams, 'is_hidden': True}
            )
            if not created:
                obj.is_hidden = True
                obj.save()
            return Response(status=204)
        else:
            return super().destroy(request, *args, **kwargs)

class RecipeAdaptationAPIView(APIView):
    """
    API permettant d'adapter une recette à un nouveau contexte : 
    - changement de moule,
    - changement de nombre de portions,
    - adaptation en se basant sur une recette de référence.

    ## Modes supportés (gérés par `get_scaling_multiplier`) :

    **Adaptations directes :**
        1. `pan_to_pan` — Adaptation entre moule source et moule cible
        2. `servings_to_pan` — Adaptation depuis un nombre de portions initial vers un moule
        3. `pan_to_servings` — Adaptation depuis un moule source vers un nombre de portions cible
        4. `servings_to_servings` — Adaptation entre deux nombres de portions connus

    **Adaptations par recette de référence :**
        5. `reference_recipe_pan` — Adaptation à partir d'une recette de référence avec pan connu 
           (recette cible adaptée vers le target_pan ou target_servings en conservant les proportions de la référence)
        6. `reference_recipe_servings` — Adaptation à partir d'une recette de référence avec servings connus 
           (recette cible adaptée vers le target_pan ou target_servings)
        
    ## Règles métier :
        - `recipe_id` est obligatoire.
        - Il faut fournir au moins un critère : `target_pan_id`, `target_servings` ou `reference_recipe_id`.

    ## Priorité effective :
        - Par défaut: adaptation directe si possible, puis fallback via référence
        - Si `prefer_reference=true` ET `reference_recipe_id` fourni: on tente d’abord par référence (puis fallback direct)
    """
    def post(self, request, *args, **kwargs):
        """
        Adapte une recette selon l’un des modes décrits dans la docstring.
        Retourne la recette adaptée avec les nouvelles quantités, le multiplicateur appliqué 
        et le mode d'adaptation utilisé.

        Paramètres d'entrée attendus (au moins un critère d'adaptation requis) :
            - recipe_id (int) : identifiant de la recette à adapter (obligatoire)
            - target_pan_id (int, optionnel) : moule cible
            - target_servings (int, optionnel) : nombre de portions cibles
            - reference_recipe_id (int, optionnel) : recette servant de référence
            - prefer_reference (bool) [ptionnel, défaut False]  : force l’utilisation prioritaire de la référence si fournie
        """
        # Extraction des paramètres du corps de la requête
        recipe_id = request.data.get("recipe_id")
        target_pan_id = request.data.get("target_pan_id")
        target_servings = request.data.get("target_servings")
        reference_recipe_id = request.data.get("reference_recipe_id")
        prefer_reference = bool(request.data.get("prefer_reference") or request.query_params.get("prefer_reference"))

        if not recipe_id:
            return Response({"error": "recipe_id est requis"}, status=status.HTTP_400_BAD_REQUEST)

        # Chargement de la recette
        recipe = get_object_or_404(Recipe, pk=recipe_id)
        target_pan = get_object_or_404(Pan, pk=target_pan_id) if target_pan_id else None
        reference_recipe = get_object_or_404(Recipe, pk=reference_recipe_id) if reference_recipe_id else None

        # Contrôle : il faut au moins un critère d’adaptation
        if not target_pan and not target_servings and not reference_recipe:
            return Response({"error": "Il faut fournir un moule cible, un nombre de portions cible ou une recette de référence."}, 
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Calcul du multiplicateur global (la logique interne gère la priorité)
            multiplier, scaling_mode = get_scaling_multiplier(recipe, target_pan=target_pan, target_servings=target_servings, 
                                                              reference_recipe=reference_recipe, prefer_reference=prefer_reference)
            # 2. Application du scaling partout
            data = scale_recipe_globally(recipe, multiplier)
            # 3. Infos utiles en plus
            data["scaling_mode"] = scaling_mode
            data["scaling_multiplier"] = multiplier  
            return Response(data, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PanEstimationAPIView(APIView):
    """
    API permettant d’estimer le volume et le nombre de portions d’un moule (pan), 
    à partir d’un moule existant.
    """

    def post(self, request):
        serializer = PanEstimationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not data.get("pan_id"):
            return Response({"error": "Un pan_id doit être fourni."}, status=400)
        pan = get_object_or_404(Pan, pk=data["pan_id"])

        try:
            estimation = estimate_servings_from_pan(pan)
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

        # Récupère user/guest pour choisir la bonne référence d’unité (spécifique → globale)
        user = request.user if request.user.is_authenticated else None
        guest_id = (request.headers.get("X-Guest-Id") or request.headers.get("X-GUEST-ID") or serializer.validated_data.get("guest_id") or request.query_params.get("guest_id"))

        # Conversion des clés en entier pour correspondre aux IDs en base
        ingredient_constraints = {int(k): v for k, v in serializer.validated_data["ingredient_constraints"].items()}

        try:
            # 1. Normalise vers l’unité attendue par la recette (via IngredientUnitReference)
            normalized_constraints = normalize_constraints_for_recipe(recipe, ingredient_constraints, user=user, guest_id=guest_id)
            # 2. Calcul du multiplicateur limitant
            multiplier, limiting_ingredient_id = get_limiting_multiplier(recipe, ingredient_constraints)
            # 3. Adaptation globale
            result = scale_recipe_globally(recipe, multiplier)
            # 4. Ajoute les infos utiles au retour
            result["limiting_ingredient_id"] = limiting_ingredient_id
            result["multiplier"] = multiplier
            return Response(result, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
