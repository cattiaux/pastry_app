from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsOwnerOrGuestOrReadOnly(BasePermission):
    """
    - Un objet ne peut être modifié que par son propriétaire authentifié OU par l'invité qui l'a créé (via guest_id).
    - Lecture seule autorisée pour tous.
    """
    def has_object_permission(self, request, view, obj):
        # Lecture seule autorisée pour tout le monde
        if request.method in SAFE_METHODS:
            return True
        # Utilisateur authentifié
        if request.user.is_authenticated:
            return obj.user == request.user
        # Sinon, mode invité : compare le guest_id fourni à celui enregistré sur l'objet
        guest_id = request.headers.get("X-Guest-Id") or request.data.get("guest_id")
        return obj.guest_id and obj.guest_id == guest_id
    
class IsNotDefaultRecipe(BasePermission):
    """
    Interdit la modification/suppression des recettes de base (is_default=True).
    """
    def has_object_permission(self, request, view, obj):
        if getattr(obj, 'is_default', False):
            return request.method in SAFE_METHODS  # Lecture seule
        return True
    
class IsAdminOrReadOnly(BasePermission):
    """
    Autorise l'écriture uniquement aux admins.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff