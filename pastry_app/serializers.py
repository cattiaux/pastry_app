from rest_framework import serializers
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError
from django.db.models import Max
from django.utils.timezone import now
from .models import *
from .constants import UNIT_CHOICES, SUBRECIPE_UNIT_CHOICES
from .text_utils import normalize_case


class StoreSerializer(serializers.ModelSerializer):
    """ Sérialise les magasins où sont vendus les ingrédients. """
    store_name = serializers.CharField(
        required=True,  # Champ obligatoire
        allow_blank=False,  # Interdit ""
        error_messages={"blank": "This field cannot be blank.", "required": "This field is required.", "null": "This field may not be null."}
    )
    city = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    zip_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)   
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True, 
                                    help_text="Optionnel : précisez la rue ou le quartier pour différencier deux magasins identiques dans la même ville.")
 

    # Utilisateur et visibilité
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    guest_id = serializers.CharField(read_only=True)
    visibility = serializers.ChoiceField(choices=[('private', 'Privée'), ('public', 'Publique')], required=False, default='private')
    is_default = serializers.BooleanField(read_only=True)

    class Meta:
        model = Store
        fields = ["id", "store_name", "city", "zip_code", "address", "user", "guest_id", "visibility", "is_default"]

    def validate_store_name(self, value):
        """ Normalisation et validation du nom du magasin. """
        value = normalize_case(value) if value else value
        if len(value) < 2:
            raise serializers.ValidationError("Le nom du magasin doit contenir au moins 2 caractères.")
        return value

    def validate_city(self, value):
        """ Normalisation + Vérifie que la ville a au moins 2 caractères """
        if not value:  # Gérer None et les valeurs vides
            return value  # Laisser DRF gérer l'erreur si nécessaire

        value = normalize_case(value)  # Maintenant, on est sûr que value n'est pas None
        if len(value) < 2:
            raise serializers.ValidationError("Le nom de la ville doit contenir au moins 2 caractères.")
        return value

    def validate_address(self, value):
        """ Normalisation + Vérifie que l'adresse a au moins 2 caractères """
        if not value:  # Gérer None et les valeurs vides
            return value  # Laisser DRF gérer l'erreur si nécessaire

        value = normalize_case(value)  # Maintenant, on est sûr que value n'est pas None
        if len(value) < 2:
            raise serializers.ValidationError("L'adresse doit contenir au moins 2 caractères.")
        return value

    def validate(self, data):
        """
        Vérifie, lors de la création ou de la mise à jour d'un Store :
        - Qu'au moins une ville (`city`), un code postal (`zip_code`) ou une addresse (`address`) est renseigné,
        - Que le magasin (défini par le tuple `store_name`, `city`, `zip_code`, `address`) n'existe pas déjà en base.
        La validation s'applique aussi bien en création (POST) qu'en modification partielle ou complète (PATCH/PUT).
        """        
        # Récupérer les valeurs actuelles (instance) si absentes de data (cas PATCH)
        store_name = data.get("store_name", getattr(self.instance, "store_name", ""))
        city = data.get("city", getattr(self.instance, "city", ""))
        zip_code = data.get("zip_code", getattr(self.instance, "zip_code", ""))
        address = data.get("address", getattr(self.instance, "address", ""))

        # Appliquer la normalisation car le champ PATCH peut ne pas passer par validate_<field>
        store_name = normalize_case(store_name) if store_name else ""
        city = normalize_case(city) if city else ""
        address = normalize_case(address) if address else ""

        # Validation métier : il faut au moins une city OU un zip_code OU une address
        if not city and not zip_code and not address:
            raise serializers.ValidationError(
                "Si un magasin est renseigné, vous devez indiquer une ville ou un code postal ou une adresse.",
                code="missing_location")

        # Vérification de l'unicité, même pour PATCH (mise à jour partielle)
        qs = Store.objects.filter(store_name=store_name, city=city, zip_code=zip_code, address=address)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("Ce magasin existe déjà.")
        
        return data

class IngredientPriceSerializer(serializers.ModelSerializer):
    ingredient = serializers.SlugRelatedField(queryset=Ingredient.objects.all(), slug_field="ingredient_name")
    store = serializers.PrimaryKeyRelatedField(required=False, queryset=Store.objects.all(), default=None)
    date = serializers.DateField(required=False, default=now().date, input_formats=['%Y-%m-%d'])
    brand_name = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None) 

    class Meta:
        model = IngredientPrice
        fields = ['id', 'ingredient', 'brand_name', 'store', 'date', 'quantity', 'unit', 'price', "is_promo", "promotion_end_date"]
    
    def validate_quantity(self, value):
        """ S'assure que `quantity` est un float valide et vérifie que la quantité est strictement positive"""
        try:
            value = float(value)
        except ValueError:
            raise serializers.ValidationError("Quantity must be a positive number.")

        if value <= 0:
            raise serializers.ValidationError("Quantity must be a positive number.")
        return value

    def validate_price(self, value):
        """ Vérifie que le prix est strictement positif. """
        if value <= 0:
            raise serializers.ValidationError("Price must be a positive number.")
        return value

    def validate_date(self, value):
        """ Vérifie que la date n'est pas dans le futur. """
        if value and value > now().date():
            raise serializers.ValidationError("La date ne peut pas être dans le futur.")
        return value

    def validate_store(self, value):
        """ Vérifie que le magasin existe bien avant de l'associer à un prix"""
        if value and not Store.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Le magasin sélectionné n'existe pas en base. Veuillez le créer avant d'ajouter un prix.")
        return value
    
    def validate_brand_name(self, value):
        """ Normalisation + Vérifie que le nom de marque a au moins 2 caractères """
        if not value: 
            return ""  
        
        value = normalize_case(value)  # Maintenant, on est sûr que value n'est pas None
        if len(value) < 2:
            raise serializers.ValidationError("Le nom de la marque doit contenir au moins 2 caractères.")
        return value

    def validate(self, data):
        """ 
        Vérifie les contraintes métier (promotions, cohérence des données, etc.). 
        1. Lors de la création :
           - Si tuple existe déjà → erreur.
        2. Lors de l’update :
           - Interdit de modifier un champ du tuple unique.
        """
        promotion_end_date = data.get("promotion_end_date", getattr(self.instance, "promotion_end_date", None))
        is_promo = data.get("is_promo", getattr(self.instance, "is_promo", False))

        if promotion_end_date and not is_promo:
            raise serializers.ValidationError("Une date de fin de promotion nécessite que `is_promo=True`.")
        
        # Permettre à `date` d'être optionnel.
        if "date" not in data:
            data["date"] = now().date()  # Assigner automatiquement la date du jour

        instance = self.instance
        ### Validation personnalisée pour gérer l'unicité sans bloquer DRF.
        # Récupérer les champs qui définissent l’unicité
        ingredient = data.get("ingredient", getattr(instance, "ingredient", None))
        store = data.get("store", getattr(instance, "store", None))
        brand_name = data.get("brand_name", getattr(instance, "brand_name", None))
        quantity = data.get("quantity", getattr(instance, "quantity", None))
        unit = data.get("unit", getattr(instance, "unit", None))

        # Vérifie le tuple unique pour une création
        if instance is None:
            # Create : on refuse si le tuple existe déjà
            if IngredientPrice.objects.filter(ingredient=ingredient, store=store, brand_name=brand_name, quantity=quantity, unit=unit).exists():
                raise serializers.ValidationError(
                    "must make a unique set. Un prix existe déjà pour cet ingrédient, ce magasin, cette marque, cette quantité et cette unité. Faites une mise à jour plutôt."
                )
        else:
            # Update : on refuse si le tuple change
            fields = ["ingredient", "store", "brand_name", "quantity", "unit"]
            for field in fields:
                old = getattr(instance, field)
                new = data.get(field, old)
                if old != new:
                    raise serializers.ValidationError(f"Le champ {field} ne peut pas être modifié. Créez un nouvel IngredientPrice si besoin.")
        return data

    def update(self, instance, validated_data):
        """
        - Applique les changements sur l’instance
        - L’archivage est totalement délégué au modèle (via .save())
        """
        # Interdiction de modification du tuple unique (métier)
        tuple_fields = ["ingredient", "store", "brand_name", "quantity", "unit"]
        for field in tuple_fields:
            old_value = getattr(instance, field)
            new_value = validated_data.get(field, old_value)
            if old_value != new_value:
                raise serializers.ValidationError(
                    f"Le champ '{field}' ne peut pas être modifié. Créez un nouveau IngredientPrice pour un nouveau tuple unique.")
        # Suite : appliquer les modifs “soft”
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()   # Toute la logique d’archivage est dans le modèle !

        return instance

class IngredientPriceHistorySerializer(serializers.ModelSerializer):
    """ Gère la validation et la sérialisation de l'historique des prix d'ingrédients. """

    class Meta:
        model = IngredientPriceHistory
        fields = ['id', 'ingredient', 'ingredient_name', 'brand_name', 'store', 'date', 'quantity', 'unit', 'price', "is_promo", "promotion_end_date"]
        read_only_fields = fields  # Empêche toute modification via l'API
    
class CategorySerializer(serializers.ModelSerializer):
    parent_category = serializers.SlugRelatedField(queryset=Category.objects.all(), slug_field="category_name", allow_null=True, required=False)

    class Meta:
        model = Category
        fields = ['id', 'category_name', 'category_type', 'parent_category']

    def to_internal_value(self, data):
        """ Normalise AVANT validation. """
        data = data.copy()  # Rend le QueryDict mutable

        if "category_name" in data:
            data["category_name"] = normalize_case(data["category_name"])
        if "category_type" in data:
            data["category_type"] = normalize_case(data["category_type"])
        if "parent_category" in data and isinstance(data["parent_category"], str):
            data["parent_category"] = normalize_case(data["parent_category"]) 
        return super().to_internal_value(data)

    def validate_category_name(self, value):
        """ Vérifie que 'category_name' existe en base et empêche les utilisateurs non-admins d'ajouter des catégories. """
        request = self.context.get("request")
        
        # Vérifie si la catégorie existe déjà en base
        category_exists = Category.objects.exclude(id=self.instance.id if self.instance else None).filter(category_name__iexact=value).exists()
        if category_exists:
            raise serializers.ValidationError("Une catégorie avec ce nom existe déjà.")

        # Seuls les admins peuvent ajouter de nouvelles catégories
        if not request.user.is_staff and not category_exists:
            raise serializers.ValidationError("Vous ne pouvez choisir qu'une catégorie existante.")

        return value

    def validate_category_type(self, value):
        """ Vérifie que `category_type` est dans les choix valides. """
        valid_choices = dict(Category.CATEGORY_CHOICES).keys()
        if value not in valid_choices:
            raise serializers.ValidationError(f"`category_type` doit être l'une des valeurs suivantes : {', '.join(valid_choices)}.")
        return value

    def validate(self, data):
        """
        - Une catégorie 'ingredient' ne peut avoir pour parent qu'une catégorie 'ingredient' ou 'both' ou rien.
        - Une catégorie 'recipe' ne peut avoir pour parent qu'une catégorie 'recipe' ou 'both' ou rien.
        - Une catégorie 'both' ne peut avoir pour parent qu'une catégorie 'both' ou rien.
        """
        parent = data.get('parent_category') or getattr(self.instance, 'parent_category', None)
        category_type = data.get('category_type') or getattr(self.instance, 'category_type', None)
        if parent:
            parent_type = parent.category_type
            if category_type == "both" and parent_type != "both":
                raise serializers.ValidationError("Une catégorie 'both' ne peut avoir qu'une catégorie parente 'both' ou aucune.")
            if category_type in ("ingredient", "recipe") and parent_type not in (category_type, "both"):
                raise serializers.ValidationError(
                    f"Une catégorie '{category_type}' ne peut avoir pour parent qu'une catégorie '{category_type}' ou 'both', jamais '{parent_type}'."
                )
        return data

    def create(self, validated_data):
        """ Seuls les admins peuvent créer une catégorie. """
        request = self.context.get("request")
        if not request.user.is_staff:
            raise serializers.ValidationError("Seuls les administrateurs peuvent créer des catégories.")

        try:
            return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError({"category_name": "Cette catégorie existe déjà."})

    def update(self, instance, validated_data):
        # Seuls les admins peuvent modifier une catégorie.
        request = self.context.get("request")
        if not request.user.is_staff:
            raise serializers.ValidationError("Seuls les administrateurs peuvent modifier une catégorie.")

        # Empêche la modification de `category_name` vers un nom déjà existant.
        new_name = validated_data.get("category_name", instance.category_name)
        if normalize_case(new_name) != normalize_case(instance.category_name):
            if Category.objects.exclude(id=instance.id).filter(category_name__iexact=new_name).exists():
                raise serializers.ValidationError({"category_name": "Une catégorie avec ce nom existe déjà."})

        return super().update(instance, validated_data)

class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ['id', 'label_name', 'label_type']

    def to_internal_value(self, data):
        """ Normalise AVANT validation. """
        data = data.copy()  # Rend le QueryDict mutable

        if "label_name" in data:
            data["label_name"] = normalize_case(data["label_name"])
        if "label_type" in data:
            data["label_type"] = normalize_case(data["label_type"])
        return super().to_internal_value(data)

    def validate_label_name(self, value):
        """ Vérifie que 'label_name' existe en base et empêche les utilisateurs non-admins d'ajouter des labels. """
        request = self.context.get("request")
        
        # Vérifie si la catégorie existe déjà en base
        label_exists = Label.objects.exclude(id=self.instance.id if self.instance else None).filter(label_name__iexact=value).exists()
        if label_exists:
            raise serializers.ValidationError("Un label avec ce nom existe déjà.")

        # Seuls les admins peuvent ajouter de nouveaux labels
        if not request.user.is_staff and not label_exists:
            raise serializers.ValidationError("Vous ne pouvez choisir qu'un label existant.")

        return value

    def validate_label_type(self, value):
        """ Vérifie que `label_type` est dans les choix valides. """
        valid_choices = dict(Label.LABEL_CHOICES).keys()
        if value not in valid_choices:
            raise serializers.ValidationError(f"`label_type` doit être l'une des valeurs suivantes : {', '.join(valid_choices)}.")
        return value

    def create(self, validated_data):
        """ Seuls les admins peuvent créer un label. """
        request = self.context.get("request")
        if not request.user.is_staff:
            raise serializers.ValidationError("Seuls les administrateurs peuvent créer des labels.")

        try:
            return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError({"label_name": "Ce label existe déjà."})

    def update(self, instance, validated_data):
        # Seuls les admins peuvent modifier un label.
        request = self.context.get("request")
        if not request.user.is_staff:
            raise serializers.ValidationError("Seuls les administrateurs peuvent modifier un label.")

        # Empêche la modification de `label_name` vers un nom déjà existant.
        new_name = validated_data.get("label_name", instance.label_name)
        if normalize_case(new_name) != normalize_case(instance.label_name):
            if Label.objects.exclude(id=instance.id).filter(label_name=new_name).exists():
                raise serializers.ValidationError({"label_name": "Un label avec ce nom existe déjà."})

        return super().update(instance, validated_data)

class IngredientSerializer(serializers.ModelSerializer):
    prices = IngredientPriceSerializer(many=True, read_only=True)
    categories = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), many=True, required=False) #PrimaryKeyRelatedField assure la vérification de l'existence de la category par DRF
    labels = serializers.PrimaryKeyRelatedField(queryset=Label.objects.all(), many=True, required=False)

    # Utilisateur et visibilité
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    guest_id = serializers.CharField(read_only=True)
    visibility = serializers.ChoiceField(choices=[('private', 'Privée'), ('public', 'Publique')], required=False, default='private')
    is_default = serializers.BooleanField(read_only=True)

    class Meta:
        model = Ingredient
        fields = ['id', 'ingredient_name', 'categories', 'labels', 'prices', "user", "guest_id", "visibility", "is_default"]
    
    def validate_ingredient_name(self, value):
        """ Vérifie que l'ingrédient n'existe pas déjà (insensible à la casse), sauf s'il s'agit de la mise à jour du même ingrédient. """
        value = normalize_case(value)  # Normalisation : minuscule + suppression espaces inutiles

        ingredient_id = self.instance.id if self.instance else None  # Exclure l'ID courant en cas de mise à jour
        if Ingredient.objects.exclude(id=ingredient_id).filter(ingredient_name__iexact=value).exists():
            raise serializers.ValidationError("Un ingrédient avec ce nom existe déjà.")
        return value

    def validate_categories(self, value):
        """
        Vérifie :
        - Que toutes les catégories existent en base (par ID)
        - Que leur type est bien 'ingredient' ou 'both'
        """
        existing_categories_ids = set(Category.objects.values_list("id", flat=True))
        for category in value:
            if category.id not in existing_categories_ids:
                raise serializers.ValidationError(f"La catégorie '{category.category_name}' n'existe pas. Veuillez la créer d'abord.")
            # Vérification sur le type de catégorie
            if category.category_type not in ("ingredient", "both"):
                raise serializers.ValidationError(f"La catégorie '{category.category_name}' (type '{category.category_type}') n'est pas valide pour un ingrédient.")
        return value

    def validate_labels(self, value):
        """
        Vérifie :
        - Que tous les labels existent en base (par ID)
        - Que leur type est bien 'ingredient' ou 'both'
        """
        existing_labels_ids = set(Label.objects.values_list("id", flat=True))
        for label in value:
            if label.id not in existing_labels_ids:
                raise serializers.ValidationError(f"Le label '{label.label_name}' n'existe pas. Veuillez le créer d'abord.")
            # Vérification sur le type de label
            if label.label_type not in ("ingredient", "both"):
                raise serializers.ValidationError(f"Le label '{label.label_name}' (type '{label.label_type}') n'est pas valide pour un ingrédient.")
        return value

    def validate(self, data):
        """ Permet de ne pas valider les champs absents dans le cas d'un PATCH. """
        if self.partial:
            return data
        return data

    def to_representation(self, instance):
        """ Assure que l'affichage dans l'API est bien normalisé """
        representation = super().to_representation(instance)
        representation["ingredient_name"] = normalize_case(representation["ingredient_name"])
        return representation

class RecipeIngredientSerializer(serializers.ModelSerializer):
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all(), required=False)
    ingredient = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    unit = serializers.ChoiceField(choices=UNIT_CHOICES)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = RecipeIngredient
        fields = ['id', 'recipe', 'ingredient', 'quantity', 'unit', 'display_name']
        extra_kwargs = {"recipe": {"read_only": True},}  # Une fois l'ingrédient ajouté à une recette, il ne peut pas être déplacé

    def get_fields(self):
        """Rend recipe optionnel via URL imbriquée."""
        fields = super().get_fields()

        # Cas de contexte parent serializer → suppression complète du champ
        if self.context.get("is_nested", False):
            fields.pop("recipe", None)
        # Cas endpoint imbriqué (ex: /recipes/<id>/steps/)
        elif "view" in self.context:
            view = self.context["view"]
            if hasattr(view, "kwargs") and "recipe_pk" in view.kwargs:
                fields["recipe"].required = False

        return fields

    def run_validation(self, data=serializers.empty):
        """Injecte recipe depuis l’URL."""
        view = self.context.get("view")
        if view and hasattr(view, "kwargs") and "recipe_pk" in view.kwargs:
            data = data.copy()
            data["recipe"] = view.kwargs["recipe_pk"]

        result = super().run_validation(data)
        return result

    def validate_quantity(self, value):
        """ Vérifie que la quantité est strictement positive. """
        if value <= 0:
            raise serializers.ValidationError("Quantity must be a positive number.")
        return value

    def validate(self, data):
        """ Vérifie que l’ingrédient, la quantité et l’unité sont bien présents (sauf en PATCH). """
        request = self.context.get("request", None)
        is_partial = request and request.method == "PATCH"  # Vérifie si c'est un PATCH

        if not is_partial:  # Ne pas exiger tous les champs en PATCH
            if "ingredient" not in data:
                raise serializers.ValidationError({"ingredient": "Un ingrédient est obligatoire."})
            if "quantity" not in data:
                raise serializers.ValidationError({"quantity": "Une quantité est obligatoire."})
            if "unit" not in data:
                raise serializers.ValidationError({"unit": "Une unité de mesure est obligatoire."})
            
        return data
    
class RecipeStepSerializer(serializers.ModelSerializer):
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())
    step_number = serializers.IntegerField(default=None, min_value=1)

    class Meta:
        model = RecipeStep
        fields = ['id', 'recipe', 'step_number', 'instruction', 'trick']

    def get_fields(self):
        """Rend recipe optionnel via URL imbriquée."""
        fields = super().get_fields()

        # Cas de contexte parent serializer → suppression complète du champ
        if self.context.get("is_nested", False):
            fields.pop("recipe", None)
        # Cas endpoint imbriqué (ex: /recipes/<id>/steps/)
        elif "view" in self.context:
            view = self.context["view"]
            if hasattr(view, "kwargs") and "recipe_pk" in view.kwargs:
                fields["recipe"].required = False

        return fields

    def run_validation(self, data=serializers.empty):
        """Injecte recipe depuis l’URL."""
        view = self.context.get("view")
        if view and hasattr(view, "kwargs") and "recipe_pk" in view.kwargs:
            data = data.copy()
            data["recipe"] = view.kwargs["recipe_pk"]

        result = super().run_validation(data)
        return result

    def validate_instruction(self, value):
        """ Vérifie que l'instruction contient au moins 5 caractères. """
        if len(value) < 5:
            raise serializers.ValidationError("L'instruction doit contenir au moins 5 caractères.")
        return value

    def validate(self, data):
        """
        - Vérifie que si il n'y a qu'une seule étape pour la recette, `step_number` doit être 1.
        - Vérifie que `step_number` est consécutif.
        - Vérifie qu'il n'y a pas déjà une étape avec ce numéro pour cette recette (unicité recipe/step_number).
        """
        recipe = data.get("recipe", getattr(self.instance, "recipe", None))
        step_number = data.get("step_number", getattr(self.instance, "step_number", None))

        # Si c'est le seul RecipeStep pour la recette, step_number doit être 1
        if recipe is not None and step_number is not None:
            count_other = RecipeStep.objects.filter(recipe=recipe).exclude(pk=getattr(self.instance, 'pk', None)).count()
            if count_other == 0 and step_number != 1:
                raise serializers.ValidationError({"step_number": "S'il n'y a qu'une seule étape, son numéro doit être 1."})

        if recipe and step_number is not None:
            # Unicité : interdit de dupliquer une étape
            qs = RecipeStep.objects.filter(recipe=recipe, step_number=step_number)
            # Si c'est un update, on exclut l'instance en cours
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"step_number": "Ce numéro d'étape existe déjà pour cette recette."})

            # Consécutivité
            last_step = RecipeStep.objects.filter(recipe=recipe).aggregate(Max("step_number"))["step_number__max"]
            if last_step is not None and step_number > last_step + 1:
                raise serializers.ValidationError({"step_number": "Step numbers must be consecutive."})

        return data
    
    def create(self, validated_data):
        """ Gère la création d'un `RecipeStep` en attribuant `step_number` automatiquement si nécessaire. """
        # Auto-incrément de `step_number` si non fourni ou None
        if validated_data.get("step_number") is None:
            max_step = RecipeStep.objects.filter(recipe=validated_data.get("recipe")).aggregate(Max("step_number"))["step_number__max"]
            validated_data["step_number"] = 1 if max_step is None else max_step + 1

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """ Gère la mise à jour d'un `RecipeStep` en vérifiant que `step_number` est fourni. """
        # Si step_number est explicitement fourni (dans la requête), il ne doit pas être null
        if "step_number" in validated_data and validated_data.get("step_number") is None:
            raise serializers.ValidationError("Le numéro d'étape est obligatoire en modification.")
        return super().update(instance, validated_data)

class SubRecipeSerializer(serializers.ModelSerializer):
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all(), required=False)
    sub_recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())
    unit = serializers.ChoiceField(choices=SUBRECIPE_UNIT_CHOICES)

    class Meta:
        model = SubRecipe
        fields = ["id", "recipe", "sub_recipe", "quantity", "unit"]
        extra_kwargs = {"recipe": {"read_only": True},}  # La recette principale ne peut pas être modifiée

    def get_fields(self):
        """Rend recipe optionnel via URL imbriquée."""
        fields = super().get_fields()

        # Cas de contexte parent serializer → suppression complète du champ
        if self.context.get("is_nested", False):
            fields.pop("recipe", None)
        # Cas endpoint imbriqué (ex: /recipes/<id>/steps/)
        elif "view" in self.context:
            view = self.context["view"]
            if hasattr(view, "kwargs") and "recipe_pk" in view.kwargs:
                fields["recipe"].required = False

        return fields

    def run_validation(self, data=serializers.empty):
        """Injecte recipe depuis l’URL."""
        view = self.context.get("view")
        if view and hasattr(view, "kwargs") and "recipe_pk" in view.kwargs:
            data = data.copy()
            data["recipe"] = view.kwargs["recipe_pk"]

        result = super().run_validation(data)
        return result

    def validate_sub_recipe(self, value):
        """ Vérifie qu'une recette ne peut pas être sa propre sous-recette """
        if self.instance and self.instance.recipe == value:
            raise serializers.ValidationError("Une recette ne peut pas être sa propre sous-recette.")
        return value

    def validate_quantity(self, value):
        """ Vérifie que la quantité est strictement positive """
        if value <= 0:
            raise serializers.ValidationError("La quantité doit être strictement positive.")
        return value

    def validate(self, data):
        """ 
        Vérifie des règles métier :
        1. Une recette ne peut pas être sa propre sous-recette.
        2. Le champ `recipe` ne peut pas être modifié après création.
        """
        recipe = data.get("recipe", getattr(self.instance, "recipe", None))
        sub_recipe = data.get("sub_recipe", getattr(self.instance, "sub_recipe", None))
        quantity = data.get("quantity", getattr(self.instance, "quantity", None))
        unit = data.get("unit", getattr(self.instance, "unit", None))

        # quantité et unité sont obligatoires
        if quantity is None or quantity < 0 :
            raise serializers.ValidationError({"quantity": "La quantité est obligatoire et doit être positive."})
        if unit is None or unit == "":
            raise serializers.ValidationError({"unit": "L'unité de mesure est obligatoire."})

        # Interdiction d'une recette en sous-recette d'elle-même
        if recipe and sub_recipe and recipe.id == sub_recipe.id:
            raise serializers.ValidationError({"sub_recipe": "Une recette ne peut pas être sa propre sous-recette."})

        # Empêcher la modification du champ `recipe` après création
        if self.instance and "recipe" in self.initial_data:
            incoming_recipe_id = data.get("recipe")
            if incoming_recipe_id and self.instance.recipe.id != incoming_recipe_id:  # On lève l’erreur que si le client fournit explicitement une valeur différente pour recipe
                raise serializers.ValidationError({"recipe": "Recipe cannot be changed after creation."})

        return data

class RecipeSerializer(serializers.ModelSerializer):
    # Champs simples
    recipe_name = serializers.CharField()
    chef_name = serializers.CharField()
    context_name = serializers.CharField(required=False, allow_blank=True, allow_null=True, default="")
    source = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    trick = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    image = serializers.ImageField(required=False, allow_null=True)
    servings_min = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    servings_max = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    parent_recipe_name = serializers.SerializerMethodField()
    adaptation_note = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    tags = serializers.ListField(child=serializers.CharField(max_length=50), required=False, allow_empty=True)

    # Relations simples
    pan = serializers.PrimaryKeyRelatedField(queryset=Pan.objects.all(), allow_null=True, required=False)
    parent_recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all(), allow_null=True, required=False)
    categories = serializers.PrimaryKeyRelatedField(many=True, queryset=Recipe.categories.rel.model.objects.all(), required=False)
    labels = serializers.PrimaryKeyRelatedField(many=True, queryset=Recipe.labels.rel.model.objects.all(), required=False)
    ingredients = RecipeIngredientSerializer(many=True, required=False, context={"is_nested": True}, source="recipe_ingredients")
    steps = RecipeStepSerializer(many=True, required=False, context={"is_nested": True})
    sub_recipes = SubRecipeSerializer(many=True, required=False, context={"is_nested": True}, source="main_recipes")

    # Utilisateur et visibilité
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    guest_id = serializers.CharField(read_only=True)
    visibility = serializers.ChoiceField(choices=[('private', 'Privée'), ('public', 'Publique')], required=False, default='private')
    is_default = serializers.BooleanField(read_only=True)

    class Meta:
        model = Recipe
        fields = ["id", 
                  "recipe_name", "chef_name", "context_name", 
                  "source", "recipe_type", "parent_recipe", "parent_recipe_name", "adaptation_note", "tags",
                  "servings_min", "servings_max", "total_recipe_quantity", "description", "trick", "image", 
                  "pan", "categories", "labels", "ingredients", "steps", "sub_recipes", 
                  "created_at", "updated_at",
                  "user", "guest_id", "visibility", "is_default"]
        read_only_fields = ["created_at", "updated_at"]    

    def __init__(self, *args, **kwargs):
        """Supprime recipe en mode nested."""
        super().__init__(*args, **kwargs)
        if "steps" in self.fields:
            self.fields["steps"].child.context.update({"is_nested": True})
        if "recipe_ingredients" in self.fields:
            self.fields["recipe_ingredients"].child.context.update({"is_nested": True})
        if "main_recipes" in self.fields:
            self.fields["main_recipes"].child.context.update({"is_nested": True})

    def to_internal_value(self, data):
        data = data.copy()
        if "recipe_name" in data:
            data["recipe_name"] = normalize_case(data["recipe_name"])
        if "chef_name" in data:
            data["chef_name"] = normalize_case(data["chef_name"])
        return super().to_internal_value(data)

    def get_parent_recipe_name(self, obj):
        return obj.parent_recipe.recipe_name if obj.parent_recipe else None

    def validate_recipe_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Le nom de la recette doit contenir au moins 3 caractères.")
        return value

    def validate_chef_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Le nom du chef doit contenir au moins 3 caractères.")
        return value

    def validate_description(self, value):
        if value and len(value.strip()) < 10:
            raise serializers.ValidationError("doit contenir au moins 10 caractères.")
        return value

    def validate_trick(self, value):
        if value and len(value.strip()) < 10:
            raise serializers.ValidationError("doit contenir au moins 10 caractères.")
        return value

    def validate_context_name(self, value):
        if value and len(value.strip()) < 3:
            raise serializers.ValidationError("Le contexte doit contenir au moins 3 caractères.")
        return value

    def validate_source(self, value):
        if value and len(value.strip()) < 3:
            raise serializers.ValidationError("La source doit contenir au moins 3 caractères.")
        return value

    def validate(self, data):
        """
        Validation centrale de Recipe :
        - Vérifie la logique d'adaptation (parent, type VARIATION, etc)
        - Vérifie unicité logique
        - Vérifie présence d'au moins un ingrédient/sous-recette SAUF si création via adapt_recipe
        """
        parent = data.get("parent_recipe", getattr(self.instance, "parent_recipe", None))
        rtype = data.get("recipe_type", getattr(self.instance, "recipe_type", "BASE"))
        request = self.context.get('request')
        user = request.user if request else None
        guest_id = data.get('guest_id') or (request.headers.get('X-Guest-Id') if request else None)

        # 0. Vérification de la présence d'un user ou d'un guest_id, mais pas les deux
        # if not user and not guest_id:
        #     raise serializers.ValidationError("Une recette doit appartenir à un utilisateur ou à un invité (user ou guest_id obligatoire).")
        # if user and guest_id:
        #     raise serializers.ValidationError("Une recette ne peut pas avoir à la fois un user et un guest_id.")

        # 1. Règles d'adaptation (parent/type)
        if parent and parent == self.instance:
            raise serializers.ValidationError("Une recette ne peut pas être sa propre version précédente.")
        if parent and rtype != "VARIATION":
            raise serializers.ValidationError("Une recette avec un parent doit être de type VARIATION.")
        if rtype == "VARIATION" and not parent:
            raise serializers.ValidationError("Une recette de type VARIATION doit avoir une parent_recipe.")

        # 2. Coherence servings
        min_val = data.get("servings_min")
        max_val = data.get("servings_max")
        if min_val and max_val and min_val > max_val:
            raise serializers.ValidationError("Le nombre de portions minimum ne peut pas être supérieur au maximum.")

        # 3. Note adaptation cohérente
        if data.get("adaptation_note") and not data.get("parent_recipe"):
            raise serializers.ValidationError({"adaptation_note": "Ce champ n'est permis que pour une adaptation (parent_recipe doit être défini)."})

        # 4. Validation d’unicité logique (soft-match insensible à la casse)
        # Fusion champ par champ pour obtenir l'état final du triplet unique
        name = normalize_case(data.get("recipe_name") or (self.instance and self.instance.recipe_name))
        chef = normalize_case(data.get("chef_name") or (self.instance and self.instance.chef_name))
        context = normalize_case(data.get("context_name") or (self.instance and self.instance.context_name))
        recipe_id = self.instance.id if self.instance else None

        # Si une autre recette a les mêmes valeurs → erreur
        if Recipe.objects.exclude(id=recipe_id).filter(recipe_name__iexact=name, chef_name__iexact=chef, context_name__iexact=context).exists():
            raise serializers.ValidationError("Une recette avec ce nom, ce chef et ce contexte existe déjà.")
        
        # 5. Présence d'ingrédients/étapes/sous-recettes (sauf adapt_recipe)
        # Vérification du contenu minimum (à la création uniquement)
        if not self.instance and not self.context.get("is_adapt_recipe", False):
            ingredients = data.get("recipe_ingredients", [])
            sub_recipes = data.get("main_recipes", [])
            steps = data.get("steps", [])

            if not (ingredients or sub_recipes):
                raise serializers.ValidationError("Une recette doit contenir au moins un ingrédient ou une sous-recette.")
            # if not (steps or sub_recipes):
            if not steps :
                raise serializers.ValidationError("Une recette doit contenir au moins une étape")

        # 6. Boucle indirecte parent (cycle)
        def has_cyclic_parent(instance, new_parent):
            current = new_parent
            while current:
                if current == instance:
                    return True
                current = current.parent_recipe
            return False

        if parent and self.instance and has_cyclic_parent(self.instance, parent):
            raise serializers.ValidationError("Cycle détecté dans les versions de recette.")

        return data

    def create(self, validated_data):
        # Extraction des sous-objets
        ingredients_data = validated_data.pop("recipe_ingredients", [])
        steps_data = validated_data.pop("steps", [])
        subrecipes_data = validated_data.pop("main_recipes", [])
        categories = validated_data.pop("categories", [])
        labels = validated_data.pop("labels", [])
        
        # Création de la recette
        recipe = Recipe.objects.create(**validated_data)
        recipe.categories.set(categories)
        recipe.labels.set(labels)

        # Complétion automatique step_number, si nécessaire
        # Ici, on force la consécutivité et l’ordre d’arrivée
        for idx, step in enumerate(steps_data, start=1):
            step["step_number"] = idx
            RecipeStep.objects.create(recipe=recipe, **step)

        for ingredient in ingredients_data:
            RecipeIngredient.objects.create(recipe=recipe, **ingredient)

        for sub in subrecipes_data:
            SubRecipe.objects.create(recipe=recipe, **sub)

        # --- AUTO-CALCUL de total_recipe_quantity : seulement si l'utilisateur n'a PAS fourni la valeur ---
        if recipe.total_recipe_quantity is None:
            try:
                recipe.compute_and_set_total_quantity(user=recipe.user, guest_id=recipe.guest_id)
            except ValidationError as e:
                recipe.delete()  # Supprime la recette si elle vient juste d'être créée
                raise serializers.ValidationError({"total_recipe_quantity": str(e)})

        return recipe

    def update(self, instance, validated_data):
        request = self.context.get("request")
        is_partial = request.method == "PATCH" if request else False

        # --- Gestion des sous-objets
        ingredients_data = validated_data.pop("recipe_ingredients", [])
        steps_data = validated_data.pop("steps", [])
        subrecipes_data = validated_data.pop("main_recipes", [])
        categories = validated_data.pop("categories", None)
        labels = validated_data.pop("labels", None)

        # --- Validation stricte en PATCH : pas de sous-objets autorisés ici
        if is_partial:
            forbidden_fields = {
                "recipe_ingredients": "Utilisez /recipes/<id>/ingredients/",
                "steps": "Utilisez /recipes/<id>/steps/",
                "main_recipes": "Utilisez /recipes/<id>/sub-recipes/"
            }
            for field in forbidden_fields:
                if field in self.initial_data:
                    raise serializers.ValidationError({field: forbidden_fields[field]})

        # --- Mise à jour des champs simples
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # --- M2M
        if categories is not None:
            instance.categories.set(categories)
        if labels is not None:
            instance.labels.set(labels)

        # --- Si PUT : suppression + recréation des sous-objets
        if not is_partial:
            if not ingredients_data and not subrecipes_data:
                raise serializers.ValidationError("Une recette doit contenir au moins un ingrédient ou une sous-recette.")
            if not steps_data and not subrecipes_data:
                raise serializers.ValidationError("Une recette doit contenir au moins une étape ou une sous-recette.")

            instance.recipe_ingredients.all().delete()
            instance.steps.all().delete()
            instance.main_recipes.all().delete()

            # Crée les RecipeStep en forçant step_number consécutif et dans l’ordre d’arrivée
            for idx, step in enumerate(steps_data, start=1):
                step["step_number"] = idx
                RecipeStep.objects.create(recipe=instance, **step)

            for ingredient in ingredients_data:
                RecipeIngredient.objects.create(recipe=instance, **ingredient)
                
            for sub in subrecipes_data:
                SubRecipe.objects.create(recipe=instance, **sub)

            # --- AUTO-CALCUL de total_recipe_quantity : si total non fourni, recalcule
            if 'total_recipe_quantity' not in self.initial_data or instance.total_recipe_quantity is None:
                try:
                    instance.compute_and_set_total_quantity(user=instance.user, guest_id=instance.guest_id)
                except ValidationError as e:
                    raise serializers.ValidationError({"total_recipe_quantity": str(e)})
                
        return instance

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user if request.user.is_authenticated else None
        guest_id = request.headers.get("X-Guest-Id")

        # Cas 1 : recette de base (is_default) ou recette qui n'appartient pas à ce user/guest
        if instance.is_default or (instance.user is None and not instance.guest_id):
            # Soft delete (masquage) pour ce user/invité
            UserRecipeVisibility.objects.get_or_create(
                user=user if user else None,
                guest_id=None if user else guest_id,
                recipe=instance,
                defaults={"visible": False}
            )
            return Response(status=status.HTTP_204_NO_CONTENT)

        # Cas 2 : c'est sa propre recette (user ou guest_id)
        return super().destroy(request, *args, **kwargs)

class PanSerializer(serializers.ModelSerializer):
    pan_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    pan_brand = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    volume_cm3 = serializers.FloatField(read_only=True)  # expose le volume calculé, non modifiable
    units_in_mold = serializers.IntegerField(min_value=1, required=False, default=1)

    # Utilisateur et visibilité
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    guest_id = serializers.CharField(read_only=True)
    visibility = serializers.ChoiceField(choices=[('private', 'Privée'), ('public', 'Publique')], required=False, default='private')
    is_default = serializers.BooleanField(read_only=True)

    class Meta:
        model = Pan
        fields = [
            "id", "pan_name", "pan_type", "pan_brand", 'units_in_mold',
            "diameter", "height",
            "length", "width", "rect_height",
            "volume_raw", "unit", "is_total_volume",
            "volume_cm3", "volume_cm3_cache",
            "user", "guest_id", "visibility", "is_default"
        ]
        read_only_fields = ["volume_cm3", "volume_cm3_cache"]

    def to_internal_value(self, data):
        data = data.copy()
        if "pan_name" in data:
            data["pan_name"] = normalize_case(data["pan_name"])
        if "pan_brand" in data:
            data["pan_brand"] = normalize_case(data["pan_brand"])
        return super().to_internal_value(data)

    def validate_pan_name(self, value):
        value = normalize_case(value)
        pan_id = self.instance.id if self.instance else None
        if Pan.objects.exclude(id=pan_id).filter(pan_name__iexact=value).exists():
            raise serializers.ValidationError("Un moule avec ce nom existe déjà.")
        
        if value and len(value) < 2:
            raise serializers.ValidationError("Le nom du moule doit contenir au moins 2 caractères.")

        return value

    def validate_pan_brand(self, value):
        if value and len(value) < 2:
            raise serializers.ValidationError("Le nom de la marque doit contenir au moins 2 caractères.")
        return value

    def validate(self, data):
        # getattr(self.instance, ...) pour gérer le cas des updates partiels (PATCH).
        pan_type = data.get("pan_type", getattr(self.instance, "pan_type", None))
        units_in_mold = data.get('units_in_mold', getattr(self.instance, 'units_in_mold', None))
        is_total_volume = data.get('is_total_volume', getattr(self.instance, 'is_total_volume', None))

        # Règle : units_in_mold > 1 seulement pour les CUSTOM
        if pan_type != 'CUSTOM' and units_in_mold != 1:
            raise serializers.ValidationError({"units_in_mold": "Ce champ ne peut être différent de 1 que pour les moules de type CUSTOM."})

        # Force is_total_volume à True si units_in_mold == 1
        if units_in_mold == 1:
            data['is_total_volume'] = True

        # Champs requis par type
        if pan_type == "ROUND":
            for field in ["diameter", "height"]:
                if not data.get(field) and not getattr(self.instance, field, None):
                    raise serializers.ValidationError({field: "Ce champ est requis pour un moule rond."})
            for forbidden in ["length", "width", "rect_height", "volume_raw", "unit"]:
                if data.get(forbidden) is not None:
                    raise serializers.ValidationError({forbidden: "Ce champ n'est pas autorisé pour un moule rond."})

        elif pan_type == "RECTANGLE":
            for field in ["length", "width", "rect_height"]:
                if not data.get(field) and not getattr(self.instance, field, None):
                    raise serializers.ValidationError({field: "Ce champ est requis pour un moule rectangulaire."})
            for forbidden in ["diameter", "height", "volume_raw", "unit"]:
                if data.get(forbidden) is not None:
                    raise serializers.ValidationError({forbidden: "Ce champ n'est pas autorisé pour un moule rectangulaire."})

        elif pan_type == "CUSTOM":
            if not data.get("volume_raw") and not getattr(self.instance, "volume_raw", None):
                raise serializers.ValidationError({"volume_raw": "Volume requis pour un moule personnalisé."})
            if not data.get("unit") and not getattr(self.instance, "unit", None):
                raise serializers.ValidationError({"unit": "Unité requise pour un moule personnalisé."})
            for forbidden in ["diameter", "height", "length", "width", "rect_height"]:
                if data.get(forbidden) is not None:
                    raise serializers.ValidationError({forbidden: "Ce champ n'est pas autorisé pour un moule personnalisé."})

        else:
            raise serializers.ValidationError({"pan_type": "Type de moule invalide."})

        return data

class IngredientUnitReferenceSerializer(serializers.ModelSerializer):
    ingredient = serializers.SlugRelatedField(queryset=Ingredient.objects.all(), slug_field='ingredient_name', required=True) # On expose l'ingrédient par son slug normalisé (plus lisible côté API)
    unit = serializers.ChoiceField(choices=UNIT_CHOICES)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    guest_id = serializers.CharField(read_only=True)

    class Meta:
        model = IngredientUnitReference
        fields = ['id', 'ingredient', 'unit', 'weight_in_grams', 'notes', 'user', 'guest_id', 'is_hidden']

    def validate_weight_in_grams(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Le poids doit être strictement supérieur à 0.")
        return value
    
    def validate(self, data):
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        guest_id = None
        if request:
            guest_id = (request.headers.get('X-Guest-Id') or request.headers.get('X-GUEST-ID') or request.data.get('guest_id') or request.query_params.get('guest_id'))
        ingredient = data.get('ingredient') or getattr(self.instance, 'ingredient', None)
        unit = data.get('unit') or getattr(self.instance, 'unit', None)
        is_hidden = data.get('is_hidden') or getattr(self.instance, 'is_hidden', None)
        if is_hidden is None:
            is_hidden = False  # la valeur par défaut métier pour toute création (POST)

        # Unicité du couple ingrédient + unité
        qs = IngredientUnitReference.objects.filter(ingredient=ingredient, unit=unit, user=user, guest_id=guest_id, is_hidden=is_hidden)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Cette référence existe déjà (active ou soft-hidée) pour cet utilisateur ou guest.")
        return data

class PanEstimationSerializer(serializers.Serializer):
    pan_id = serializers.IntegerField(required=False)
    pan_type = serializers.ChoiceField(choices=["ROUND", "RECTANGLE", "OTHER"], required=False)

    diameter = serializers.FloatField(required=False)
    height = serializers.FloatField(required=False)

    length = serializers.FloatField(required=False)
    width = serializers.FloatField(required=False)
    rect_height = serializers.FloatField(required=False)

    volume_raw = serializers.FloatField(required=False)

    def validate(self, data):
        if not data.get("pan_id") and not data.get("pan_type") and not data.get("volume_raw"):
            raise serializers.ValidationError("Vous devez fournir un pan_id OU un pan_type avec dimensions OU un volume_raw.")
        return data

class PanSuggestionSerializer(serializers.Serializer):
    target_servings = serializers.IntegerField(required=True, min_value=1)

    def validate_target_servings(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le nombre de portions doit être supérieur à 0.")
        return value

class RecipeAdaptationByIngredientSerializer(serializers.Serializer):
    recipe_id = serializers.IntegerField(required=True)
    ingredient_constraints = serializers.DictField(
        child=serializers.FloatField(),
        help_text="Dictionnaire sous la forme {ingredient_id: quantité_disponible}"
    )

class RecipeReferenceSuggestionSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()
    parent_category = serializers.StringRelatedField(source='category.parent_category', default=None)

    class Meta:
        model = Recipe
        fields = ["id", "recipe_name", "total_recipe_quantity", "category", "parent_category"]
