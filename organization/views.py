from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from organization.models import Company, Department
from organization.serializers import CompanySerializer, DepartmentSerializer

# NOTE (Phase 2): move to users/permissions.py and re-export from
# users/views.py to eliminate the settings.views -> users.views coupling.
from users.views import user_has_module_permission

class CompanyViewSet(viewsets.ModelViewSet):
    """
    Company management endpoints.
    """
    queryset = Company.objects.filter(is_archived=False)
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def _caller_may_write(self, request):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_active is False or getattr(request.user, "is_archived", False):
            return False
        if getattr(request.user, "is_superuser", False):
            return True
        # TODO (Phase 2): map HTTP verb to action (create->add, destroy->delete,
        # update/partial_update->edit) when the resolver centralizes this.
        return user_has_module_permission(
            request.user, "employees:profiles", action="edit"
        )

    def create(self, request, *args, **kwargs):
        if not self._caller_may_write(request):
            return Response(
                {"detail": "You do not have permission to create companies."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='org-tree')
    def org_tree(self, request):
        companies = Company.objects.filter(is_archived=False).prefetch_related('departments')
        return Response(CompanySerializer(companies, many=True).data)

    @action(detail=True, methods=['get', 'post'], url_path='departments')
    def departments_for_company(self, request, pk=None):
        company = self.get_object()
        if request.method == 'POST':
            if not self._caller_may_write(request):
                return Response(
                    {"detail": "You do not have permission to create departments."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            data = request.data.copy()
            data['company_id'] = company.id
            serializer = DepartmentSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        departments = company.departments.filter(is_archived=False)
        return Response(DepartmentSerializer(departments, many=True).data)

    def update(self, request, *args, **kwargs):
        if not self._caller_may_write(request):
            return Response(
                {"detail": "You do not have permission to edit companies."},
                status=status.HTTP_403_FORBIDDEN,
            )
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not self._caller_may_write(request):
            return Response(
                {"detail": "You do not have permission to edit companies."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not self._caller_may_write(request):
            return Response(
                {"detail": "You do not have permission to delete companies."},
                status=status.HTTP_403_FORBIDDEN,
            )
        company = self.get_object()
        company.archive(user_identifier=request.user.username)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    Department management endpoints.
    """
    queryset = Department.objects.filter(is_archived=False)
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def _caller_may_write(self, request):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_active is False or getattr(request.user, "is_archived", False):
            return False
        if getattr(request.user, "is_superuser", False):
            return True
        # TODO (Phase 2): map HTTP verb to action (create->add, destroy->delete,
        # update/partial_update->edit) when the resolver centralizes this.
        return user_has_module_permission(
            request.user, "employees:profiles", action="edit"
        )

    def create(self, request, *args, **kwargs):
        if not self._caller_may_write(request):
            return Response(
                {"detail": "You do not have permission to create departments."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not self._caller_may_write(request):
            return Response(
                {"detail": "You do not have permission to edit departments."},
                status=status.HTTP_403_FORBIDDEN,
            )
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not self._caller_may_write(request):
            return Response(
                {"detail": "You do not have permission to edit departments."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not self._caller_may_write(request):
            return Response(
                {"detail": "You do not have permission to delete departments."},
                status=status.HTTP_403_FORBIDDEN,
            )
        department = self.get_object()
        department.archive(user_identifier=request.user.username)
        return Response(status=status.HTTP_204_NO_CONTENT)
