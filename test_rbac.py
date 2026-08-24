import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.exceptions import ValidationError
from users.models import User, Role, PagePermission
from users.serializers import UserProfileSerializer, RoleSerializer

def test_rbac_suite():
    print("=== STARTING DYNAMIC RBAC & TRIPLE-LOCK TESTS ===")

    # Test 1: Baseline roles & permissions
    perm_count = PagePermission.objects.count()
    role_count = Role.objects.count()
    super_admin_role = Role.objects.get(code='SUPER_ADMIN')
    print(f"[TEST 1 PASS] Seeded {perm_count} permissions and {role_count} roles. Super Admin has {super_admin_role.permissions.count()} permissions.")

    # Clean up test users if any
    User.objects.filter(username__in=['superadmin_test2', 'supervisor_test']).delete()

    # Test 2: Get or Create sole Super Admin user
    super_admin = User.objects.filter(role__code='SUPER_ADMIN', is_archived=False).first()
    if not super_admin:
        super_admin = User.objects.create_superuser(
            username='superadmin',
            email='superadmin@company.com',
            password='Admin@123'
        )
    print(f"[TEST 2 PASS] Verified Super Admin: @{super_admin.username} (Role: {super_admin.role.code})")

    # Test 3: Attempt creating a second Super Admin (Must Fail)
    try:
        User.objects.create_superuser(
            username='superadmin_test2',
            email='superadmin2@company.com',
            password='Password123!'
        )
        print("[TEST 3 FAIL] Created second superadmin without error!")
        assert False
    except ValidationError as e:
        print(f"[TEST 3 PASS] Blocked second Super Admin creation: {e}")

    # Test 4: Attempt demoting / changing role of Super Admin (Must Fail)
    employee_role = Role.objects.get(code='EMPLOYEE')
    try:
        super_admin.role = employee_role
        super_admin.save()
        print("[TEST 4 FAIL] Super Admin role was modified without error!")
        assert False
    except ValidationError as e:
        print(f"[TEST 4 PASS] Blocked Super Admin demotion/role change: {e}")
        super_admin.refresh_from_db()

    # Test 5: Attempt archiving or deleting Super Admin (Must Fail)
    try:
        super_admin.archive(user_identifier='test_actor')
        print("[TEST 5 FAIL] Super Admin was archived without error!")
        assert False
    except ValidationError as e:
        print(f"[TEST 5 PASS] Blocked Super Admin soft-archiving: {e}")
        super_admin.refresh_from_db()

    try:
        super_admin.delete()
        print("[TEST 5 FAIL] Super Admin was deleted without error!")
        assert False
    except ValidationError as e:
        print(f"[TEST 5 PASS] Blocked Super Admin deletion: {e}")

    # Test 6: Create custom dynamic role
    custom_role, created = Role.objects.get_or_create(
        code='SHIFT_SUPERVISOR_TEST',
        defaults={'name': 'Shift Supervisor (Test)', 'description': 'Supervises attendance and shifts'}
    )
    test_perms = PagePermission.objects.filter(code__in=['dashboard', 'employees', 'attendance', 'shifts-rosters'])
    custom_role.permissions.set(test_perms)
    print(f"[TEST 6 PASS] Created Custom Role: {custom_role.name} with {custom_role.permissions.count()} pages assigned.")

    # Test 7: User profile serialization returns allowed_pages
    test_user = User.objects.create_user(
        username='supervisor_test',
        email='supervisor@company.com',
        password='Password123!',
        role=custom_role
    )
    serialized = UserProfileSerializer(test_user).data
    print(f"[TEST 7 PASS] Serialized user @{test_user.username} with role={serialized['role']}, allowed_pages={serialized['allowed_pages']}")
    assert set(serialized['allowed_pages']) == {'dashboard', 'employees', 'attendance', 'shifts-rosters'}

    print("=== ALL DYNAMIC RBAC & TRIPLE-LOCK TESTS PASSED PERFECTLY ===")

if __name__ == '__main__':
    test_rbac_suite()
