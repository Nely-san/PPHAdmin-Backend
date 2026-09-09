from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q

from leaves_ob.models import LeaveOBApplication
from leaves_ob.serializers import LeaveOBApplicationSerializer, LeaveOBActionSerializer

class LeaveOBViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for Leave & Official Business (OB) Applications (/api/leaves-ob/).
    """
    queryset = LeaveOBApplication.objects.filter(is_archived=False).select_related('person', 'reviewed_by')
    serializer_class = LeaveOBApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        status_val = self.request.query_params.get('status')
        if status_val and status_val.upper() != 'ALL':
            qs = qs.filter(status__iexact=status_val)

        req_type = self.request.query_params.get('requestType') or self.request.query_params.get('request_type')
        if req_type and req_type.upper() != 'ALL':
            qs = qs.filter(request_type__iexact=req_type)

        person_id = self.request.query_params.get('person') or self.request.query_params.get('personId')
        if person_id:
            qs = qs.filter(person_id=person_id)

        start_date = self.request.query_params.get('startDate') or self.request.query_params.get('start_date')
        if start_date:
            qs = qs.filter(end_date__gte=start_date)

        end_date = self.request.query_params.get('endDate') or self.request.query_params.get('end_date')
        if end_date:
            qs = qs.filter(start_date__lte=end_date)

        company_id = self.request.query_params.get('companyId')
        if company_id:
            qs = qs.filter(person__company_id=company_id)

        department_id = self.request.query_params.get('departmentId')
        if department_id:
            qs = qs.filter(person__department_id=department_id)

        search = self.request.query_params.get('search')
        if search and search.strip():
            q = search.strip()
            qs = qs.filter(
                Q(person__name__icontains=q) |
                Q(reason__icontains=q) |
                Q(location__icontains=q)
            )

        return qs

    def perform_create(self, serializer):
        # Auto-link person if not explicitly passed and user has linked person
        person = serializer.validated_data.get('person')
        if not person and hasattr(self.request.user, 'person'):
            serializer.save(person=self.request.user.person)
        else:
            serializer.save()

    @action(detail=True, methods=['post'], url_path='action')
    def process_action(self, request, pk=None):
        """
        HR Review / Approval / Rejection endpoint.
        """
        application = self.get_object()
        serializer = LeaveOBActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action_type = serializer.validated_data['action']
        remarks = serializer.validated_data.get('remarks', '')

        application.status = action_type
        application.reviewed_by = request.user
        application.review_remarks = remarks
        application.reviewed_at = timezone.now()
        application.save()

        return Response(LeaveOBApplicationSerializer(application).data)

    @action(detail=True, methods=['post'], url_path='withdraw')
    def withdraw(self, request, pk=None):
        """
        Allows applicant to withdraw a pending application.
        """
        application = self.get_object()
        if application.status != 'PENDING':
            return Response(
                {"detail": "Only pending applications can be withdrawn."},
                status=status.HTTP_400_BAD_REQUEST
            )
        application.status = 'WITHDRAWN'
        application.save()
        return Response(LeaveOBApplicationSerializer(application).data)
