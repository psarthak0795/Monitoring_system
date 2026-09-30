import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.auth import visible_user_filter


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


if __name__ == "__main__":
    unittest.main()