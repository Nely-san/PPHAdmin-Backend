from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from users.models import User, Role
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
