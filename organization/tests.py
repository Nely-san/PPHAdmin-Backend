from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from users.models import User, Role, PagePermission
from organization.models import Company, Department

class OrganizationAPITests(TestCase):
    def setUp(self):
        self.role, _ = Role.objects.get_or_create(code='SUPER_ADMIN', defaults={'name': 'Super Admin'})
        self.user, _ = User.objects.get_or_create(
            username='org_admin',
            defaults={
                'email': 'org_admin@test.com',
                'role': self.role,
                'approval_status': 'APPROVED',
                'is_active': True
            }
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_company_crud_and_departments(self):
        # 1. Create Company
        comp_res = self.client.post('/api/companies/', {
            'name': 'PPH Tech Corp',
            'code': 'PPH_TECH'
        }, format='json')
        self.assertEqual(comp_res.status_code, status.HTTP_201_CREATED)
        company_id = comp_res.data['id']

        # 2. Create Department for Company
        dept_res = self.client.post(f'/api/companies/{company_id}/departments/', {
            'name': 'Engineering',
            'code': 'ENG'
        }, format='json')
        self.assertEqual(dept_res.status_code, status.HTTP_201_CREATED)
        department_id = dept_res.data['id']

        # 3. Update Department at /api/departments/{id}/
        update_dept_res = self.client.put(f'/api/departments/{department_id}/', {
            'name': 'Software Engineering',
            'code': 'SWE'
        }, format='json')
        self.assertEqual(update_dept_res.status_code, status.HTTP_200_OK)
        self.assertEqual(update_dept_res.data['name'], 'Software Engineering')

        # 4. Org-Tree with trailing slash
        org_tree_slash = self.client.get('/api/companies/org-tree/')
        self.assertEqual(org_tree_slash.status_code, status.HTTP_200_OK)
        self.assertEqual(len(org_tree_slash.data), 1)
        self.assertEqual(len(org_tree_slash.data[0]['departments']), 1)

        # 5. Org-Tree without trailing slash
        org_tree_no_slash = self.client.get('/api/companies/org-tree')
        self.assertEqual(org_tree_no_slash.status_code, status.HTTP_200_OK)
        self.assertEqual(len(org_tree_no_slash.data), 1)

        # 6. Delete Department at /api/departments/{id}/
        del_dept_res = self.client.delete(f'/api/departments/{department_id}/')
        self.assertEqual(del_dept_res.status_code, status.HTTP_204_NO_CONTENT)

        # 7. Delete Company at /api/companies/{id}/
        del_comp_res = self.client.delete(f'/api/companies/{company_id}/')
        self.assertEqual(del_comp_res.status_code, status.HTTP_204_NO_CONTENT)


class OrganizationPermissionsSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_role, _ = Role.objects.get_or_create(
            code='ADMIN', defaults={'name': 'Admin', 'is_system_role': True}
        )
        self.employee_role, _ = Role.objects.get_or_create(
            code='EMPLOYEE', defaults={'name': 'Employee', 'is_system_role': False}
        )

        perm_edit, _ = PagePermission.objects.get_or_create(
            code='employees:profiles:edit',
            defaults={'name': 'Employee Profiles (Edit)', 'module': 'EMPLOYEES'}
        )
        self.admin_role.permissions.add(perm_edit)

        self.admin_user, _ = User.objects.get_or_create(
            username='org_admin_user',
            defaults={
                'email': 'admin@test.com',
                'role': self.admin_role,
                'approval_status': 'APPROVED',
                'is_active': True,
            }
        )
        self.employee_user, _ = User.objects.get_or_create(
            username='org_employee_user',
            defaults={
                'email': 'employee@test.com',
                'role': self.employee_role,
                'approval_status': 'APPROVED',
                'is_active': True,
            }
        )

        self.company = Company.objects.create(name='Initial Company', code='INIT_CO')

    def test_company_write_denied_for_employee(self):
        # authenticate as a user with role code 'EMPLOYEE' and no
        # employees:profiles:edit grant.
        # POST /api/companies/ with a minimal valid body -> 403.
        # GET /api/companies/ -> 200 (read stays open to any authenticated user).
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.post('/api/companies/', {
            'name': 'Denied Company',
            'code': 'DENIED_CO',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get('detail'), "You do not have permission to create companies.")

        get_res = self.client.get('/api/companies/')
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)

    def test_company_write_allowed_for_admin(self):
        # authenticate as a user with role code 'ADMIN' (has
        # employees:profiles:edit today).
        # POST /api/companies/ with a minimal valid body -> 201.
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post('/api/companies/', {
            'name': 'Admin Allowed Company',
            'code': 'ADM_CO',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_department_write_denied_for_employee(self):
        # authenticate as a user with role code 'EMPLOYEE' and no
        # employees:profiles:edit grant.
        # POST /api/departments/ with a minimal valid body -> 403.
        # GET /api/departments/ -> 200 (read stays open to any authenticated user).
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.post('/api/departments/', {
            'name': 'Denied Department',
            'code': 'DENIED_DEPT',
            'company_id': str(self.company.id),
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get('detail'), "You do not have permission to create departments.")

        get_res = self.client.get('/api/departments/')
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)

    def test_department_write_allowed_for_admin(self):
        # authenticate as a user with role code 'ADMIN' (has
        # employees:profiles:edit today).
        # POST /api/departments/ with a minimal valid body -> 201.
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post('/api/departments/', {
            'name': 'Admin Allowed Department',
            'code': 'ADM_DEPT',
            'company_id': str(self.company.id),
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_company_nested_department_create_denied_for_employee(self):
        # authenticate as EMPLOYEE. POST /api/companies/<company.id>/departments/
        # with a minimal valid body. Expect 403.
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.post(
            f'/api/companies/{self.company.id}/departments/',
            {'name': 'Denied Nested Dept', 'code': 'DEN_NEST_DEPT'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get('detail'), "You do not have permission to create departments.")

    def test_company_nested_department_create_allowed_for_admin(self):
        # authenticate as ADMIN. POST the same URL. Expect 201.
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            f'/api/companies/{self.company.id}/departments/',
            {'name': 'Admin Nested Dept', 'code': 'ADM_NEST_DEPT'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


