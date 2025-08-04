from django.db.models import Q

class GuestUserRecipeMixin:
    """
    Mixin pour factoriser la gestion des recettes/ingrédients/moules/magasins multi-utilisateurs (user ou invité/guest_id).
    - Permet à un utilisateur connecté d'accéder à ses propres éléments + publiques + "de base".
    - Permet à un invité d'accéder aux éléments publiques, de base, et à ses propres éléments privées (par guest_id).
    - Attribue la recette à user ou guest_id lors de la création.
    - Forçage : les éléments créées par un invité sont privées par défaut, sauf si "public" est explicitement demandé.
    """

    def get_guest_id(self):
        """Récupère le guest_id depuis le header, les données du body ou les query params."""
        return (
            self.request.headers.get("X-Guest-Id")
            or self.request.headers.get("X-GUEST-ID")  # Certains navigateurs upper-case tout
            or self.request.data.get("guest_id")
            or self.request.query_params.get("guest_id")
        )

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            # Recettes de l'utilisateur + publiques + de base
            return (self.queryset.model.objects.filter(Q(user=user) | Q(visibility="public") | Q(is_default=True)).distinct())
        else:
            guest_id = self.get_guest_id()
            qs = self.queryset.model.objects.filter(Q(visibility="public") | Q(is_default=True))
            if guest_id:
                # Ajoute ses recettes privées (en tant qu'invité identifié par guest_id)
                qs = qs | self.queryset.model.objects.filter(guest_id=guest_id, visibility="private")
            return qs.distinct()

    def perform_create(self, serializer):
        """
        Lors de la création :
        - Attribue à l'utilisateur connecté, OU à l'invité (guest_id).
        - Forçage : si invité, visibility="private" sauf si explicitement demandé "public" ET si tu l'acceptes.
        """
        user = self.request.user if self.request.user.is_authenticated else None
        guest_id = self.get_guest_id() if not user else None
        visibility = self.request.data.get("visibility")

        # Par défaut toujours "private", sauf si explicitement public
        if not visibility or visibility != "public":
            visibility = "private"
        save_kwargs = dict(user=user, guest_id=guest_id, visibility=visibility)
        serializer.save(**save_kwargs)

class GuestUserReferenceMixin:
    """
    Mixin ultra-minimaliste pour gestion user/guest sur les modèles sans visibility.
    """

    def get_guest_id(self):
        """Récupère le guest_id depuis le header, les données du body ou les query params."""
        return (
            self.request.headers.get("X-Guest-Id")
            or self.request.headers.get("X-GUEST-ID")  # Certains navigateurs upper-case tout
            or self.request.data.get("guest_id")
            or self.request.query_params.get("guest_id")
        )

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user if self.request.user.is_authenticated else None
        guest_id = self.get_guest_id()
        return qs.filter(Q(user=user) | Q(guest_id=guest_id) | (Q(user__isnull=True) & Q(guest_id__isnull=True)))

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        guest_id = self.get_guest_id()
        serializer.save(user=user, guest_id=guest_id)

class OverridableReferenceQuerysetMixin:
    """
    Pour les modèles à “base globale overridable”, fournit la logique DRY de merge privé + global sauf overridés.
    """

    def get_user_overridable_queryset(self, base_queryset):
        """
        base_queryset doit être le queryset du modèle complet (all())
        Renvoie : privés du user/guest + globales non overridées
        """
        user = self.request.user if self.request.user.is_authenticated else None
        guest_id = self.request.session.get('guest_id')
        # 1. Privés
        private_qs = base_queryset.filter(Q(user=user) | Q(guest_id=guest_id))
        # 2. Clefs déjà overridées
        private_keys = set((ref.ingredient_id, ref.unit) for ref in private_qs)
        # 3. Globales pas overridées
        global_qs = base_queryset.filter(user__isnull=True, guest_id__isnull=True)
        if private_keys:
            q_objects = Q()
            for (i, u) in private_keys:
                q_objects |= (Q(ingredient_id=i) & Q(unit=u))
            global_qs = global_qs.exclude(q_objects)
        # 4. Union (queryset combiné)
        return private_qs | global_qs
    
