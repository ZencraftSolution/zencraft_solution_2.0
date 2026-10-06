from rest_framework import serializers, status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.careers.models import JobApplication
from apps.core.utils import log_action
from apps.estimator.models import ProjectInquiry


class IsActiveStaff(BasePermission):
    """Like IsAdminUser, but also refuses an account that has since been deactivated.

    IsAdminUser only looks at is_staff, so a session created before an account was switched off
    would keep working until it expired. The dashboard views already check is_active; this makes
    the API agree with them.
    """

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_staff)


class StatusSerializer(serializers.Serializer):
    status = serializers.CharField(max_length=20)


class _StatusUpdateAPI(APIView):
    """PATCH {status} from the kanban boards. SessionAuthentication enforces CSRF."""

    permission_classes = [IsActiveStaff]
    model = None
    label = ""

    def patch(self, request, pk):
        obj = self.model.objects.filter(pk=pk).first()
        if obj is None:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = StatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]
        if new_status not in dict(self.model.STATUS_CHOICES):
            return Response({"detail": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
        old = obj.status
        obj.status = new_status
        obj.save(update_fields=["status", "updated_at"])
        log_action(request._request, f"moved {self.label}", obj, detail=f"{old} to {new_status}")
        return Response({"ok": True, "status": new_status, "label": obj.get_status_display()})


class LeadStatusAPI(_StatusUpdateAPI):
    model = ProjectInquiry
    label = "lead"


class ApplicationStatusAPI(_StatusUpdateAPI):
    model = JobApplication
    label = "application"
