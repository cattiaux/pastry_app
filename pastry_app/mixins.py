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
            return (
                self.queryset.model.objects.filter(
                    Q(user=user) | Q(visibility="public") | Q(is_default=True)
                ).distinct()
            )
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
        # Forçage privé par défaut pour invité
        if not user:
            if not visibility or visibility != "public":
                visibility = "private"
        serializer.save(user=user, guest_id=guest_id, visibility=visibility)
