import json, subprocess, sys, os
from pathlib import Path
from django.contrib import admin, messages
from django.contrib.admin import RelatedOnlyFieldListFilter
from django import forms
from django.forms.models import BaseInlineFormSet
from django.db.models import Exists, OuterRef
from django.urls import reverse, path
from django.shortcuts import redirect
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.conf import settings
from django.http import JsonResponse
from .models import *
from .mixins import *

class StoreCityListFilter(admin.SimpleListFilter):
    """
    Class pour filter par city dans l'admin de Django.
    """
    title = 'Ville du magasin'
    parameter_name = 'store_city'

    def lookups(self, request, model_admin):
        # Liste des villes présentes dans les stores liés à IngredientPrice
        cities = set(Store.objects.exclude(city__isnull=True).exclude(city__exact="").values_list('city', flat=True))
        return [(city, city) for city in cities]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(store__city=self.value())
        return queryset

class StoreNameListFilter(admin.SimpleListFilter):
    """
    Class pour filter par nom de magasin dans l'admin de Django.
    """
    title = 'Nom du magasin'
    parameter_name = 'store_store_name'

    def lookups(self, request, model_admin):
        # Liste des store_name présentes dans les stores liés à IngredientPrice
        store_names = set(Store.objects.exclude(store_name__isnull=True).exclude(store_name__exact="").values_list('store_name', flat=True))
        return [(store_name, store_name) for store_name in store_names]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(store__store_name=self.value())
        return queryset

class CategoryAdminForm(forms.ModelForm):
    """ formulaire personnalisé pour Category"""
    class Meta:
        model = Category
        fields = "__all__"

class IngredientAdminForm(forms.ModelForm):
    """
    Formulaire admin personnalisé pour Ingredient.

    - Affiche une erreur claire sur le champ 'ingredient_name' si le nom existe déjà,
    au lieu d'une page d'erreur générale. Améliore l'UX admin pour la contrainte unique.
    - Form admin Ingredient: restreint catégories/labels et valide.
    """
    class Meta:
        model = Ingredient
        fields = '__all__'

    def clean_ingredient_name(self):
        # On normalise comme en prod
        value = self.cleaned_data["ingredient_name"].strip().lower()
        if Ingredient.objects.exclude(pk=self.instance.pk).filter(ingredient_name__iexact=value).exists():
            raise ValidationError("Un ingrédient avec ce nom existe déjà.")
        return value

    def __init__(self, *args, **kwargs):
        """Initialise le formulaire et restreint les M2M aux catégories/labels de type 'ingredient' ou 'both'."""
        super().__init__(*args, **kwargs)
        self.fields["categories"].queryset = Category.objects.filter(category_type__in=["ingredient", "both"])
        self.fields["labels"].queryset     = Label.objects.filter(label_type__in=["ingredient", "both"])

    def clean(self):
        """Vérifie les sélections M2M et refuse toute catégorie/label de type 'recipe'; retourne les données validées."""
        data = super().clean()
        cats = data.get("categories")
        if cats is not None:
            bad = cats.exclude(category_type__in=["ingredient", "both"])
            if bad.exists():
                raise ValidationError(f"Catégories interdites pour un ingrédient: {', '.join(b.category_name for b in bad)}")
        labs = data.get("labels")
        if labs is not None:
            bad = labs.exclude(label_type__in=["ingredient", "both"])
            if bad.exists():
                raise ValidationError(f"Labels interdits pour un ingrédient: {', '.join(b.label_name for b in bad)}")
        return data

@admin.register(IngredientPrice)
class IngredientPriceAdmin(AdminSuggestMixin, admin.ModelAdmin):
    list_display = ("id", "ingredient", "brand_name", "store", "quantity", "unit", "price", "is_promo", "promotion_end_date", "date")
    list_filter = ("brand_name", "is_promo", StoreCityListFilter, StoreNameListFilter)
    search_fields = ("ingredient__ingredient_name", "brand_name", "store__store_name")
    autocomplete_fields = ['ingredient', 'store']

    class Media:
        css = {'all': ('pastry_app/admin/required_fields.css',)}
        js = ('pastry_app/admin/search_suggest.js',)

@admin.register(IngredientPriceHistory)
class IngredientPriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "ingredient_name", "brand_name", "store", "quantity", "unit", "price", "is_promo", "promotion_end_date", "date")
    list_filter = ("brand_name", "is_promo", StoreCityListFilter, StoreNameListFilter)
    search_fields = ("ingredient__ingredient_name", "brand_name", "store__store_name")
    date_hierarchy = 'date'
    
    def has_add_permission(self, request):
        """ Empêche l'ajout manuel d'entrées historiques sauf pour les super-utilisateurs. """
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """ Empêche la modification d'entrées historiques sauf pour les super-utilisateurs. """
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        """ Empêche la suppression d'entrées historiques sauf pour les super-utilisateurs. """
        return request.user.is_superuser

class ChildCategoryInline(admin.TabularInline):
    """
    Affiche les sous-catégories sur la page d'une catégorie parente.
    """
    model = Category
    fk_name = "parent_category"
    extra = 0
    show_change_link = True  # crayon vers la sous-catégorie

@admin.register(Category)
class CategoryAdmin(AdminSuggestMixin, admin.ModelAdmin):
    """
    Changelist par défaut : seules les catégories PARENTS (parent_category IS NULL).
    Comportements:
      - ?show=all     → toutes les catégories
      - ?show=leaves  → uniquement les FEUILLES (sans enfants)
      - ?parent=<id>  → uniquement les enfants de cette catégorie
      - Recherche (q) → cherche sur TOUTES les catégories
      - L’URL ?parent_category__id__exact=<id> affiche les enfants (lookup admin natif).
      - Page objet    → jamais filtrée (évite 404)
    """
    form = CategoryAdminForm
    list_display = ("category_name", "category_type", "parent_category", "children_link", "id")
    search_fields = ('category_name',)
    inlines = [ChildCategoryInline]

    class Media:
        js = ('pastry_app/admin/category_admin.js', 'pastry_app/admin/search_suggest.js',)
        css = {'all': ('pastry_app/admin/required_fields.css',)}

    # 2) Filtre latéral interne, gère le défaut 'Parents'
    class ShowFilter(admin.SimpleListFilter):
        title = "Affichage"
        parameter_name = "show"

        def lookups(self, request, model_admin):
            return (("main", "Parents"), ("all", "Toutes"), ("leaves", "Feuilles"))

        def queryset(self, request, qs):
            # Si on a un lookup parent natif ou une recherche, ne pas restreindre
            if request.GET.get("parent_category__id__exact") or request.GET.get("q"):
                return qs
            
            v = self.value()
            if v == "all":
                return qs
            if v == "leaves":
                Model = qs.model
                # ré-annoter au cas où
                has_children = Exists(Model.objects.filter(parent_category=OuterRef("pk")))
                return qs.annotate(has_children=has_children).filter(has_children=False)
            # défaut: Parents
            return qs.filter(parent_category__isnull=True)

    list_filter = (ShowFilter, "category_type")
    
    # Lien enfants → changelist filtré par lookup admin valide
    def children_link(self, obj):
        if not getattr(obj, "has_children", False):
            return ""
        url = reverse(
            f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist",
            current_app=self.admin_site.name,
        )
        return format_html('<a href="{}?parent_category__id__exact={}">Voir sous-catégories</a>', url, obj.pk)
    children_link.short_description = "Sous-catégories"

    # Surcharge de la vue de suppression pour contrôler les messages et empêcher le double message succès/erreur
    def delete_view(self, request, object_id, extra_context=None):
        """
        Cette méthode est surchargée pour :
        - Empêcher la suppression d'une catégorie si elle possède des sous-catégories ou est utilisée,
        - Afficher un message d'erreur (et uniquement celui-ci),
        - Rediriger vers la liste sans afficher le message de succès natif du Django admin,
        - Éviter l'affichage simultané d'un message de succès (inexact) et d'un message d'erreur métier.
        """
        obj = self.get_object(request, object_id)
        # Cas de blocage par enfants ou utilisation
        if obj:
            if obj.recipecategory_set.exists() or obj.ingredientcategory_set.exists():
                messages.error(request, "Impossible de supprimer cette catégorie : elle est utilisée par une recette ou un ingrédient.")
                return redirect('..')
            subcategories = obj.subcategories.all()
            if subcategories.exists():
                sub_names = ', '.join([sc.category_name for sc in subcategories])
                messages.error(
                    request,
                    f"Impossible de supprimer cette catégorie : elle possède des sous-catégories ({sub_names})."
                )
                return redirect('..')
        return super().delete_view(request, object_id, extra_context)

    # Action admin : suppression parent + enfants
    def delete_with_children(self, request, queryset):
        for obj in queryset:
            subcategories = obj.subcategories.all()
            count = subcategories.count()
            subcategories.delete()
            obj.delete()
            messages.success(request, f"Catégorie '{obj.category_name}' et ses {count} sous-catégories supprimées.")
    delete_with_children.short_description = "Supprimer catégorie + sous-catégories"
    actions = [delete_with_children]

@admin.register(Label)
class LabelAdmin(AdminSuggestMixin, admin.ModelAdmin):
    """
    - list_filter par type (choices de label_type)
    - search sur label_name et label_type (valeurs brutes des choices)
    """
    list_display = ('label_name', 'label_type')
    list_filter = ('label_type',)  
    search_fields = ('label_name', 'label_type') 

    class Media:
        css = {'all': ('pastry_app/admin/required_fields.css',)}
        js = ('pastry_app/admin/search_suggest.js',)

    def delete_model(self, request, obj):
        # Refuse la suppression si le label est utilisé
        if obj.recipelabel_set.exists() or obj.ingredientlabel_set.exists():
            messages.error(request, "Impossible de supprimer ce label : il est utilisé par une recette ou un ingrédient.")
            return
        super().delete_model(request, obj)

@admin.register(Store)
class StoreAdmin(AdminSuggestMixin, admin.ModelAdmin):
    list_display = ('store_name', 'id', 'city', 'zip_code', 'address', 'visibility', 'is_default')
    search_fields = ('store_name', 'city')
    list_filter = ('city', 'visibility')

    fieldsets = (
        ('Caractéristiques du magasin', {
            'fields': ('store_name', 'city', 'zip_code', 'address')
        }),
        ('Gestion / Droits', {
            'fields': ('visibility', 'is_default', 'user', 'guest_id'),
            'description': "Champs relatifs à la visibilité, aux droits, ou à la gestion multi-utilisateur."
        }),
    )

    class Media:
        css = {'all': ('pastry_app/admin/required_fields.css',)}
        js = ('pastry_app/admin/search_suggest.js',)

@admin.register(Pan)
class PanAdmin(AdminSuggestMixin, admin.ModelAdmin):
    list_display = ('pan_name', 'id', 'pan_brand', 'pan_type', 'units_in_mold', 'visibility', 'is_default')
    search_fields = ('pan_name', 'pan_brand')
    list_filter = ('pan_type', ('pan_brand', admin.AllValuesFieldListFilter), 'visibility')

    fieldsets = (
        ('Caractéristiques du moule', {
            'fields': (
                'pan_name', 'pan_type', 'pan_brand', 
                'diameter', 'height', 
                'length', 'width', 'rect_height', 
                'volume_raw', 'is_total_volume', 'unit'
            )
        }),
        ('Gestion / Droits', {
            'fields': ('visibility', 'is_default', 'user', 'guest_id'),
            'description': "Champs relatifs à la visibilité, aux droits, ou à la gestion multi-utilisateur."
        }),
    )

    class Media:
        js = ('pastry_app/admin/pan_admin.js', 'pastry_app/admin/search_suggest.js',)
        css = {'all': ('pastry_app/admin/required_fields.css',)}

# Pour l’affichage des catégories et labels sous forme de string
def categories_display(obj):
    return ", ".join([c.category_name for c in obj.categories.all()])
categories_display.short_description = "Catégories"

def labels_display(obj):
    return ", ".join([l.label_name for l in obj.labels.all()])
labels_display.short_description = "Labels"

def prices_count(obj):
    return obj.prices.count()
prices_count.short_description = "Nb Prix"

class IngredientPriceInline(admin.TabularInline):
    model = IngredientPrice
    extra = 0  # number of extra forms to display
    min_num = 0
    show_change_link = True  # pour avoir un lien direct vers la fiche prix si besoin

class CategoryDrilldownFilter(admin.SimpleListFilter):
    """Filtre hiérarchique: parents -> enfants -> petits-enfants, etc."""
    title = "Catégorie"
    parameter_name = "cat"
    allowed_types = ("ingredient", "recipe", "both")  # Défaut neutre (évite l’AttributeError si __init__ n’est pas pris)

    def __init__(self, request, params, model, model_admin):
        """Lit category_allowed_types; log le modèle et les types autorisés."""
        super().__init__(request, params, model, model_admin)
        Model = getattr(model_admin, "model", None)
        # 1) Si l’admin définit explicitement les types, on les utilise
        if hasattr(model_admin, "category_allowed_types"):
            self.allowed_types = tuple(model_admin.category_allowed_types)
        # 2) Sinon, déduis automatiquement par modèle (évite le défaut 'toutes')
        else:
            if Model is Ingredient:
                self.allowed_types = ("ingredient", "both")
            elif Model is Recipe:
                self.allowed_types = ("recipe", "both")
            else:
                self.allowed_types = ("ingredient", "recipe", "both")

    def lookups(self, request, model_admin):
        """
        Construit les options visibles. Lit category_allowed_types à chaque appel
        pour éviter les instances avec le défaut neutre.
        """
        # Calcule les types autorisés depuis l'admin courant
        allowed = tuple(getattr(model_admin, "category_allowed_types",
                                self.allowed_types))
        self.allowed_types = allowed  # persiste pour queryset()

        sel = self.value()
        qs = (Category.objects.filter(parent_category__isnull=True,
                                    category_type__in=allowed)
            if not sel else
            Category.objects.filter(parent_category_id=sel,
                                    category_type__in=allowed))

        return [(c.pk, ("↳ " + c.category_name) if sel else c.category_name)
                for c in qs.order_by("category_name")]

    def _descendants_ids(self, root_id):
        ids = {int(root_id)}
        frontier = [int(root_id)]
        while frontier:
            children = Category.objects.filter(parent_category_id__in=frontier)\
                                       .values_list("id", flat=True)
            new = set(children) - ids
            if not new: break
            ids |= new
            frontier = list(new)
        return ids

    def queryset(self, request, qs):
        sel = self.value()
        if not sel:
            return qs
        ids = self._descendants_ids(sel)
        return qs.filter(categories__id__in=ids).distinct()

@admin.register(Ingredient)
class IngredientAdmin(AdminSuggestMixin, admin.ModelAdmin):
    category_allowed_types = ("ingredient", "both")
    form = IngredientAdminForm
    inlines = [IngredientPriceInline]
    list_display = ('ingredient_name', 'id', categories_display, labels_display, 'visibility', 'is_default', prices_count)
    search_fields = ('ingredient_name', 'categories__category_name', 'labels__label_name')

    # ---- Filtre Labels restreint (type ingredient|both) ----
    class _LabelForIngredientFilter(RelatedOnlyFieldListFilter):
        """Filtre 'labels' restreint à label_type in (ingredient, both)."""
        def field_choices(self, field, request, model_admin):
            qs = Label.objects.filter(label_type__in=["ingredient", "both"])
            return [(l.pk, str(l)) for l in qs]

    list_filter = (CategoryDrilldownFilter, ("labels", _LabelForIngredientFilter), "visibility")

    class Media:
        css = {'all': ('pastry_app/admin/required_fields.css',)}
        js = ('pastry_app/admin/search_suggest.js',)

    # Pour mieux ordonner les champs et regrouper les sections
    fieldsets = (
        ('Informations principales', {
            'fields': ('ingredient_name', 'categories', 'labels')
        }),
        ('Gestion', {
            'fields': ('visibility', 'is_default', 'user', 'guest_id')
        }),
    )

    # Pour afficher les catégories/labels sous forme de widget horizontal
    filter_horizontal = ('categories', 'labels')
    # autocomplete_fields = ['categories', 'labels']  # si préférence pour l’auto-complétion en formulaire plutôt que filter_horizontal

class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 0
    readonly_fields = ['display_name'] 

class RecipeStepInlineForm(forms.ModelForm):
    """
    Formulaire ModelForm custom pour RecipeStep Inline dans l'admin.
    - Garantit que le step_number assigné dans cleaned_data est bien propagé sur l'instance avant sauvegarde.
    """
    def save(self, commit=True):
        # Force la cohérence : ce qui est dans cleaned_data devient la vraie valeur de l'instance
        step_number = self.cleaned_data.get('step_number')
        if step_number is not None:
            self.instance.step_number = step_number
        return super().save(commit=commit)

class RecipeStepInlineFormSet(BaseInlineFormSet):
    """
    Formset personnalisé pour la gestion des étapes de recette (RecipeStep) dans l'admin Django.

    - Auto-recalcule TOUS les step_number consécutifs (1...N) après création, édition ou suppression.
    - Aucun champ step_number n'est obligatoire côté admin.
    - UX fluide, plus besoin de corriger à la main, ni de gérer les doublons ou les trous dans la séquence.
    - Affiche les erreurs métier user-friendly dans l'admin (pas d'écran jaune).
    """
    def clean(self):
        # Appelle la clean de base (qui va appeler clean() sur chaque form/instance)
        super().clean()

        # 1. Retire l'erreur métier "l'unique step doit être n°1" en mode admin, seulement en création admin
        #    (souvent gênante lors des saisies multiples inline)
        errors_to_skip = ["S'il n'y a qu'une seule étape, son numéro doit être 1."]
        for form in self.forms:
            if form.errors:
                # Si la forme contient l'erreur métier ciblée, on la retire
                # (utile uniquement lors de la création, pas lors de l'update d'une recette existante)
                for error in errors_to_skip:
                    form._errors.pop('__all__', None)

        # 2. Récupère tous les forms valides (pas DELETE)
        step_forms = [form for form in self.forms if form.cleaned_data and not form.cleaned_data.get('DELETE', False)]

        # 3. Attribue à CHAQUE form un step_number consécutif en fonction de l'ordre visuel (formset)
        for i, form in enumerate(step_forms, start=1):
            form.cleaned_data['step_number'] = i

class RecipeStepInline(admin.TabularInline):
    model = RecipeStep
    extra = 1
    form = RecipeStepInlineForm
    formset = RecipeStepInlineFormSet

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "instruction":
            kwargs["widget"] = forms.Textarea(attrs={"rows": 2, "cols": 40})
        if db_field.name == "trick":
            kwargs["widget"] = forms.Textarea(attrs={"rows": 1, "cols": 40})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def delete_model(self, request, obj):
        """ Affiche les erreurs métier (ex: suppression du dernier step) comme message utilisateur."""
        try:
            obj.delete()
        except ValidationError as e:
            self.message_user(request, e.messages[0], level=messages.ERROR)

    def save_formset(self, request, form, formset, change):
        """ Réordonne automatiquement les step_number après modification/suppression. """
        # Appel normal
        super().save_formset(request, form, formset, change)
        # Réordonner les steps
        recipe = form.instance
        steps = recipe.steps.order_by('step_number')
        for i, step in enumerate(steps, start=1):
            if step.step_number != i:
                step.step_number = i
                step.save()

class SubRecipeInline(admin.TabularInline):
    model = SubRecipe
    fk_name = 'recipe'
    extra = 0
    show_change_link = True  # permet d’ouvrir/éditer la sous-recette depuis l’inline

    # Optionnel: lien direct vers la recette liée (fichier Recipe) pour éviter toute ambiguïté
    # readonly_fields = ("open_sub_recipe",)
    # fields = ("sub_recipe", "open_sub_recipe", "quantity", "unit")

    # def open_sub_recipe(self, obj):
    #     from django.utils.html import format_html
    #     from django.urls import reverse
    #     if not obj or not obj.pk:
    #         return ""
    #     url = reverse("admin:pastry_app_recipe_change", args=(obj.sub_recipe_id,))
    #     return format_html('<a href="{}">Ouvrir la sous-recette</a>', url)
    # open_sub_recipe.short_description = "Recette liée"

class RecipeCategoryInline(admin.TabularInline):
    model = RecipeCategory
    extra = 0
    autocomplete_fields = ['category']

class RecipeLabelInline(admin.TabularInline):
    model = RecipeLabel
    extra = 0
    autocomplete_fields = ['label']

class RecipeAdminForm(forms.ModelForm):
    mode_ajustement = forms.BooleanField(required=False, label="Mode ajustement", 
                                         help_text="Permet d’ajuster les quantités sans modifier la recette.")

    class Meta:
        model = Recipe
        fields = "__all__"
  
@admin.register(Recipe)
class RecipeAdmin(AdminSuggestMixin, admin.ModelAdmin):

    class ShowFilter(admin.SimpleListFilter):
        """Affichage: principales / toutes / sous-recettes."""
        title = "Affichage"
        parameter_name = "show"
        def lookups(self, request, model_admin):
            return (("main", "Recettes principales"), ("all", "Toutes"), ("sub", "Sous-recettes"))
        def queryset(self, request, queryset):
            used_ids = SubRecipe.objects.values_list("sub_recipe_id", flat=True)
            v = self.value()
            if v == "all":
                return Recipe.objects.all()
            if v == "sub":
                return Recipe.objects.filter(id__in=used_ids)
            if v == "main":
                return Recipe.objects.exclude(id__in=used_ids)
            return queryset  # laisse get_queryset décider

    # ---- Filtre Labels restreint (type recipe|both) ----
    class _LabelForRecipeFilter(RelatedOnlyFieldListFilter):
        """Filtre 'labels' restreint à label_type in (recipe, both)."""
        def field_choices(self, field, request, model_admin):
            qs = Label.objects.filter(label_type__in=["recipe", "both"])
            return [(l.pk, str(l)) for l in qs]

    category_allowed_types = ("recipe", "both")
    inlines = [RecipeCategoryInline, RecipeLabelInline, RecipeIngredientInline, RecipeStepInline, SubRecipeInline]
    list_display = ('recipe_name', 'id', 'chef_name', 'context_name', 'parent_recipe', 'display_tags', 'visibility', 'is_default')
    list_filter = (ShowFilter, 'recipe_type', CategoryDrilldownFilter, ("labels", _LabelForRecipeFilter), 'visibility')
    search_fields = ('recipe_name', 'categories__category_name', 'labels__label_name')
    readonly_fields = ['recipe_subrecipes_synthesis']
    form = RecipeAdminForm

    class Media:
        css = {'all': ('pastry_app/admin/required_fields.css',
                       'pastry_app/admin/recipe_admin.css', 
                       'pastry_app/admin/tagify.css')}
        js = ('pastry_app/admin/tagify.min.js',
              'pastry_app/admin/recipe_admin.js', 
              'pastry_app/admin/recipe_adjustment_admin.js',
              'pastry_app/admin/search_suggest.js',)
    
    fieldsets = (
        (None, {'fields': ('mode_ajustement',)}),
        ('Synthèse', {
            'fields': ('recipe_subrecipes_synthesis',),
            'classes': ('hide-label',),
            'description': "Vue synthétique ingrédients et étapes (recette + sous-recettes)."
        }),
        ('Caractéristiques principales de la recette', {
            'fields': ('recipe_type', 'recipe_name', 'chef_name', 'parent_recipe', 'version_note',
                       'servings_min', 'servings_max', 'pan', 'pan_quantity', 'total_recipe_quantity')
        }),
        ('Contenu', {
            'fields': ('description', 'trick', 'image', 'tags')
        }),
        ('Source de la recette', {
            'fields': ('context_name', 'source')
        }),
        ('Gestion / Droits', {
            'fields': ('visibility', 'is_default', 'user', 'guest_id'),
            'description': "Champs relatifs à la visibilité, aux droits, ou à la gestion multi-utilisateur."
        }),
    )

    @admin.display(description="Tags")
    def display_tags(self, obj):
        """
        Affiche la liste des tags de façon lisible, même si le champ tags contient des données sérialisées de façon incohérente 
        (ex : liste de JSON stringifiés).
        Cette fonction tente d'afficher uniquement les valeurs de tags, quel que soit le format présent en base.
        """
        # obj.tags peut être :
        # - une liste de chaînes JSON (["[{\"value\":\"foo\"}]"])
        # - une liste de chaînes simples (["foo", "bar"])
        # On essaie de parser la première valeur comme JSON
        if isinstance(obj.tags, list) and obj.tags:
            first_value = obj.tags[0]
            try:
                # Si c'est une string JSON, on la parse
                tags_list = json.loads(first_value)
                # Si c'est une liste de dicts [{"value": "foo"}, ...]
                if isinstance(tags_list, list) and tags_list and isinstance(tags_list[0], dict):
                    return ", ".join(tag.get("value", "") for tag in tags_list)
            except Exception:
                # Sinon, on considère que c'est une liste plate de strings
                return ", ".join(obj.tags)
        return ""

    def recipe_subrecipes_synthesis(self, obj):
        html = "<div class='recipe-columns-container'>"

        # Main recipe (always first column)
        html += """
        <div class='recipe-card'>
        <h3 class='main-title'>Main recipe</h3>
        <b>Ingredients:</b>
        <ul>
        """
        for ri in obj.recipe_ingredients.all():
            html += f"<li>{ri.quantity} {ri.unit} of <b>{ri.ingredient}</b></li>"
        html += "</ul><b>Steps:</b><ol>"
        for step in obj.steps.all().order_by('step_number'):
            html += f"<li>{step.instruction}</li>"
        html += "</ol></div>"

        # Subrecipes (one column per subrecipe)
        for sub in obj.main_recipes.all():
            html += f"""
            <div class='recipe-card'>
                <h4 class='sub-title'>Sub-recipe: {sub.sub_recipe.recipe_name}</h4>
                <b>Ingredients:</b>
                <ul>
            """
            for ri in sub.sub_recipe.recipe_ingredients.all():
                html += f"<li>{ri.quantity} {ri.unit} of <b>{ri.ingredient}</b></li>"
            html += "</ul><b>Steps:</b><ol>"
            for step in sub.sub_recipe.steps.all().order_by('step_number'):
                html += f"<li>{step.instruction}</li>"
            html += "</ol></div>"

        html += "</div>"  # end of flex container

        return mark_safe(html)
    recipe_subrecipes_synthesis.short_description = ""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """
        Ajuste la taille (hauteur/largeur) des champs texte 'description' et 'trick', 
        pour avoir des champs moins envahissants et un rendu plus agréable.
        """
        if db_field.name == "description":
            kwargs["widget"] = forms.Textarea(attrs={"rows": 2, "cols": 60})
        if db_field.name == "trick":
            kwargs["widget"] = forms.Textarea(attrs={"rows": 1, "cols": 60})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        """ Empêche la modification du champ 'is_default' par les utilisateurs non-admin dans l'interface admin. """
        ro_fields = super().get_readonly_fields(request, obj)
        if not request.user.is_staff:
            return ro_fields + ('is_default',)
        return ro_fields

    # Pour afficher toute la liste sans chercher: ajoute ?show=all à l’URL.
    def get_queryset(self, request):
        """
        Changelist: masque les recettes utilisées comme sous-recettes.
        Change view (objet précis): ne filtre pas, sinon 404.
        ?show=all => affiche tout.
        La recherche est gérée dans get_search_results.
        """
        qs = super().get_queryset(request)

        # 1) Change view / History / Delete confirm → ne pas filtrer
        rm = getattr(request, "resolver_match", None)
        if rm and rm.kwargs.get("object_id"):
            return qs  # important: pas d’exclude ici

        # 2) Forcer l’affichage complet via ?show=all
        if request.GET.get("show") == "all":
            return qs

        # 3) Changelist par défaut: masquer les sous-recettes
        used_ids = SubRecipe.objects.values_list("sub_recipe_id", flat=True)
        return qs.exclude(id__in=used_ids)

    def get_search_results(self, request, queryset, search_term):
        """
        Recherche sur TOUTES les recettes, même celles filtrées par get_queryset.
        Ainsi « pâte sucrée » apparaît en résultats même si masquée par défaut.
        """
        if search_term:
            base = Recipe.objects.all()
            return super().get_search_results(request, base, search_term)
        return super().get_search_results(request, queryset, search_term)

    def save_related(self, request, form, formsets, change):
        """
        Valide les contraintes “au moins un ingrédient/sous-recette” après sauvegarde.
        Évite l’écran jaune admin et affiche une erreur claire à l’utilisateur.
        Nécessaire car l’admin ne gère pas ces règles lors de la création.
        """
        super().save_related(request, form, formsets, change)
        recipe = form.instance

        try :
            # On vérifie la présence d'au moins un ingrédient ou une sous-recette
            has_ingredients = recipe.recipe_ingredients.exists()
            has_subrecipes = recipe.main_recipes.exists()
            has_steps = recipe.steps.exists()
            if not (has_ingredients or has_subrecipes):
                raise ValidationError("Une recette doit contenir au moins un ingrédient ou une sous-recette.")
            if not has_steps:
                raise ValidationError("Une recette doit contenir au moins une étape.")
        except ValidationError as e:
            # Cas création (recette pas encore en BDD avant cette transaction)
            if recipe._state.adding:
                recipe.delete()
                self.message_user(request, str(e), level=messages.ERROR)
                # Ne pas raise: force le redirect à la liste
            else:
                # Cas édition, on ne supprime pas !
                raise

class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ('recipe_name', 'ingredient_name', 'id')
    readonly_fields = ['display_name'] 

    def recipe_name(self, obj):
        return obj.recipe.recipe_name
    recipe_name.short_description = 'Recipe Name'  # Sets column name in admin site

    def ingredient_name(self, obj):
        return obj.ingredient.ingredient_name
    ingredient_name.short_description = 'Ingredient Name'  # Sets column name in admin site

@admin.register(RecipeStep)
class RecipeStepAdmin(AdminSuggestMixin, admin.ModelAdmin):

    list_display = ('recipe_name', 'id', 'step_number')
    search_fields = ('recipe__recipe_name',)
    list_select_related = ('recipe',) 
    list_filter = ('recipe__recipe_name',)

    class Media:
        css = {'all': ('pastry_app/admin/required_fields.css',)}
        js = ('pastry_app/admin/search_suggest.js',)

    def recipe_name(self, obj):
        return obj.recipe.recipe_name
    recipe_name.short_description = 'Recipe Name'

    def get_form(self, request, obj=None, **kwargs):
        """ Rend le champ step_number obligatoire en modification, mais facultatif en création. """
        form = super().get_form(request, obj, **kwargs)
        original_init = form.__init__
        def custom_init(form_self, *a, **kw):
            original_init(form_self, *a, **kw)
            if obj:  # update
                form_self.fields["step_number"].required = True
            else:
                form_self.fields["step_number"].required = False
        form.__init__ = custom_init
        return form

    def delete_view(self, request, object_id, extra_context=None):
        """
        Empêche la suppression du dernier step, affiche une erreur UX-friendly,
        et évite l'écran jaune.
        """
        obj = self.get_object(request, object_id)
        if obj:
            total_steps = RecipeStep.objects.filter(recipe=obj.recipe).count()
            if total_steps == 1:
                self.message_user(request, "❌ Une recette doit avoir au moins une étape.", level=messages.ERROR)
                return redirect(request.META.get('HTTP_REFERER', '/admin/pastry_app/recipestep/'))
        return super().delete_view(request, object_id, extra_context)

    def get_actions(self, request):
        """ Déscactive l'action de suppression en masse pour éviter l'écran jaune d'erreur. """
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

@admin.register(SubRecipe)
class SubRecipeAdmin(AdminSuggestMixin, admin.ModelAdmin):
    list_display = ('subrecipe_name', 'recipe_name', 'id')
    search_fields = ('recipe__recipe_name', 'sub_recipe__recipe_name')
    list_select_related = ('recipe', 'sub_recipe')  # Perf: évite des JOINs supplémentaires

    class Media:
        js = ('pastry_app/admin/search_suggest.js',)

    def recipe_name(self, obj):
        return obj.recipe.recipe_name
    recipe_name.short_description = 'Recipe Name'

    def subrecipe_name(self, obj):
        return obj.sub_recipe.recipe_name
    subrecipe_name.short_description = 'Subrecipe Name'

@admin.register(IngredientUnitReference)
class IngredientUnitReferenceAdmin(AdminSuggestMixin, admin.ModelAdmin):
    list_display = ('ingredient', 'unit', 'weight_in_grams', 'notes', 'is_hidden', "provenance")
    list_filter = (('unit', admin.AllValuesFieldListFilter), ('ingredient', admin.RelatedOnlyFieldListFilter), 'is_hidden')  # ne liste que les unit et ingrédients présents dans IUR
    search_fields = ('ingredient__ingredient_name', 'unit', 'notes')
    autocomplete_fields = ['ingredient']
    ordering = ('ingredient', 'unit')
    actions = ["run_iur_loader"]

    class Media:
        js = ('pastry_app/admin/search_suggest.js',)

    # La colonne Provenance s’appuie sur notes. Adapte si besoin
    def provenance(self, obj):
        """Indique si la ligne vient du loader (heuristique via notes)."""
        n = (obj.notes or "").lower()
        return "loader" if ("default" in n or "rui" in n or "forme" in n) else ""
    provenance.short_description = "Provenance"

    def run_iur_loader(self, request, queryset):
        """
        Lance load_base_ingredientUnitReference.py dans un sous-processus.
        Affiche le delta de lignes après exécution.
        """
        script = Path(settings.BASE_DIR) / "pastry_app" / "fixtures" / "load_base_ingredientUnitReference.py"
        if not script.exists():
            self.message_user(request, f"Script introuvable: {script}", level="error")
            return

        env = os.environ.copy()
        # propage le settings module actif à l’enfant
        env["DJANGO_SETTINGS_MODULE"] = env.get("DJANGO_SETTINGS_MODULE", "settings")

        before = IngredientUnitReference.objects.count()
        proc = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            self.message_user(request, f"Erreur loader: {proc.stderr.strip()}", level="error")
            return

        after = IngredientUnitReference.objects.count()
        msg = f"Références chargées (+{after - before})."
        if proc.stdout:
            msg += f" Log: {proc.stdout.splitlines()[-1][:200]}"
        self.message_user(request, msg)    
    run_iur_loader.short_description = "Charger/mettre à jour via load_base_ingredientUnitReference.py"
