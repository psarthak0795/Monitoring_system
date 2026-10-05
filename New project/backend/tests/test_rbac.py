import unittest
from datetime import datetime, timezone

from fastapi import HTTPException

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.auth import can_manage, require_admin, visible_user_filter
from app.routers.departments import create_department, list_departments
from app.routers.users import create_user, update_user
from app.routers.users import get_user_activity_summary, list_users
from app.schemas import DepartmentCreate, UserCreate, UserUpdate


class RbacVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(cls.engine)
        cls.session_factory = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.session_factory()
        self.db.query(models.User).delete(synchronize_session=False)
        self.db.query(models.Department).delete(synchronize_session=False)
        self.db.commit()
        department_a = models.Department(name=f"Org A {id(self)}")
        department_b = models.Department(name=f"Org B {id(self)}")
        self.db.add_all([department_a, department_b])
        self.db.flush()
        self.superadmin = models.User(name="Super", email=f"super-{id(self)}@test", hashed_password="x", role=models.UserRole.superadmin)
        self.admin = models.User(name="Admin", email=f"admin-{id(self)}@test", hashed_password="x", role=models.UserRole.admin, department_id=department_a.id)
        self.manager = models.User(name="Manager", email=f"manager-{id(self)}@test", hashed_password="x", role=models.UserRole.manager, department_id=department_a.id)
        self.employee = models.User(name="Employee", email=f"employee-{id(self)}@test", hashed_password="x", role=models.UserRole.employee, department_id=department_a.id, manager=self.manager)
        self.nested = models.User(name="Nested", email=f"nested-{id(self)}@test", hashed_password="x", role=models.UserRole.employee, department_id=department_a.id, manager=self.employee)
        self.other = models.User(name="Other", email=f"other-{id(self)}@test", hashed_password="x", role=models.UserRole.employee, department_id=department_b.id)
        self.db.add_all([self.superadmin, self.admin, self.manager, self.employee, self.nested, self.other])
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_superadmin_sees_everyone(self):
        visible = visible_user_filter(self.db.query(models.User), self.superadmin).all()
        self.assertEqual({user.email for user in visible}, {user.email for user in [self.superadmin, self.admin, self.manager, self.employee, self.nested, self.other]})

    def test_admin_sees_only_organization_and_not_superadmin(self):
        visible = visible_user_filter(self.db.query(models.User), self.admin).all()
        self.assertEqual({user.email for user in visible}, {self.admin.email, self.manager.email, self.employee.email, self.nested.email})

    def test_manager_sees_recursive_team_only(self):
        visible = visible_user_filter(self.db.query(models.User), self.manager).all()
        self.assertEqual({user.email for user in visible}, {self.manager.email, self.employee.email, self.nested.email})

    def test_admin_can_create_department_but_manager_cannot(self):
        authorized_admin = require_admin(self.admin)
        department = create_department(
            payload=DepartmentCreate(name="New Admin Department"),
            db=self.db,
            current_user=authorized_admin,
        )

        self.assertEqual(department.name, "New Admin Department")
        self.assertEqual(department.created_by_id, self.admin.id)
        with self.assertRaises(HTTPException) as raised:
            require_admin(self.manager)
        self.assertEqual(raised.exception.status_code, 403)

    def test_admin_department_visibility_is_private_and_names_are_per_admin(self):
        other_admin = models.User(
            name="Other Admin",
            email=f"other-admin-{id(self)}@test",
            hashed_password="x",
            role=models.UserRole.admin,
            department_id=self.other.department_id,
        )
        self.db.add(other_admin)
        self.db.commit()

        department_a = create_department(
            payload=DepartmentCreate(name="Operations"),
            db=self.db,
            current_user=self.admin,
        )
        department_b = create_department(
            payload=DepartmentCreate(name="Operations"),
            db=self.db,
            current_user=other_admin,
        )
        manager_a = create_user(
            payload=UserCreate(
                name="Operations Manager A",
                email=f"manager-a-{id(self)}@example.com",
                password="password",
                role=models.UserRole.manager,
                department_id=department_a.id,
                parent_id=self.admin.id,
            ),
            db=self.db,
            current_user=self.admin,
        )
        manager_b = create_user(
            payload=UserCreate(
                name="Operations Manager B",
                email=f"manager-b-{id(self)}@example.com",
                password="password",
                role=models.UserRole.manager,
                department_id=department_b.id,
                parent_id=other_admin.id,
            ),
            db=self.db,
            current_user=other_admin,
        )

        admin_departments = list_departments(db=self.db, current_user=self.admin)
        other_admin_departments = list_departments(db=self.db, current_user=other_admin)
        superadmin_departments = list_departments(db=self.db, current_user=self.superadmin)
        admin_users = list_users(db=self.db, current_user=self.admin)
        other_admin_users = list_users(db=self.db, current_user=other_admin)

        self.assertEqual(department_a.name, department_b.name)
        self.assertEqual(department_a.created_by_id, self.admin.id)
        self.assertEqual(department_b.created_by_id, other_admin.id)
        self.assertIn(department_a.id, {department.id for department in admin_departments})
        self.assertNotIn(department_b.id, {department.id for department in admin_departments})
        self.assertIn(department_b.id, {department.id for department in other_admin_departments})
        self.assertNotIn(department_a.id, {department.id for department in other_admin_departments})
        self.assertIn(department_a.id, {department.id for department in superadmin_departments})
        self.assertIn(department_b.id, {department.id for department in superadmin_departments})
        self.assertIn(manager_a.id, {user.id for user in admin_users})
        self.assertNotIn(manager_b.id, {user.id for user in admin_users})
        self.assertIn(manager_b.id, {user.id for user in other_admin_users})
        self.assertNotIn(manager_a.id, {user.id for user in other_admin_users})

    def test_superadmin_can_create_admin_without_department(self):
        admin = create_user(
            payload=UserCreate(
                name="New Admin",
                email=f"new-admin-{id(self)}@example.com",
                password="password",
                role=models.UserRole.admin,
                parent_id=self.superadmin.id,
            ),
            db=self.db,
            current_user=self.superadmin,
        )

        self.assertEqual(admin.role, models.UserRole.admin)
        self.assertIsNone(admin.department_id)

    def test_superadmin_can_assign_and_unassign_admin_department(self):
        admin = models.User(
            name="Unassigned Admin",
            email=f"unassigned-admin-{id(self)}@example.com",
            hashed_password="x",
            role=models.UserRole.admin,
            parent_id=self.superadmin.id,
        )
        self.db.add(admin)
        self.db.commit()

        assigned = update_user(
            user_id=admin.id,
            payload=UserUpdate(department_id=self.other.department_id),
            db=self.db,
            acting_user=self.superadmin,
        )
        self.assertEqual(assigned.department_id, self.other.department_id)

        unassigned = update_user(
            user_id=admin.id,
            payload=UserUpdate(department_id=None),
            db=self.db,
            acting_user=self.superadmin,
        )
        self.assertIsNone(unassigned.department_id)

    def test_manager_dashboard_lists_assigned_admin_without_profile_access(self):
        self.manager.parent_id = self.admin.id
        self.db.commit()

        dashboard_members = list_users(db=self.db, current_user=self.manager)

        self.assertIn(self.admin.id, {member.id for member in dashboard_members})
        self.assertFalse(can_manage(self.db, self.manager, self.admin.id))
        self.assertNotIn(self.superadmin.id, {member.id for member in dashboard_members})

    def test_manager_can_read_assigned_admin_summary_only(self):
        self.manager.parent_id = self.admin.id
        now = datetime.now(timezone.utc)
        self.db.add(models.TimeEntry(
            user_id=self.admin.id,
            start_time=now,
            last_seen_at=now,
            status=models.TimeEntryStatus.active,
            is_idle=False,
        ))
        self.db.commit()

        summary = get_user_activity_summary(user_id=self.admin.id, db=self.db, current_user=self.manager)

        self.assertEqual(summary["status"], "active")
        self.assertFalse(can_manage(self.db, self.manager, self.admin.id))
        with self.assertRaises(HTTPException):
            get_user_activity_summary(user_id=self.superadmin.id, db=self.db, current_user=self.manager)

    def test_employee_sees_only_themselves(self):
        team_lead = models.User(
            name="Team Lead",
            email=f"tl-{id(self)}@test",
            hashed_password="x",
            role=models.UserRole.tl,
            parent_id=self.manager.id,
        )
        self.db.add(team_lead)
        self.db.flush()
        self.employee.parent_id = team_lead.id
        colleague = models.User(
            name="Colleague",
            email=f"colleague-{id(self)}@test",
            hashed_password="x",
            role=models.UserRole.user,
            parent_id=team_lead.id,
        )
        self.db.add(colleague)
        self.db.commit()

        visible = visible_user_filter(self.db.query(models.User), self.employee).all()

        self.assertEqual({user.id for user in visible}, {self.employee.id})
        self.assertTrue(can_manage(self.db, self.employee, self.employee.id))
        self.assertFalse(can_manage(self.db, self.employee, team_lead.id))
        self.assertFalse(can_manage(self.db, self.employee, colleague.id))

    def test_team_lead_can_view_reports_but_not_manager(self):
        team_lead = models.User(
            name="Team Lead",
            email=f"tl-{id(self)}@test",
            hashed_password="x",
            role=models.UserRole.tl,
            parent_id=self.manager.id,
        )
        self.db.add(team_lead)
        self.db.flush()
        employee = models.User(
            name="Team Member",
            email=f"team-member-{id(self)}@test",
            hashed_password="x",
            role=models.UserRole.user,
            parent_id=team_lead.id,
        )
        self.db.add(employee)
        self.db.commit()

        self.assertTrue(can_manage(self.db, team_lead, team_lead.id))
        self.assertTrue(can_manage(self.db, team_lead, employee.id))
        self.assertFalse(can_manage(self.db, team_lead, self.manager.id))

    def test_team_lead_dashboard_lists_manager_without_profile_access(self):
        team_lead = models.User(
            name="Team Lead",
            email=f"tl-{id(self)}@test",
            hashed_password="x",
            role=models.UserRole.tl,
            parent_id=self.manager.id,
        )
        self.db.add(team_lead)
        self.db.flush()
        employee = models.User(
            name="Team Member",
            email=f"team-member-{id(self)}@test",
            hashed_password="x",
            role=models.UserRole.user,
            parent_id=team_lead.id,
        )
        self.db.add(employee)
        self.db.commit()

        dashboard_members = list_users(db=self.db, current_user=team_lead)

        self.assertEqual({member.id for member in dashboard_members}, {team_lead.id, employee.id, self.manager.id})
        self.assertFalse(can_manage(self.db, team_lead, self.manager.id))

    def test_employee_dashboard_lists_team_lead_without_profile_access(self):
        team_lead = models.User(
            name="Team Lead",
            email=f"tl-{id(self)}@test",
            hashed_password="x",
            role=models.UserRole.tl,
            parent_id=self.manager.id,
        )
        self.db.add(team_lead)
        self.db.flush()
        self.employee.parent_id = team_lead.id
        self.db.commit()

        dashboard_members = list_users(db=self.db, current_user=self.employee)

        self.assertEqual({member.id for member in dashboard_members}, {self.employee.id, team_lead.id, self.manager.id})
        self.assertFalse(can_manage(self.db, self.employee, team_lead.id))

    def test_employee_can_read_only_direct_team_lead_activity_summary(self):
        team_lead = models.User(
            name="Team Lead",
            email=f"tl-{id(self)}@test",
            hashed_password="x",
            role=models.UserRole.tl,
            parent_id=self.manager.id,
        )
        self.db.add(team_lead)
        self.db.flush()
        self.employee.parent_id = team_lead.id
        now = datetime.now(timezone.utc)
        self.db.add(models.TimeEntry(
            user_id=team_lead.id,
            start_time=now,
            last_seen_at=now,
            status=models.TimeEntryStatus.active,
            is_idle=True,
        ))
        self.db.commit()

        summary = get_user_activity_summary(user_id=team_lead.id, db=self.db, current_user=self.employee)

        self.assertEqual(summary["status"], "idle")
        self.assertIsNotNone(summary["last_activity_at"])
        with self.assertRaises(HTTPException):
            get_user_activity_summary(user_id=self.admin.id, db=self.db, current_user=self.employee)

    def test_employee_can_read_manager_status_and_ip_in_reporting_chain(self):
        team_lead = models.User(
            name="Team Lead",
            email=f"tl-{id(self)}@test",
            hashed_password="x",
            role=models.UserRole.tl,
            parent_id=self.manager.id,
        )
        self.db.add(team_lead)
        self.db.flush()
        self.employee.parent_id = team_lead.id
        now = datetime.now(timezone.utc)
        self.db.add(models.TimeEntry(
            user_id=self.manager.id,
            start_time=now,
            last_seen_at=now,
            start_ip_address="10.0.0.12",
            status=models.TimeEntryStatus.active,
            is_idle=False,
        ))
        self.db.commit()

        summary = get_user_activity_summary(user_id=self.manager.id, db=self.db, current_user=self.employee)

        self.assertEqual(summary["status"], "active")
        self.assertEqual(summary["current_ip"], "10.0.0.12")

    def test_team_lead_can_read_direct_manager_status_without_profile_access(self):
        team_lead = models.User(
            name="Team Lead",
            email=f"tl-{id(self)}@test",
            hashed_password="x",
            role=models.UserRole.tl,
            manager_id=self.manager.id,
        )
        self.db.add(team_lead)
        self.db.flush()
        now = datetime.now(timezone.utc)
        self.db.add(models.TimeEntry(
            user_id=self.manager.id,
            start_time=now,
            last_seen_at=now,
            status=models.TimeEntryStatus.active,
            is_idle=False,
        ))
        self.db.commit()

        dashboard_members = list_users(db=self.db, current_user=team_lead)
        summary = get_user_activity_summary(user_id=self.manager.id, db=self.db, current_user=team_lead)

        self.assertIn(self.manager.id, {member.id for member in dashboard_members})
        self.assertEqual(summary["status"], "active")
        self.assertFalse(can_manage(self.db, team_lead, self.manager.id))
        with self.assertRaises(HTTPException):
            get_user_activity_summary(user_id=self.admin.id, db=self.db, current_user=team_lead)


if __name__ == "__main__":
    unittest.main()