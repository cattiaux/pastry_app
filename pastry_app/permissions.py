from rest_framework.permissions import BasePermission, SAFE_METHODS

def extract_guest_id(request):
    return (
        request.headers.get("X-Guest-Id") or
        request.headers.get("X-GUEST-ID") or
        request.data.get("guest_id") or
        request.query_params.get("guest_id")
    )

class IsOwnerOrGuestOrReadOnly(BasePermission):
    """
    Lecture seule pour tous. Modif/suppression : owner ou guest seulement.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_authenticated:
            return obj.user == request.user
        guest_id = extract_guest_id(request)
        return obj.guest_id and obj.guest_id == guest_id

class IsNotDefaultInstance(BasePermission):
    """
    Empêche toute modif/suppression sur instance "de base" (is_default=True).
    """
    def has_object_permission(self, request, view, obj):
        return not getattr(obj, 'is_default', False) or request.method in SAFE_METHODS

class CanSoftHideRecipeOrIsOwnerOrGuest(IsOwnerOrGuestOrReadOnly):
    """
    Pour Recipe : 
    - soft-hide autorisé sur is_default en DELETE (pour tout user/guest identifié)
    - Sinon, logique owner classique.
    """
    def has_object_permission(self, request, view, obj):
        # Lecture seule toujours autorisée
        if request.method in SAFE_METHODS:
            return True
        # Cas soft-hide sur recette de base
        if request.method == "DELETE" and getattr(obj, "is_default", False):
            # Autorise tout user identifié ou guest identifié
            return request.user.is_authenticated or extract_guest_id(request)
        # Sinon comportement owner/guest
        return super().has_object_permission(request, view, obj)

class CanForkOrIsOwnerOrGuest(IsOwnerOrGuestOrReadOnly):
    """
    Permet PATCH/DELETE sur une instance globale (user=None, guest_id=None) pour fork automatique.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        # Autorise modif/suppression sur globale (pour fork)
        if getattr(obj, "user", None) is None and getattr(obj, "guest_id", None) is None:
            return True
        # Sinon comportement owner/guest
        return super().has_object_permission(request, view, obj)

class IsAdminOrReadOnly(BasePermission):
    """
    Seuls les admins peuvent modifier/supprimer/créer.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff
