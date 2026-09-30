import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getCurrentUser, getUser, listScreenshots } from "../api";
import useScreenshotImageUrls from "../hooks/useScreenshotImageUrls";

function localDay(dateStr) {
  const d = new Date(dateStr);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function todayStr() {
  return localDay(new Date().toISOString());
}
function addDays(dateStr, delta) {
  const d = new Date(`${dateStr}T00:00:00`);
  d.setDate(d.getDate() + delta);
  return localDay(d.toISOString());
}
function fullDateLabel(dateStr) {
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString([], {
    weekday: "long", month: "short", day: "numeric", year: "numeric",
  });
}
function hourLabel(hour) {
  const d = new Date(); d.setHours(hour, 0, 0, 0);
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", hour12: true });
}
function hourRangeLabel(hour) {
  const start = new Date(); start.setHours(hour, 0, 0, 0);
  const end = new Date(start); end.setHours(hour + 1);
  const fmt = (d) => d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", hour12: true });
  return `${fmt(start)} – ${fmt(end)}`;
}
function activityDotClass(level) {
  if (level >= 60) return "shot-dot-active";
  if (level > 0) return "shot-dot-idle";
  return "shot-dot-offline";
}
function timeLabel(dateStr) {
  return new Date(dateStr).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

const DENSITY_START_HOUR = 8;
const DENSITY_END_HOUR = 20; // inclusive
const DENSITY_TICK_HOURS = [8, 10, 12, 16, 20];

export default function EmployeeScreenshots() {
  const { id, role } = useParams();
  const isCurrentUser = id === "me";
  const userId = isCurrentUser ? null : Number(id);
  const memberRoleNames = { admins: "Admins", managers: "Managers", "team-leads": "Team Leads", users: "Users" };
  const detailPath = role ? `/members/${role}/${userId}` : `/employee/${id}`;

  const [user, setUser] = useState(null);
  const [shots, setShots] = useState([]);
  const [dateFilter, setDateFilter] = useState(todayStr());
  const [selectedIndex, setSelectedIndex] = useState(null);
  const [loading, setLoading] = useState(true);
  const dateInputRef = useRef(null);

  useEffect(() => {
    setLoading(true);
    const userRequest = isCurrentUser ? getCurrentUser() : getUser(userId);
    userRequest
      .then((currentUser) => Promise.all([currentUser, listScreenshots(currentUser.id)]))
      .then(([u, s]) => { setUser(u); setShots(s); })
      .finally(() => setLoading(false));
  }, [id, isCurrentUser, userId]);

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === "Escape") setSelectedIndex(null);
      if (e.key === "ArrowRight") setSelectedIndex((i) => (i === null ? null : Math.min(i + 1, dayShots.length - 1)));
      if (e.key === "ArrowLeft") setSelectedIndex((i) => (i === null ? null : Math.max(i - 1, 0)));
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shots, dateFilter]);

  const dayShots = useMemo(
    () => shots.filter((s) => localDay(s.captured_at) === dateFilter)
               .sort((a, b) => new Date(a.captured_at) - new Date(b.captured_at)),
    [shots, dateFilter]
  );
  const imageUrls = useScreenshotImageUrls(dayShots);

  const groups = useMemo(() => {
    const byHour = new Map();
    dayShots.forEach((s) => {
      const hour = new Date(s.captured_at).getHours();
      if (!byHour.has(hour)) byHour.set(hour, []);
      byHour.get(hour).push(s);
    });
    return Array.from(byHour.entries()).sort((a, b) => a[0] - b[0]).map(([hour, items]) => ({ hour, items }));
  }, [dayShots]);

  const isToday = dateFilter === todayStr();
  const currentHour = new Date().getHours();

  const densityBuckets = useMemo(() => {
    const counts = Array.from({ length: DENSITY_END_HOUR - DENSITY_START_HOUR + 1 }, (_, i) => {
      const hour = DENSITY_START_HOUR + i;
      const count = dayShots.filter((s) => new Date(s.captured_at).getHours() === hour).length;
      return { hour, count };
    });
    const max = Math.max(...counts.map((c) => c.count), 1);
    return counts.map((c) => ({ ...c, intensity: c.count / max }));
  }, [dayShots]);

  function densityClass(intensity) {
    if (intensity === 0) return "density-empty";
    if (intensity < 0.34) return "density-low";
    if (intensity < 0.67) return "density-mid";
    return "density-high";
  }

  function openLightbox(shot) {
    setSelectedIndex(dayShots.findIndex((s) => s.id === shot.id));
  }

  const selectedShot = selectedIndex !== null ? dayShots[selectedIndex] : null;

  if (loading) return <div className="loading-state">Loading...</div>;

  return (
    <div>
      <nav className="page-header-bar page-breadcrumb" aria-label="Breadcrumb">
        {role ? (
          <>
            <Link to="/members" className="breadcrumb-link">Members</Link>
            <span className="breadcrumb-separator">›</span>
            <Link to={`/members/${role}`} className="breadcrumb-link">{memberRoleNames[role] || "Members"}</Link>
            <span className="breadcrumb-separator">›</span>
            <Link to={detailPath} className="breadcrumb-link">{user?.name || "Member"}</Link>
          </>
        ) : (
          <>
            <Link to="/" className="breadcrumb-link">Dashboard</Link>
            <span className="breadcrumb-separator">›</span>
            <Link to={detailPath} className="breadcrumb-link">{user?.name || "Employee"}</Link>
          </>
        )}
        <span className="breadcrumb-separator">›</span>
        <span className="breadcrumb-current">Screenshots</span>
      </nav>

      <div className="shots-header-row">
        <div>
          <div className="shots-title-line">
            <h1>Screenshots{user ? `: ${user.name}` : ""}</h1>
            <span className="shots-count-pill">{dayShots.length} Captures</span>
          </div>
          <p className="subtitle">
            {dayShots.length} screenshot{dayShots.length === 1 ? "" : "s"} captured on {fullDateLabel(dateFilter)}
          </p>
        </div>
        <div className="day-nav">
          <button className="day-nav-arrow" onClick={() => setDateFilter((d) => addDays(d, -1))}>‹</button>
          <div
            className="date-field"
            onClick={() => dateInputRef.current?.showPicker?.()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") dateInputRef.current?.showPicker?.();
            }}
          >
            <span className="date-field-icon">📅</span>
            <span className="date-field-label">{fullDateLabel(dateFilter)}</span>
            <input
              ref={dateInputRef}
              type="date"
              value={dateFilter}
              aria-label="Choose screenshot date"
              onChange={(e) => setDateFilter(e.target.value)}
            />
          </div>
          <button className="day-nav-arrow" onClick={() => setDateFilter((d) => addDays(d, 1))}>›</button>
          <button className="btn-secondary" onClick={() => setDateFilter(todayStr())}>Today</button>
        </div>
      </div>

      <div className="card density-card">
        <h3 className="density-title">Daily Capture Density</h3>
        <div className="density-strip">
          {densityBuckets.map((b) => (
            <div
              key={b.hour}
              className={`density-seg ${densityClass(b.intensity)} ${isToday && b.hour === currentHour ? "density-seg-active" : ""}`}
              title={`${hourLabel(b.hour)}: ${b.count} screenshot${b.count === 1 ? "" : "s"}`}
            />
          ))}
        </div>
        <div className="density-ticks">
          {densityBuckets
            .filter((b) => DENSITY_TICK_HOURS.includes(b.hour))
            .map((b) => (
              <span key={b.hour} className={isToday && b.hour === currentHour ? "density-tick-active" : ""}>
                {hourLabel(b.hour)}{isToday && b.hour === currentHour ? " (Active)" : ""}
              </span>
            ))}
        </div>
      </div>

      {groups.length === 0 ? (
        <div className="card empty-state">No screenshots captured on this day.</div>
      ) : (
        groups.map((g) => (
          <div key={g.hour} className="shots-group">
            <div className="shots-group-header">
              <h3>{hourRangeLabel(g.hour)}</h3>
              <span className="shots-count-badge">{g.items.length}</span>
            </div>
            <div className="shots-grid">
              {g.items.map((s) => (
                <button key={s.id} className="shot-card" onClick={() => openLightbox(s)}>
                  <div className="shot-card-status">
                    <span className={`shot-dot ${activityDotClass(s.activity_level || 0)}`} />
                    <span className="shot-card-time">{timeLabel(s.captured_at)}</span>
                  </div>
                  <img className="shot-card-thumb" src={imageUrls[s.id] || undefined} alt={`Screenshot at ${s.captured_at}`} />
                </button>
              ))}
            </div>
          </div>
        ))
      )}

      {selectedShot && (
        <div className="lightbox-overlay" onClick={() => setSelectedIndex(null)}>
          <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
            <button className="lightbox-close" onClick={() => setSelectedIndex(null)}>✕</button>
            {selectedIndex > 0 && (
              <button className="lightbox-nav lightbox-nav-prev" onClick={(e) => { e.stopPropagation(); setSelectedIndex((i) => i - 1); }}>‹</button>
            )}
            <img src={imageUrls[selectedShot.id] || undefined} alt={`Screenshot ${selectedShot.id}`} />
            {selectedIndex < dayShots.length - 1 && (
              <button className="lightbox-nav lightbox-nav-next" onClick={(e) => { e.stopPropagation(); setSelectedIndex((i) => i + 1); }}>›</button>
            )}
            <div className="lightbox-caption">
              {new Date(selectedShot.captured_at).toLocaleString()} — IP: {selectedShot.ip_address}
              <span className="lightbox-position">{selectedIndex + 1} / {dayShots.length}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}