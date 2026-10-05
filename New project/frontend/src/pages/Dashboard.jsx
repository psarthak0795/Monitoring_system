import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Download } from "lucide-react";
import { getCurrentUser, getUserActivitySummary, listUsers, listTimeEntries, listScreenshots, listDepartments, createUser, updateUser, downloadDepartmentDailyReport } from "../api";

const roleLabels = { admin: "Admin", manager: "Manager", tl: "Team Lead", user: "User" };
const parentRoles = { admin: "superadmin", manager: "admin", tl: "manager", user: "tl" };

function sameId(left, right) {
  return left != null && right != null && Number(left) === Number(right);
}

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
  const [teamLeadSummary, setTeamLeadSummary] = useState(null);
  const [managerSummary, setManagerSummary] = useState(null);
  const [adminSummary, setAdminSummary] = useState(null);
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
  const [selectedSummaryMember, setSelectedSummaryMember] = useState(null);
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportDate, setReportDate] = useState(todayStr());
  const [reportError, setReportError] = useState("");
  const [downloadingReport, setDownloadingReport] = useState(false);

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

  useEffect(() => {
    let active = true;
    setTeamLeadSummary(null);
    setManagerSummary(null);
    setAdminSummary(null);
    const teamLead = users.find((user) => user.id === currentUser?.parent_id && user.role === "tl");
    if (currentUser?.role === "manager") {
      const admin = users.find((user) => user.role === "admin" && sameId(currentUser.parent_id, user.id));
      if (!admin) return () => { active = false; };
      getUserActivitySummary(admin.id)
        .then((summary) => { if (active) setAdminSummary(summary); })
        .catch(() => { if (active) setAdminSummary(null); });
      return () => { active = false; };
    }
    if (currentUser?.role === "tl") {
      const manager = users.find((user) => user.role === "manager" && [currentUser.parent_id, currentUser.manager_id].some((managerId) => sameId(managerId, user.id)));
      if (!manager) return () => { active = false; };
      getUserActivitySummary(manager.id)
        .then((summary) => { if (active) setManagerSummary(summary); })
        .catch(() => { if (active) setManagerSummary(null); });
      return () => { active = false; };
    }
    if (currentUser?.role !== "user" || !teamLead) return () => { active = false; };

    Promise.all([
      getUserActivitySummary(teamLead.id).catch(() => null),
      teamLead.parent_id ? getUserActivitySummary(teamLead.parent_id).catch(() => null) : Promise.resolve(null),
    ]).then(([teamLeadData, managerData]) => {
      if (active) {
        setTeamLeadSummary(teamLeadData);
        setManagerSummary(managerData);
      }
    });

    return () => { active = false; };
  }, [users, currentUser?.id, currentUser?.parent_id, currentUser?.role]);

  const rows = useMemo(() => {
    const directTeamLead = users.find((user) => user.id === currentUser?.parent_id && user.role === "tl");
    return users.map((u) => {
      const isDirectTeamLead = currentUser?.role === "user" && u.id === currentUser.parent_id && u.role === "tl";
      const isTeamLeadManager = currentUser?.role === "user" && u.role === "manager" && directTeamLead?.parent_id === u.id;
      const isDirectParentManager = currentUser?.role === "tl" && u.role === "manager" && [currentUser.parent_id, currentUser.manager_id].some((managerId) => sameId(managerId, u.id));
      const isDirectParentAdmin = currentUser?.role === "manager" && u.role === "admin" && sameId(currentUser.parent_id, u.id);
      const canViewActivitySummary = isDirectTeamLead || isTeamLeadManager || isDirectParentManager || isDirectParentAdmin;
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

      let status = isDirectTeamLead
        ? teamLeadSummary?.status || "offline"
        : isTeamLeadManager || isDirectParentManager ? managerSummary?.status || "offline"
          : isDirectParentAdmin ? adminSummary?.status || "offline" : "offline";
      if (!isDirectTeamLead && !isTeamLeadManager && !isDirectParentManager && !isDirectParentAdmin && activeEntry && isLive) {
        status = activeEntry.is_idle ? "idle" : "active";
      }

      const activityRestricted = (currentUser?.role === "user" && u.id !== currentUser.id) || isDirectParentManager || isDirectParentAdmin;
      const statusVisible = !activityRestricted || isDirectTeamLead || isTeamLeadManager || isDirectParentManager || isDirectParentAdmin;
      const lastActiveVisible = !activityRestricted || isDirectTeamLead || isDirectParentManager || isDirectParentAdmin;
      const currentIpVisible = !activityRestricted || isTeamLeadManager || isDirectParentManager || isDirectParentAdmin;
      const visibleLastActiveAt = isDirectTeamLead ? teamLeadSummary?.last_activity_at : isTeamLeadManager || isDirectParentManager ? managerSummary?.last_activity_at : isDirectParentAdmin ? adminSummary?.last_activity_at : lastActiveAt;
      return {
        user: u,
        status,
        currentIp: isTeamLeadManager || isDirectParentManager
          ? managerSummary?.current_ip || "-"
          : isDirectParentAdmin ? adminSummary?.current_ip || "-"
          : !activityRestricted && isLive ? activeEntry?.start_ip_address || "-" : "-",
        secondsToday,
        lastActiveAt: visibleLastActiveAt,
        activityRestricted,
        statusVisible,
        lastActiveVisible,
        currentIpVisible,
        isDirectTeamLead,
        isTeamLeadManager,
        isDirectParentManager,
        isDirectParentAdmin,
        canViewActivitySummary,
      };
    });
  }, [users, entries, screenshots, dateFilter, now, currentUser, teamLeadSummary, managerSummary]);

  const filteredRows = useMemo(() => {
    return rows.filter((r) => {
      const q = search.toLowerCase();
      const matchesSearch = r.user.name.toLowerCase().includes(q) || r.user.email.toLowerCase().includes(q);
      const matchesStatus = statusFilter === "all" || (!r.activityRestricted && r.status === statusFilter);
      return matchesSearch && matchesStatus;
    });
  }, [rows, search, statusFilter]);

  const stats = useMemo(() => {
    const activityRows = rows.filter((row) => !row.activityRestricted);
    return {
      total: activityRows.length,
      activeNow: activityRows.filter((row) => row.status === "active").length,
      idleNow: activityRows.filter((row) => row.status === "idle").length,
      offlineNow: activityRows.filter((row) => row.status === "offline").length,
      totalSeconds: activityRows.reduce((sum, row) => sum + row.secondsToday, 0),
    };
  }, [rows]);

  const trackerRunning = stats.activeNow + stats.idleNow > 0;
  const selectedSummary = selectedSummaryMember?.role === "admin"
    ? adminSummary
    : selectedSummaryMember?.role === "manager" ? managerSummary : teamLeadSummary;

  async function handleAddMember(e) {
    e.preventDefault();
    setAddError("");
    setSaving(true);
    try {
      await createUser({
        ...newMember,
        parent_id: Number(newMember.parent_id),
        ...(newMember.department_id ? { department_id: Number(newMember.department_id) } : {}),
      });
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
        ...(currentUser?.role === "superadmin" && updateMember.role === "admin"
          ? { department_id: updateMember.department_id ? Number(updateMember.department_id) : null }
          : updateMember.department_id ? { department_id: Number(updateMember.department_id) } : {}),
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

  async function handleDepartmentReportDownload() {
    if (!reportDate) {
      setReportError("Choose a date for the report.");
      return;
    }
    setDownloadingReport(true);
    setReportError("");
    try {
      const { blob, filename } = await downloadDepartmentDailyReport(reportDate);
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      setShowReportModal(false);
    } catch (error) {
      setReportError(error.message || "Unable to download the report.");
    } finally {
      setDownloadingReport(false);
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
          {currentUser?.role === "admin" && (
            <button
              className="btn-secondary department-report-button"
              onClick={() => {
                setReportDate(todayStr());
                setReportError("");
                setShowReportModal(true);
              }}
              title="Download company-wide daily timesheet report"
            ><Download size={15} aria-hidden="true" /> Company Report</button>
          )}
          <button className="btn-primary" onClick={openUpdateModal}>✎ Update User</button>
          {["superadmin", "admin"].includes(currentUser?.role) && (
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
                    <span className={`avatar-sm${r.statusVisible ? ` avatar-${r.status}` : ""}`}>{r.user.name.charAt(0).toUpperCase()}</span>
                    <div><strong>{r.user.name}</strong><small>{roleLabels[r.user.role] || r.user.role}</small></div>
                  </div>
                </td>
                <td>{r.user.email}</td>
                <td>{r.user.department?.name || "Unassigned"}</td>
                <td>{!r.statusVisible ? "—" : (
                  <span className={`pill pill-${r.status}`}>
                    <span className="pill-dot" /> {r.status.charAt(0).toUpperCase() + r.status.slice(1)}
                  </span>
                )}</td>
                <td className="mono">{r.currentIpVisible ? r.currentIp : "—"}</td>
                <td className="mono">{r.activityRestricted ? "—" : formatClock(r.secondsToday)}</td>
                <td>{!r.lastActiveVisible ? "—" : timeAgo(r.lastActiveAt)}</td>
                <td className="member-action-cell">
                  <div className="member-row-actions">
                    <button
                      className="btn-view"
                      disabled={r.activityRestricted && !r.canViewActivitySummary}
                      title={r.canViewActivitySummary ? `View ${roleLabels[r.user.role] || "member"} summary` : r.activityRestricted ? `You cannot view this ${roleLabels[r.user.role] || "member"}'s profile` : "View employee details"}
                      onClick={() => r.canViewActivitySummary ? setSelectedSummaryMember(r.user) : navigate(`/employee/${r.user.id}`)}
                    >View</button>
                    {currentUser?.role !== "user" && !r.isDirectParentManager && !r.isDirectParentAdmin && (
                      <button className="btn-view" onClick={() => openUpdateModal(r.user)}>Edit</button>
                    )}
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
              <label>Department{newMember.role === "admin" ? " (optional)" : ""}</label>
              <select
                required={newMember.role !== "admin"}
                value={newMember.department_id}
                onChange={(e) => setNewMember({ ...newMember, department_id: e.target.value })}
                disabled={!departments.length && newMember.role !== "admin"}
              >
                <option value="">
                  {newMember.role === "admin"
                    ? "Unassigned"
                    : departments.length ? "Select department" : "No departments available"}
                </option>
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
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={saving || (newMember.role !== "admin" && !newMember.department_id)}
                >{saving ? "Adding..." : "Add Member"}</button>
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
                <option value="">
                  {currentUser?.role === "superadmin" && updateMember.role === "admin"
                    ? "Unassigned"
                    : "Keep current / Unassigned"}
                </option>
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

      {selectedSummaryMember && (
        <div className="modal-overlay" onClick={() => setSelectedSummaryMember(null)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h3>{roleLabels[selectedSummaryMember.role] || "Member"} Summary</h3>
            <p><strong>{selectedSummaryMember.name}</strong></p>
            <p>{selectedSummaryMember.email}</p>
            <p>Department: {selectedSummaryMember.department?.name || "Unassigned"}</p>
            <p>Status: {selectedSummary?.status || "Offline"}</p>
            <p>Current Session IP: {selectedSummary?.current_ip || "-"}</p>
            <p>Last Active: {timeAgo(selectedSummary?.last_activity_at)}</p>
            <div className="modal-actions">
              <button type="button" className="btn-secondary" onClick={() => setSelectedSummaryMember(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
      {showReportModal && currentUser?.role === "admin" && (
        <div className="modal-overlay" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !downloadingReport) setShowReportModal(false);
        }}>
          <section
            className="modal-box timesheet-download-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="company-report-title"
          >
            <h3 id="company-report-title">Download Company Report</h3>
            <p className="muted">Choose a date to export daily timesheet summaries for Managers, Team Leads, and Users in your company.</p>
            <label htmlFor="company-report-date">Report Date</label>
            <input
              id="company-report-date"
              type="date"
              value={reportDate}
              onChange={(event) => setReportDate(event.target.value)}
              disabled={downloadingReport}
            />
            {reportError && <div className="alert-error" role="alert">{reportError}</div>}
            <div className="modal-actions">
              <button type="button" className="btn-secondary" onClick={() => setShowReportModal(false)} disabled={downloadingReport}>
                Cancel
              </button>
              <button type="button" className="btn-primary" onClick={handleDepartmentReportDownload} disabled={downloadingReport}>
                {downloadingReport ? "Downloading..." : "Download Report"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}