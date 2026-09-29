import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Building2, Network, Rocket, Search, ShieldCheck, SquareTerminal, UserPlus } from "lucide-react";
import { createUser, getCurrentUser, listDepartments, listUsers } from "../api";

const roleGroups = [
  { role: "admin", slug: "admins", title: "Admin", descriptor: "Members", action: "Manage Admins", tier: "Tier 1", Icon: ShieldCheck },
  { role: "manager", slug: "managers", title: "Manager", descriptor: "Members", action: "Manage Managers", tier: "Tier 2", Icon: Network },
  { role: "tl", slug: "team-leads", title: "Team Lead (TL)", descriptor: "Squad Leads", action: "Manage Team Leads", tier: "Tier 3", Icon: Rocket },
  { role: "user", slug: "users", title: "User / Engineer", descriptor: "Engineers", action: "Manage Users", tier: "Tier 4", Icon: SquareTerminal },
];

const roleLabels = { superadmin: "Super Admin", admin: "Admin", manager: "Manager", tl: "Team Lead", user: "User" };
const parentRoles = { admin: "superadmin", manager: "admin", tl: "manager", user: "tl" };
const creatableRoles = {
  superadmin: ["admin", "manager", "tl", "user"],
  admin: ["manager", "tl", "user"],
  manager: ["tl", "user"],
  tl: ["user"],
  user: [],
};
const visibleRoles = {
  superadmin: ["admin", "manager", "tl", "user"],
  admin: ["manager", "tl", "user"],
  manager: ["tl", "user"],
  tl: ["user"],
  user: ["user"],
};

export default function Members() {
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [addError, setAddError] = useState("");
  const [departmentLoading, setDepartmentLoading] = useState(false);
  const [departmentError, setDepartmentError] = useState("");
  const [newMember, setNewMember] = useState({ name: "", email: "", password: "", role: "", parent_id: "", department_id: "" });

  const allowedRoles = creatableRoles[currentUser?.role] || [];
  const displayedRoleGroups = roleGroups.filter((group) => (visibleRoles[currentUser?.role] || []).includes(group.role));

  async function loadMembers() {
    const [members, departmentList] = await Promise.all([listUsers(), listDepartments()]);
    setUsers(members);
    setDepartments(departmentList);
  }

  useEffect(() => {
    setDepartmentLoading(true);
    Promise.all([getCurrentUser(), listUsers(), listDepartments()])
      .then(([user, members, departmentList]) => {
        setCurrentUser(user);
        setUsers(members);
        setDepartments(departmentList);
      })
      .catch((err) => {
        setError(err.message);
        setDepartmentError(err.message);
      })
      .finally(() => {
        setLoading(false);
        setDepartmentLoading(false);
      });
  }, []);

  const filteredUsers = useMemo(() => {
    const query = search.trim().toLowerCase();
    return users.filter((user) => !query || `${user.name} ${user.email} ${user.department?.name || ""}`.toLowerCase().includes(query));
  }, [users, search]);

  function openAddModal() {
    setAddError("");
    setDepartmentError("");
    setNewMember({ name: "", email: "", password: "", role: allowedRoles[0] || "", parent_id: "", department_id: "" });
    setShowAddModal(true);
  }

  async function handleAddMember(event) {
    event.preventDefault();
    setAddError("");
    setSaving(true);
    try {
      await createUser({ ...newMember, parent_id: Number(newMember.parent_id), department_id: Number(newMember.department_id) });
      await loadMembers();
      setShowAddModal(false);
    } catch (err) {
      setAddError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const parentRole = parentRoles[newMember.role];
  const parentChoices = users.filter((user) => user.role === parentRole);

  return (
    <div className="mr-page">
      <header className="mr-topbar">
        <div className="mr-topbar-left">
          <span className="mr-title">Members &amp; Roles</span>
          <span className="mr-divider" />
        </div>
        <div className="mr-topbar-right">
          <label className="mr-search">
            <Search size={16} className="mr-search-icon" aria-hidden="true" />
            <input type="text" placeholder="Search members..." value={search} onChange={(event) => setSearch(event.target.value)} />
          </label>
          <button className="mr-add-btn" type="button" onClick={openAddModal} disabled={!allowedRoles.length}>
            <UserPlus size={16} aria-hidden="true" />
            <span>Add Member</span>
          </button>
          {currentUser?.role === "superadmin" && (
            <button className="mr-departments-btn" type="button" onClick={() => navigate("/departments")}>
              <Building2 size={16} aria-hidden="true" /> Departments
            </button>
          )}
        </div>
      </header>

      {error && <div className="members-alert" role="alert">{error}</div>}

      <main className="mr-grid">
        {displayedRoleGroups.map((group) => {
          const count = users.filter((user) => user.role === group.role).length;
          const Icon = group.Icon;
          return (
            <article className={`mr-card mr-card--${group.role}`} key={group.role}>
              <div className="mr-card-top">
                <div className="mr-icon-box"><Icon size={20} aria-hidden="true" /></div>
                <span className="mr-badge">{group.tier}</span>
              </div>
              <h2 className="mr-card-title">{group.title}</h2>
              <div className="mr-count-row">
                <span className="mr-count">{loading ? "-" : count}</span>
                <span className="mr-count-label">{group.descriptor}</span>
              </div>
              <div className="mr-card-divider" />
              <button type="button" className="mr-manage-btn" onClick={() => navigate(`/members/${group.slug}`)}>
                <span>{group.action}</span>
                <ArrowRight size={14} aria-hidden="true" />
              </button>
            </article>
          );
        })}
      </main>

      {search.trim() && (
        <section className="members-roster" aria-live="polite">
          <div className="members-roster-heading">
            <div>
              <p className="members-roster-eyebrow">Member directory</p>
              <h2>Search results</h2>
            </div>
            <button type="button" className="members-close-roster" onClick={() => setSearch("")} aria-label="Clear search">×</button>
          </div>
          {loading ? <p className="members-empty">Loading members...</p> : filteredUsers.length ? (
            <div className="members-roster-list">
              {filteredUsers.map((user) => (
                <button type="button" className="members-roster-row" key={user.id} onClick={() => navigate(`/employee/${user.id}`)}>
                  <span className="members-avatar">{user.name.charAt(0).toUpperCase()}</span>
                  <span className="members-roster-person"><strong>{user.name}</strong><small>{user.email}</small></span>
                  <span className={`members-status${user.is_active ? " is-active" : ""}`}>{user.is_active ? "Active" : "Inactive"}</span>
                  <span className="members-row-arrow" aria-hidden="true">→</span>
                </button>
              ))}
            </div>
          ) : <p className="members-empty">No members match this role and search.</p>}
        </section>
      )}

      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-box members-modal" onClick={(event) => event.stopPropagation()}>
            <div className="members-modal-heading">
              <div><p className="members-roster-eyebrow">Member management</p><h2>Add Member</h2></div>
              <button type="button" className="members-close-roster" onClick={() => setShowAddModal(false)} aria-label="Close">×</button>
            </div>
            {addError && <div className="alert-error" role="alert">{addError}</div>}
            <form onSubmit={handleAddMember}>
              <label htmlFor="member-name">Name</label>
              <input id="member-name" required value={newMember.name} onChange={(event) => setNewMember({ ...newMember, name: event.target.value })} />
              <label htmlFor="member-email">Email</label>
              <input id="member-email" required type="email" value={newMember.email} onChange={(event) => setNewMember({ ...newMember, email: event.target.value })} />
              <label htmlFor="member-password">Password</label>
              <input id="member-password" required type="password" value={newMember.password} onChange={(event) => setNewMember({ ...newMember, password: event.target.value })} />
              <label htmlFor="member-role">Role</label>
              <select id="member-role" required value={newMember.role} onChange={(event) => setNewMember({ ...newMember, role: event.target.value, parent_id: "" })}>
                {allowedRoles.map((role) => <option value={role} key={role}>{roleLabels[role]}</option>)}
              </select>
              <label htmlFor="member-department">Department</label>
              <select id="member-department" required value={newMember.department_id} onChange={(event) => setNewMember({ ...newMember, department_id: event.target.value })} disabled={departmentLoading || departments.length === 0}>
                <option value="">{departmentLoading ? "Loading departments..." : departments.length ? "Select department" : "No departments available"}</option>
                {departments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}
              </select>
              {departmentError && <div className="alert-error" role="alert">{departmentError}</div>}
              {!departmentLoading && !departmentError && departments.length === 0 && <p className="members-empty">Ask a Super Admin to create a department first.</p>}
              <label htmlFor="member-parent">Reports to</label>
              <select id="member-parent" required value={newMember.parent_id} onChange={(event) => setNewMember({ ...newMember, parent_id: event.target.value })}>
                <option value="">Select {roleLabels[parentRole] || "manager"}</option>
                {parentChoices.map((user) => <option value={user.id} key={user.id}>{user.name} ({user.email})</option>)}
              </select>
              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setShowAddModal(false)}>Cancel</button>
                <button type="submit" className="btn-primary" disabled={saving || !newMember.role || !newMember.department_id}>{saving ? "Adding..." : "Add Member"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}