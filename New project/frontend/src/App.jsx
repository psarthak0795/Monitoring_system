import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, NavLink, Navigate } from "react-router-dom";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import TrackerSettings from "./pages/TrackerSettings.jsx";
import EmployeeDetail from "./pages/EmployeeDetail.jsx";
import EmployeeScreenshots from "./pages/EmployeeScreenshots.jsx";
import Timesheets from "./pages/Timesheets.jsx";
import Screenshots from "./pages/Screenshots.jsx";
import Alerts from "./pages/Alerts.jsx";
import Members from "./pages/Members.jsx";
import RoleMembers from "./pages/RoleMembers.jsx";
import Departments from "./pages/Departments.jsx";
import { getCurrentUser, logout } from "./api";
import logo from "./assets/org-tracker-logo.svg";

function isAuthenticated() {
  return !!localStorage.getItem("token");
}

function getRoleLabel(role) {
  return { superadmin: "Super Administrator", admin: "Administrator", manager: "Manager", tl: "Team Lead", user: "Employee" }[role] || role;
}

function RequireAuth({ children }) {
  return isAuthenticated() ? children : <Navigate to="/login" replace />;
}

function RequireAdmin({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCurrentUser()
      .then(setCurrentUser)
      .catch(() => setCurrentUser(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading-state">Loading...</div>;
  if (!['superadmin', 'admin'].includes(currentUser?.role)) return <Navigate to="/" replace />;
  return children;
}

function NavIcon({ type }) {
  const paths = {
    dashboard: <><rect x="2.5" y="2.5" width="4" height="4" rx=".5" /><rect x="9.5" y="2.5" width="4" height="4" rx=".5" /><rect x="2.5" y="9.5" width="4" height="4" rx=".5" /><rect x="9.5" y="9.5" width="4" height="4" rx=".5" /></>,
    members: <><circle cx="6" cy="5" r="2.5" /><path d="M1.5 13.5v-1a4.5 4.5 0 0 1 9 0v1zM11 3a2.5 2.5 0 0 1 0 4.9M12 9a3.5 3.5 0 0 1 2.5 3.4v1" /></>,
    timesheets: <><circle cx="8" cy="4.8" r="2.2" /><path d="M3.5 13.5c.8-2.5 3.1-3.8 4.5-3.8 1.4 0 3.7 1.3 4.5 3.8" /></>,
    screenshots: <><rect x="2" y="3" width="12" height="8" rx="1" /><path d="M5 14h6M8 11v3" /></>,
    management: <><path d="M8 2.5 9.2 3l1.4-.5 1.1 1.1-.5 1.4.5 1.2 1.3.7v1.6l-1.3.7-.5 1.2.5 1.4-1.1 1.1-1.4-.5-1.2.5-.7 1.3H6.7L6 12.9l-1.2-.5-1.4.5-1.1-1.1.5-1.4-.5-1.2L1 8.5V6.9l1.3-.7.5-1.2-.5-1.4 1.1-1.1 1.4.5L6 2.5l.7-1.3h1.6z" /><circle cx="7.5" cy="7.7" r="2" /></>,
    alerts: <><path d="M8 2.5a4 4 0 0 1 4 4v2l1.3 2H2.7L4 8.5v-2a4 4 0 0 1 4-4Z" /><path d="M6.5 13.5h3" /></>,
  };

  return <svg className={`nav-icon${type === "management" ? " management-icon" : ""}`} viewBox="0 0 16 16" aria-hidden="true">{paths[type]}</svg>;
}

function Shell({ children }) {
  const [currentUser, setCurrentUser] = useState(null);

  useEffect(() => {
    getCurrentUser().then(setCurrentUser).catch(() => setCurrentUser(null));
  }, []);

  const userInitials = currentUser?.name
    ? currentUser.name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase()
    : "--";
  const currentRoleLabel = getRoleLabel(currentUser?.role);

  return (
    <div className="app-shell">
      <div className="sidebar">
        <div className="brand-mark">
          <img className="brand-logo" src={logo} alt="Org Tracker" />
          <div><strong>Org Tracker</strong><small>IT IDOL</small></div>
        </div>
        <nav className="sidebar-nav">
          <NavLink to="/"><NavIcon type="dashboard" />Dashboard</NavLink>
          <NavLink to="/members"><NavIcon type="members" />Members</NavLink>
          <NavLink to="/employee/me"><NavIcon type="timesheets" />Profile</NavLink>
          <NavLink to="/screenshots"><NavIcon type="screenshots" />Screenshots</NavLink>
          {(currentUser?.role === "superadmin" || currentUser?.role === "admin") && <NavLink className="management-link" to="/tracker-management"><NavIcon type="management" />Tracker Management</NavLink>}
        </nav>
        <div className="sidebar-footer">
          <div className="admin-profile"><span className="admin-avatar">{userInitials}</span><div><strong>{currentUser?.name || "Loading..."}</strong><small>{currentUser?.email || ""}</small></div></div>
          <div className="profile-role">{currentRoleLabel}</div>
          <a href="#" onClick={() => { logout(); window.location.href = "/login"; }}><span className="nav-icon">↪</span>Sign Out</a>
        </div>
      </div>
      <div className="content">{children}</div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Shell><Dashboard /></Shell>
            </RequireAuth>
          }
        />
        <Route
          path="/members"
          element={
            <RequireAuth>
              <Shell><Members /></Shell>
            </RequireAuth>
          }
        />
        <Route
          path="/departments"
          element={
            <RequireAuth>
              <Shell><Departments /></Shell>
            </RequireAuth>
          }
        />
        <Route
          path="/members/:role"
          element={
            <RequireAuth>
              <Shell><RoleMembers /></Shell>
            </RequireAuth>
          }
        />
        <Route
          path="/members/:role/:id/screenshots"
          element={
            <RequireAuth>
              <Shell><EmployeeScreenshots /></Shell>
            </RequireAuth>
          }
        />
        <Route
          path="/members/:role/:id"
          element={
            <RequireAuth>
              <Shell><EmployeeDetail /></Shell>
            </RequireAuth>
          }
        />
        <Route
          path="/tracker-management"
          element={
            <RequireAuth>
              <RequireAdmin>
                <Shell><TrackerSettings /></Shell>
              </RequireAdmin>
            </RequireAuth>
          }
        />
        <Route
          path="/employee/:id"
          element={
            <RequireAuth>
              <Shell><EmployeeDetail /></Shell>
            </RequireAuth>
          }
        />
        <Route
          path="/employee/:id/screenshots"
          element={
            <RequireAuth>
              <Shell><EmployeeScreenshots /></Shell>
            </RequireAuth>
          }
        />
        <Route
          path="/timesheets"
          element={
            <RequireAuth>
              <Shell><Timesheets /></Shell>
            </RequireAuth>
          }
        />
        <Route
          path="/screenshots"
          element={
            <RequireAuth>
              <Shell><Screenshots /></Shell>
            </RequireAuth>
          }
        />
        <Route
          path="/alerts"
          element={<RequireAuth><Shell><Alerts /></Shell></RequireAuth>}
        />
      </Routes>
    </BrowserRouter>
  );
}