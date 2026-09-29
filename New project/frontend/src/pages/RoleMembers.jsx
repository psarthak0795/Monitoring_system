import { Fragment, useEffect, useMemo, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import {
  Building2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Eye,
  Network,
  Search,
  UserPlus,
  Users,
} from "lucide-react";
import { createUser, getCurrentUser, listDepartments, listTimeEntries, listUsers } from "../api";

const roleConfig = {
  admins: {
    role: "admin",
    title: "Admins",
    addLabel: "Add Admin",
    memberHeader: "ADMIN",
    reportsHeader: "ACCESS",
    searchPlaceholder: "Search admins by name or email...",
    nextRole: "manager",
    nextLabel: "Managers Overseen",
    parentLabel: "All Super Admins",
  },
  managers: {
    role: "manager",
    title: "Managers",
    addLabel: "Add Manager",
    memberHeader: "MANAGER",
    reportsHeader: "TEAM LEADS",
    searchPlaceholder: "Search managers by name or email...",
    nextRole: "tl",
    nextLabel: "Team Leads Managed",
    parentLabel: "All Admins",
  },
  "team-leads": {
    role: "tl",
    title: "Team Leads (TL)",
    addLabel: "Add Team Lead",
    memberHeader: "TEAM LEAD",
    reportsHeader: "ENGINEERS",
    searchPlaceholder: "Search team leads by name or email...",
    nextRole: "user",
    nextLabel: "Engineers Managed",
    parentLabel: "All Managers",
  },
  users: {
    role: "user",
    title: "Users / Engineers",
    addLabel: "Add Engineer",
    memberHeader: "ENGINEER",
    reportsHeader: "ACCESS",
    searchPlaceholder: "Search engineers by name or email...",
    parentLabel: "All Team Leads",
  },
};

const roleLabels = { superadmin: "Super Admin", admin: "Admin", manager: "Manager", tl: "Team Lead", user: "Engineer" };
const roleSlug = { admin: "admins", manager: "managers", tl: "team-leads", user: "users" };
const allowedViews = {
  superadmin: ["admins", "managers", "team-leads", "users"],
  admin: ["managers", "team-leads", "users"],
  manager: ["team-leads", "users"],
  tl: ["users"],
  user: ["users"],
};
const creatableRoles = {
  superadmin: ["admin", "manager", "tl", "user"],
  admin: ["manager", "tl", "user"],
  manager: ["tl", "user"],
  tl: ["user"],
  user: [],
};
const requiredParentRole = { admin: "superadmin", manager: "admin", tl: "manager", user: "tl" };
const pageSize = 6;
const onlineWindowMs = 30_000;

function initials(name) {
  return name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();
}

function timeAgo(dateValue) {
  if (!dateValue) return "No recent activity";
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(dateValue).getTime()) / 60_000));
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function RoleMembers() {
  const { role } = useParams();
  const config = roleConfig[role];
  const [users, setUsers] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [entries, setEntries] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [parentFilter, setParentFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [expandedMemberId, setExpandedMemberId] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [addError, setAddError] = useState("");
  const [departmentError, setDepartmentError] = useState("");
  const [departmentLoading, setDepartmentLoading] = useState(false);
  const [newMember, setNewMember] = useState({ name: "", email: "", password: "", role: "", parent_id: "" });

  async function loadData() {
    const [memberList, entryList, departmentList] = await Promise.all([listUsers(), listTimeEntries(), listDepartments()]);
    setUsers(memberList);
    setEntries(entryList);
    setDepartments(departmentList);
  }

  useEffect(() => {
    if (!config) return undefined;
    setLoading(true);
    setDepartmentLoading(true);
    setError("");
    setDepartmentError("");
    getCurrentUser()
      .then((user) => {
        setCurrentUser(user);
        if (!(allowedViews[user.role] || []).includes(role)) return null;
        return Promise.all([
          listUsers(),
          listTimeEntries(),
          listDepartments().catch((err) => {
            setDepartmentError(err.message);
            return [];
          }),
        ]);
      })
      .then((data) => {
        if (!data) return;
        const [memberList, entryList, departmentList] = data;
        setUsers(memberList);
        setEntries(entryList);
        setDepartments(departmentList);
      })
      .catch((err) => setError(err.message))
      .finally(() => {
        setLoading(false);
        setDepartmentLoading(false);
      });
    return undefined;
  }, [role]);

  const memberById = useMemo(() => new Map(users.map((user) => [user.id, user])), [users]);
  const latestActivity = useMemo(() => {
    const latest = new Map();
    entries.forEach((entry) => {
      const timestamp = entry.last_seen_at || entry.end_time || entry.start_time;
      if (!timestamp) return;
      const current = latest.get(entry.user_id);
      if (!current || new Date(timestamp) > new Date(current)) latest.set(entry.user_id, timestamp);
    });
    return latest;
  }, [entries]);

  const filteredUsers = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return users.filter((user) => {
      if (user.role !== config?.role) return false;
      if (parentFilter !== "all" && String(user.parent_id) !== parentFilter) return false;
      return !normalizedQuery || `${user.name} ${user.email} ${user.id} ${user.department?.name || ""}`.toLowerCase().includes(normalizedQuery);
    });
  }, [users, config, query, parentFilter]);

  useEffect(() => setPage(1), [role, query, parentFilter]);

  const onlineIds = useMemo(() => {
    const now = Date.now();
    return new Set(entries.filter((entry) => {
      return entry.status === "active" && entry.last_seen_at && now - new Date(entry.last_seen_at).getTime() <= onlineWindowMs;
    }).map((entry) => entry.user_id).filter((userId) => memberById.get(userId)?.is_active));
  }, [entries, memberById]);
  const liveStatusById = useMemo(() => {
    const now = Date.now();
    const statuses = new Map();
    entries.forEach((entry) => {
      const heartbeatAge = entry.last_seen_at ? now - new Date(entry.last_seen_at).getTime() : Infinity;
      if (entry.status !== "active" || heartbeatAge < 0 || heartbeatAge > onlineWindowMs || !memberById.get(entry.user_id)?.is_active) return;
      statuses.set(entry.user_id, entry.is_idle ? "idle" : "active");
    });
    return statuses;
  }, [entries, memberById]);

  if (!config) return <Navigate to="/members" replace />;
  if (currentUser && !(allowedViews[currentUser.role] || []).includes(role)) return <Navigate to="/members" replace />;

  const availableRoles = creatableRoles[currentUser?.role] || [];
  const allowedToAdd = availableRoles.length > 0;
  const selectedRole = newMember.role || (availableRoles.includes(config.role) ? config.role : availableRoles[0] || "");
  const parentRole = requiredParentRole[selectedRole];
  const parentOptions = users.filter((user) => user.role === parentRole);
  const filteredParentOptions = config.role === "admin" ? users.filter((user) => user.role === "superadmin") : parentOptions;
  const maxPage = Math.max(1, Math.ceil(filteredUsers.length / pageSize));
  const currentPage = Math.min(page, maxPage);
  const pageUsers = filteredUsers.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const roleUsers = users.filter((user) => user.role === config.role);
  const onlineCount = roleUsers.filter((user) => onlineIds.has(user.id)).length;
  const nextRoleCount = config.nextRole
    ? users.filter((user) => user.role === config.nextRole && roleUsers.some((parent) => parent.id === user.parent_id)).length
    : new Set(roleUsers.map((user) => user.parent_id).filter(Boolean)).size;
  const parentRoleTitle = roleLabels[parentRole] || "manager";

  function openAddDialog() {
    setAddError("");
    setDepartmentError("");
    setNewMember({ name: "", email: "", password: "", role: selectedRole, parent_id: "", department_id: "" });
    setShowAddModal(true);
  }

  async function handleAddMember(event) {
    event.preventDefault();
    setSaving(true);
    setAddError("");
    try {
      await createUser({
        ...newMember,
        role: selectedRole,
        parent_id: Number(newMember.parent_id),
        department_id: Number(newMember.department_id),
      });
      await loadData();
      setShowAddModal(false);
    } catch (err) {
      setAddError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={`rm-page rm--${role}`}>
      <div className="page-header-bar rm-page-header">
        <nav className="page-breadcrumb" aria-label="Breadcrumb">
          <Link to="/members" className="breadcrumb-link">Members</Link>
          <span className="breadcrumb-separator">›</span>
          <span className="breadcrumb-current">{config.title}</span>
        </nav>
      </div>

      <main className="rm-content">
        <div className="rm-heading-row">
          <div className="rm-heading-left">
            <h1 className="rm-heading">{config.title}</h1>
            <span className="rm-pill">Registered {config.title} · {loading ? "-" : roleUsers.length} accounts</span>
          </div>
          <div className="rm-heading-right">
            <div className="rm-stats" aria-label="Role statistics">
              <span className="rm-stat"><i className="rm-online-dot" />{onlineCount} Online</span>
              <span className="rm-stat"><Users size={13} aria-hidden="true" />{nextRoleCount} {config.nextLabel || "Team Leads"}</span>
            </div>
            <button className="rm-add-btn" type="button" onClick={openAddDialog} disabled={!allowedToAdd}>
              <UserPlus size={15} aria-hidden="true" />
              <span>{config.addLabel}</span>
            </button>
          </div>
        </div>

        {error && <div className="rm-error" role="alert">{error}</div>}

        <section className="rm-card" aria-label={`${config.title} list`}>
          <div className="rm-toolbar">
            <label className="rm-search">
              <Search size={15} aria-hidden="true" />
              <input type="search" placeholder={config.searchPlaceholder} value={query} onChange={(event) => setQuery(event.target.value)} />
            </label>
            <label className="rm-filter">
              {config.role === "tl" || config.role === "user" ? <Network size={13} aria-hidden="true" /> : <Building2 size={13} aria-hidden="true" />}
              <select aria-label={config.parentLabel} value={parentFilter} onChange={(event) => setParentFilter(event.target.value)}>
                <option value="all">{config.parentLabel}</option>
                {filteredParentOptions.map((parent) => <option value={parent.id} key={parent.id}>{parent.name}</option>)}
              </select>
              <ChevronDown size={13} aria-hidden="true" />
            </label>
          </div>

          <div className="rm-table-scroll">
            <table className="rm-table">
              <thead>
                <tr>
                  <th>{config.memberHeader}</th>
                  <th>EMAIL &amp; ID</th>
                  <th>DEPARTMENT</th>
                  <th>{config.reportsHeader}</th>
                  <th>REPORTS TO</th>
                  <th>STATUS &amp; TIME</th>
                  <th className="rm-th-right">ACTION</th>
                </tr>
              </thead>
              <tbody>
                {loading ? <tr><td colSpan={7} className="rm-empty">Loading members...</td></tr> : pageUsers.map((member) => {
                  const directReports = users.filter((user) => user.parent_id === member.id);
                  const lastSeen = latestActivity.get(member.id);
                  const parent = memberById.get(member.parent_id);
                  const directReportsForRole = directReports.filter((user) => user.role === config.nextRole);
                  const isExpanded = Boolean(config.nextRole) && expandedMemberId === member.id;
                  const accessLabel = config.role === "user" ? "Employee access" : null;
                  const liveStatus = !member.is_active ? "inactive" : liveStatusById.get(member.id) || "offline";
                  const liveStatusLabel = { active: "Active", idle: "Idle", offline: "Offline", inactive: "Inactive" }[liveStatus];

                  return (
                    <Fragment key={member.id}>
                      <tr>
                        <td>
                          <div className="rm-member">
                            <div className="rm-avatar">{initials(member.name)}<i className={`rm-dot ${liveStatus === "active" ? "on" : liveStatus === "idle" ? "away" : "off"}`} /></div>
                            <div><div className="rm-name">{member.name}</div><div className="rm-sub">{roleLabels[member.role] || member.role}</div></div>
                          </div>
                        </td>
                        <td><div className="rm-email">{member.email}</div><div className="rm-id">ID: <b>{member.id}</b></div></td>
                        <td><span className="rm-department">{member.department?.name || "Unassigned"}</span></td>
                        <td>
                          {config.nextRole ? (
                            <button
                              type="button"
                              className="rm-chip rm-chip-button"
                              aria-expanded={isExpanded}
                              aria-label={`${directReportsForRole.length} ${roleLabels[config.nextRole]}${directReportsForRole.length === 1 ? "" : "s"} under ${member.name}`}
                              onClick={() => setExpandedMemberId((currentId) => currentId === member.id ? null : member.id)}
                            >
                              <Users size={12} aria-hidden="true" />
                              {directReportsForRole.length} {roleLabels[config.nextRole]}{directReportsForRole.length === 1 ? "" : "s"}
                              <ChevronDown className={isExpanded ? "rm-chip-chevron is-expanded" : "rm-chip-chevron"} size={12} aria-hidden="true" />
                            </button>
                          ) : <span className="rm-chip"><Users size={12} aria-hidden="true" />{accessLabel}</span>}
                        </td>
                        <td><span className="rm-reports-to">{parent?.name || "-"}</span></td>
                        <td><span className={`rm-status ${liveStatus}`}>{liveStatusLabel}</span><span className="rm-time">{timeAgo(lastSeen)}</span></td>
                        <td className="rm-td-right"><Link className="rm-view-btn" to={`/members/${role}/${member.id}`}><Eye size={13} aria-hidden="true" />View</Link></td>
                      </tr>
                      {isExpanded && (
                        <tr className="rm-report-row">
                          <td colSpan={7}>
                            <div className="rm-report-list">
                              <div className="rm-report-heading">{roleLabels[config.nextRole]}s reporting to {member.name}</div>
                              {directReportsForRole.length ? directReportsForRole.map((report) => (
                                <Link className="rm-report-member" key={report.id} to={`/members/${roleSlug[report.role]}/${report.id}`}>
                                  <span className="rm-report-avatar">{initials(report.name)}</span>
                                  <span><strong>{report.name}</strong><small>{report.email}</small></span>
                                  <Eye size={13} aria-hidden="true" />
                                </Link>
                              )) : <p className="rm-report-empty">No {roleLabels[config.nextRole].toLowerCase()}s report to this {roleLabels[member.role]} yet.</p>}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
                {!loading && pageUsers.length === 0 && <tr><td colSpan={7} className="rm-empty">No members found.</td></tr>}
              </tbody>
            </table>
          </div>

          <footer className="rm-footer">
            <span>Showing <b>{filteredUsers.length ? (currentPage - 1) * pageSize + 1 : 0}-{Math.min(currentPage * pageSize, filteredUsers.length)}</b> of <b>{filteredUsers.length}</b> {config.title.toLowerCase()}</span>
            <div className="rm-pager">
              <span>Page {currentPage} of {maxPage}</span>
              <button type="button" aria-label="Previous page" disabled={currentPage === 1} onClick={() => setPage((value) => Math.max(1, value - 1))}><ChevronLeft size={14} /></button>
              <button type="button" aria-label="Next page" disabled={currentPage >= maxPage} onClick={() => setPage((value) => Math.min(maxPage, value + 1))}><ChevronRight size={14} /></button>
            </div>
          </footer>
        </section>
      </main>

      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-box members-modal" onClick={(event) => event.stopPropagation()}>
            <div className="members-modal-heading">
              <div><p className="members-roster-eyebrow">Member management</p><h2>Add Member</h2></div>
              <button type="button" className="members-close-roster" onClick={() => setShowAddModal(false)} aria-label="Close">×</button>
            </div>
            {addError && <div className="alert-error" role="alert">{addError}</div>}
            <form onSubmit={handleAddMember}>
              <label htmlFor="role-member-name">Name</label>
              <input id="role-member-name" required value={newMember.name} onChange={(event) => setNewMember({ ...newMember, name: event.target.value })} />
              <label htmlFor="role-member-email">Email</label>
              <input id="role-member-email" required type="email" value={newMember.email} onChange={(event) => setNewMember({ ...newMember, email: event.target.value })} />
              <label htmlFor="role-member-password">Password</label>
              <input id="role-member-password" required type="password" value={newMember.password} onChange={(event) => setNewMember({ ...newMember, password: event.target.value })} />
              <label htmlFor="role-member-role">Role</label>
              <select
                id="role-member-role"
                required
                value={selectedRole}
                onChange={(event) => setNewMember({ ...newMember, role: event.target.value, parent_id: "" })}
              >
                {availableRoles.map((memberRole) => <option value={memberRole} key={memberRole}>{roleLabels[memberRole]}</option>)}
              </select>
              <label htmlFor="role-member-department">Department</label>
              <select
                id="role-member-department"
                required
                value={newMember.department_id || ""}
                onChange={(event) => setNewMember({ ...newMember, department_id: event.target.value })}
                disabled={departmentLoading || departments.length === 0}
              >
                <option value="">{departmentLoading ? "Loading departments..." : departments.length ? "Select department" : "No departments available"}</option>
                {departments.map((department) => <option value={department.id} key={department.id}>{department.name}</option>)}
              </select>
              {departmentError && <div className="alert-error" role="alert">{departmentError}</div>}
              {!departmentLoading && !departmentError && departments.length === 0 && <p className="members-empty">Ask a Super Admin to create a department first.</p>}
              <label htmlFor="role-member-parent">Reports to ({parentRoleTitle})</label>
              <select id="role-member-parent" required value={newMember.parent_id} onChange={(event) => setNewMember({ ...newMember, parent_id: event.target.value })}>
                <option value="">Select {parentRoleTitle}</option>
                {parentOptions.map((parent) => <option value={parent.id} key={parent.id}>{parent.name} ({parent.email})</option>)}
              </select>
              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setShowAddModal(false)}>Cancel</button>
                <button type="submit" className="btn-primary" disabled={saving || !selectedRole || !newMember.department_id || parentOptions.length === 0}>{saving ? "Adding..." : "Add Member"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}