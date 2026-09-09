from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from organization.models import Company, Department
from organization.serializers import CompanySerializer, DepartmentSerializer

class CompanyViewSet(viewsets.ModelViewSet):
    """
    Company management endpoints.
    """
    queryset = Company.objects.filter(is_archived=False)
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    @action(detail=False, methods=['get'], url_path='org-tree')
    def org_tree(self, request):
        companies = Company.objects.filter(is_archived=False).prefetch_related('departments')
        return Response(CompanySerializer(companies, many=True).data)

    @action(detail=True, methods=['get', 'post'], url_path='departments')
    def departments_for_company(self, request, pk=None):
        company = self.get_object()
        if request.method == 'POST':
            data = request.data.copy()
            data['company_id'] = company.id
            serializer = DepartmentSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        departments = company.departments.filter(is_archived=False)
        return Response(DepartmentSerializer(departments, many=True).data)

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
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

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        department = self.get_object()
        department.archive(user_identifier=request.user.username)
        return Response(status=status.HTTP_204_NO_CONTENT)
