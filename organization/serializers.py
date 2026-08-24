from rest_framework import serializers
from organization.models import Company, Department

class DepartmentSerializer(serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(queryset=Company.objects.filter(is_archived=False), source='company', write_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    companyId = serializers.CharField(source='company.id', read_only=True)
    companyName = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = Department
        fields = ['id', 'company', 'company_id', 'company_name', 'companyId', 'companyName', 'name', 'code', 'created_at', 'updated_at']
        extra_kwargs = {'company': {'read_only': True}}


class CompanySerializer(serializers.ModelSerializer):
    departments = DepartmentSerializer(many=True, read_only=True)
    department_count = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = ['id', 'name', 'code', 'departments', 'department_count', 'created_at', 'updated_at']

    def get_department_count(self, obj):
        return obj.departments.filter(is_archived=False).count()
