import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCurrentUser, listUsers, listTimeEntries, listScreenshots, listDepartments, createUser, updateUser } from "../api";

const roleLabels = { admin: "Admin", manager: "Manager", tl: "Team Lead", user: "User" };
const parentRoles = { admin: "superadmin", manager: "admin", tl: "manager", user: "tl" };

function formatClock(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function formatHM(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${String(m).padStart(2, "0")}m`;
}

// active entries never get duration_seconds updated until /stop is called,
// so compute the live elapsed time for whichever entry is still running
function liveDuration(entry) {
  if (entry.status === "active") {
    return Math.max(0, Math.floor((Date.now() - new Date(entry.start_time).getTime()) / 1000));
  }
  return entry.duration_seconds || 0;
}

function timeAgo(dateStr) {
  if (!dateStr) return "-";
  const diffMs = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins} mins ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hr${hrs > 1 ? "s" : ""} ago`;
  const days = Math.floor(hrs / 24);
  return days === 1 ? "Yesterday" : `${days} days ago`;
}

function localDay(dateStr) {
  const d = new Date(dateStr);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function todayStr() {
  return localDay(new Date().toISOString());
}

const HEARTBEAT_TIMEOUT_MS = 30000;

export default function Dashboard() {
  const navigate = useNavigate();

  const [users, setUsers] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  const [entries, setEntries] = useState([]);
  const [screenshots, setScreenshots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(Date.now());

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const dateFilter = todayStr();

  const [showAddModal, setShowAddModal] = useState(false);
  const [newMember, setNewMember] = useState({ name: "", email: "", password: "", role: "user", parent_id: "", department_id: "" });
  const [addError, setAddError] = useState("");
  const [saving, setSaving] = useState(false);
  const [showUpdateModal, setShowUpdateModal] = useState(false);
  const [updateMember, setUpdateMember] = useState({ id: "", name: "", role: "user", parent_id: "", department_id: "" });
  const [updateError, setUpdateError] = useState("");

  async function loadAll(viewer = currentUser) {
    setLoading(true);
    const [u, departmentList] = await Promise.all([listUsers(), listDepartments()]);
    setUsers(u);
    setDepartments(departmentList);
    const [e, s] = await Promise.all([listTimeEntries(), listScreenshots()]);
    setEntries(e);
    setScreenshots(s);
    setLoading(false);
  }

  useEffect(() => {
    getCurrentUser().then(setCurrentUser).catch(() => setCurrentUser(null));
    loadAll();
    const interval = setInterval(loadAll, 30000); // keep live times fresh
    const clock = setInterval(() => setNow(Date.now()), 5000);
    return () => {
      clearInterval(interval);
      clearInterval(clock);
    };
  }, []);

  const rows = useMemo(() => {
    return users.map((u) => {
      const userEntries = entries.filter((e) => e.user_id === u.id);
      const activeEntry = userEntries.find((e) => e.status === "active");
      const entriesToday = userEntries.filter((e) => localDay(e.start_time) === dateFilter);
      const secondsToday = entriesToday.reduce((sum, e) => sum + liveDuration(e), 0);

      const userShots = screenshots
        .filter((s) => s.user_id === u.id)
        .sort((a, b) => new Date(b.captured_at) - new Date(a.captured_at));
      const lastShot = userShots[0];
      const lastActiveAt = activeEntry?.last_seen_at || lastShot?.captured_at || activeEntry?.start_time || userEntries[0]?.start_time;
      const heartbeatAt = activeEntry?.last_seen_at ? new Date(activeEntry.last_seen_at).getTime() : 0;
      const isLive = heartbeatAt > 0 && now - heartbeatAt <= HEARTBEAT_TIMEOUT_MS;

      let status = "offline";
      if (activeEntry && isLive) {
        status = activeEntry.is_idle ? "idle" : "active";
      }

      return { user: u, status, currentIp: isLive ? activeEntry?.start_ip_address || "-" : "-", secondsToday, lastActiveAt };
    });
  }, [users, entries, screenshots, dateFilter, now]);

  const filteredRows = useMemo(() => {
    return rows.filter((r) => {
      const q = search.toLowerCase();
      const matchesSearch = r.user.name.toLowerCase().includes(q) || r.user.email.toLowerCase().includes(q);
      const matchesStatus = statusFilter === "all" || r.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [rows, search, statusFilter]);

  const stats = useMemo(() => ({
    total: users.length,
    activeNow: rows.filter((r) => r.status === "active").length,
    idleNow: rows.filter((r) => r.status === "idle").length,
    offlineNow: rows.filter((r) => r.status === "offline").length,
    totalSeconds: rows.reduce((sum, r) => sum + r.secondsToday, 0),
  }), [rows, users]);

  const trackerRunning = stats.activeNow + stats.idleNow > 0;

  async function handleAddMember(e) {
    e.preventDefault();
    setAddError("");
    setSaving(true);
    try {
      await createUser({ ...newMember, parent_id: Number(newMember.parent_id), department_id: Number(newMember.department_id) });
      setShowAddModal(false);
      setNewMember({ name: "", email: "", password: "", role: "user", parent_id: "", department_id: "" });
      await loadAll();
    } catch (err) {
      setAddError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function openUpdateModal(member = users[0]) {
    if (!member) return;
    setUpdateMember({ id: member.id, name: member.name, role: member.role, parent_id: member.parent_id || "", department_id: member.department_id || "" });
    setUpdateError("");
    setShowUpdateModal(true);
  }

  function handleUpdateMemberSelection(e) {
    const member = users.find((user) => user.id === Number(e.target.value));
    if (!member) return;
    setUpdateMember({ id: member.id, name: member.name, role: member.role, parent_id: member.parent_id || "", department_id: member.department_id || "" });
    setUpdateError("");
  }

  async function handleUpdateMember(e) {
    e.preventDefault();
    setUpdateError("");
    setSaving(true);
    try {
      await updateUser(updateMember.id, {
        name: updateMember.name,
        role: updateMember.role,
        ...(updateMember.department_id ? { department_id: Number(updateMember.department_id) } : {}),
        ...(updateMember.role !== "superadmin" ? { parent_id: Number(updateMember.parent_id) } : {}),
      });
      setShowUpdateModal(false);
      await loadAll();
    } catch (err) {
      setUpdateError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="dashboard-header">
        <div className="search-wrap">
          <span className="search-icon">⌕</span>
          <input
            className="search-input"
            placeholder="Search members or IP..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="header-actions">
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Filter by status">
            <option value="all">All Statuses</option>
            <option value="active">Active</option>
            <option value="idle">Idle</option>
            <option value="offline">Offline</option>
          </select>
          <button className="btn-primary" onClick={openUpdateModal}>✎ Update User</button>
          {currentUser?.role === "superadmin" && (
            <button className="btn-primary" onClick={() => navigate("/departments")}>＋ Create Department</button>
          )}
          <button className="btn-primary" onClick={() => setShowAddModal(true)}>＋ Add Member</button>
        </div>
      </div>

      <div className="page-title-row">
        <div>
          <h1>Team Overview</h1>
          <p className="subtitle">Monitor real-time employee activity and status.</p>
        </div>
        <div className={`updated-indicator ${trackerRunning ? "tracker-running" : "tracker-stopped"}`}>
          <span /> Tracker {trackerRunning ? "Running" : "Stopped"}
        </div>
      </div>

      <div className="stat-cards">
        <div className="stat-card">
          <div className="stat-label">Total Employees</div>
          <div className="stat-value">{stats.total}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Active Now</div>
          <div className="stat-value stat-active">● {stats.activeNow}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Currently Idle</div>
          <div className="stat-value stat-idle">● {stats.idleNow}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Offline</div>
          <div className="stat-value stat-offline">● {stats.offlineNow}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Work Hours Today</div>
          <div className="stat-value">{formatHM(stats.totalSeconds)}</div>
        </div>
      </div>

      <div className="table-card">
        <div className="table-heading">
          <div><h2>Member Activity</h2><span>{users.length} members registered</span></div>
          <div className="table-tabs"><button className={statusFilter === "all" ? "selected" : ""} onClick={() => setStatusFilter("all")}>All ({users.length})</button><button className={statusFilter === "active" ? "selected" : ""} onClick={() => setStatusFilter("active")}>Active ({stats.activeNow})</button><button className={statusFilter === "offline" ? "selected" : ""} onClick={() => setStatusFilter("offline")}>Offline ({stats.offlineNow})</button></div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Employee</th>
              <th>Email</th>
              <th>Department</th>
              <th>Status</th>
              <th>Current Session IP</th>
              <th>Today's Time</th>
              <th>Last Active</th>
              <th className="member-action-heading">Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((r) => (
              <tr key={r.user.id}>
                <td>
                  <div className="name-cell">
                    <span className={`avatar-sm avatar-${r.status}`}>{r.user.name.charAt(0).toUpperCase()}</span>
                    <div><strong>{r.user.name}</strong><small>{roleLabels[r.user.role] || r.user.role}</small></div>
                  </div>
                </td>
                <td>{r.user.email}</td>
                <td>{r.user.department?.name || "Unassigned"}</td>
                <td>
                  <span className={`pill pill-${r.status}`}>
                    <span className="pill-dot" /> {r.status.charAt(0).toUpperCase() + r.status.slice(1)}
                  </span>
                </td>
                <td className="mono">{r.currentIp}</td>
                <td className="mono">{formatClock(r.secondsToday)}</td>
                <td>{timeAgo(r.lastActiveAt)}</td>
                <td className="member-action-cell">
                  <div className="member-row-actions">
                    <button className="btn-view" onClick={() => navigate(`/employee/${r.user.id}`)}>View</button>
                    <button className="btn-view" onClick={() => openUpdateModal(r.user)}>Edit</button>
                  </div>
                </td>
              </tr>
            ))}
            {!loading && filteredRows.length === 0 && (
              <tr><td colSpan={8} className="empty-state">No employees match your filters.</td></tr>
            )}
          </tbody>
        </table>
        <div className="table-footer"><span>Showing 1 to {filteredRows.length} of {users.length} members</span><div className="pagination"><button disabled>Previous</button><button className="page-current">1</button><button disabled>Next</button></div></div>
      </div>

      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h3>Add Member</h3>
            {addError && <div className="alert-error">{addError}</div>}
            <form onSubmit={handleAddMember}>
              <label>Name</label>
              <input required value={newMember.name} onChange={(e) => setNewMember({ ...newMember, name: e.target.value })} />
              <label>Email</label>
              <input required type="email" value={newMember.email} onChange={(e) => setNewMember({ ...newMember, email: e.target.value })} />
              <label>Password</label>
              <input required type="password" value={newMember.password} onChange={(e) => setNewMember({ ...newMember, password: e.target.value })} />
              <label>Role</label>
              <select value={newMember.role} onChange={(e) => setNewMember({ ...newMember, role: e.target.value, parent_id: "" })}>
                <option value="admin">Admin</option>
                <option value="manager">Manager</option>
                <option value="tl">Team Lead</option>
                <option value="user">User</option>
              </select>
              <label>Department</label>
              <select required value={newMember.department_id} onChange={(e) => setNewMember({ ...newMember, department_id: e.target.value })} disabled={!departments.length}>
                <option value="">{departments.length ? "Select department" : "No departments available"}</option>
                {departments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}
              </select>
              <label>Reports to</label>
              <select required value={newMember.parent_id} onChange={(e) => setNewMember({ ...newMember, parent_id: e.target.value })}>
                <option value="">Select {parentRoles[newMember.role]}</option>
                {users.filter((user) => user.role === parentRoles[newMember.role]).map((user) => (
                  <option key={user.id} value={user.id}>{user.name} ({user.email})</option>
                ))}
              </select>
              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setShowAddModal(false)}>Cancel</button>
                <button type="submit" className="btn-primary" disabled={saving || !newMember.department_id}>{saving ? "Adding..." : "Add Member"}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showUpdateModal && (
        <div className="modal-overlay" onClick={() => setShowUpdateModal(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h3>Update User</h3>
            {updateError && <div className="alert-error">{updateError}</div>}
            <form onSubmit={handleUpdateMember}>
              <label>User</label>
              <select value={updateMember.id} onChange={handleUpdateMemberSelection}>
                {users.map((user) => <option key={user.id} value={user.id}>{user.name} ({user.email})</option>)}
              </select>
              <label>Name</label>
              <input required value={updateMember.name} onChange={(e) => setUpdateMember({ ...updateMember, name: e.target.value })} />
              <label>Department</label>
              <select value={updateMember.department_id} onChange={(e) => setUpdateMember({ ...updateMember, department_id: e.target.value })}>
                <option value="">Keep current / Unassigned</option>
                {departments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}
              </select>
              <label>Role</label>
              <select
                value={updateMember.role}
                disabled={Number(updateMember.id) === currentUser?.id}
                onChange={(e) => setUpdateMember({ ...updateMember, role: e.target.value, parent_id: "" })}
              >
                <option value="superadmin">Super Administrator</option>
                <option value="admin">Admin</option>
                <option value="manager">Manager</option>
                <option value="tl">Team Lead</option>
                <option value="user">User</option>
              </select>
              {Number(updateMember.id) === currentUser?.id && <p className="muted">You cannot change your own role. Ask another authorized administrator.</p>}
              {updateMember.role !== "superadmin" && (
                <>
                  <label>Reports to</label>
                  <select required value={updateMember.parent_id} onChange={(e) => setUpdateMember({ ...updateMember, parent_id: e.target.value })}>
                    <option value="">Select {parentRoles[updateMember.role]}</option>
                    {users.filter((user) => user.id !== updateMember.id && user.role === parentRoles[updateMember.role]).map((user) => (
                      <option key={user.id} value={user.id}>{user.name} ({user.email})</option>
                    ))}
                  </select>
                </>
              )}
              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setShowUpdateModal(false)}>Cancel</button>
                <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Updating..." : "Update User"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}