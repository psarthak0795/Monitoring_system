import { useEffect, useState } from "react";
import { getCurrentUser, getSettings, updateSettings } from "../api";

const SCREENSHOT_PRESETS = [60, 120, 300, 600, 900, 1800];
const IDLE_PRESETS = [60, 180, 300, 600, 900, 1800];

function formatDuration(totalSeconds) {
  if (totalSeconds % 60 === 0) return `${totalSeconds / 60} min`;
  return `${totalSeconds} sec`;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function SettingsIcon({ type, className = "" }) {
  const paths = {
    camera: <><rect x="2" y="4" width="12" height="9" rx="2" /><path d="m5 4 1-2h4l1 2" /><circle cx="8" cy="8.5" r="2.2" /></>,
    clock: <><circle cx="8" cy="8" r="5.5" /><path d="M8 5v3l2 1" /></>,
    policy: <><path d="M8 2.5 13 4v3.7c0 3.1-2.1 5.4-5 6.8-2.9-1.4-5-3.7-5-6.8V4z" /><path d="m5.8 8 1.5 1.5L10.5 6" /></>,
    tune: <><circle cx="8" cy="8" r="5.5" /><path d="M8 5v3l2 1" /></>,
    pencil: <><path d="m3 11.8-.5 2.7 2.7-.5L12.8 6.4 10.6 4.2z" /><path d="m9.8 5 1.2-1.2 1.8 1.8-1.2 1.2" /></>,
    check: <path d="m3.5 8.3 3 3 6-6" />,
    reset: <><path d="M3 7a5.2 5.2 0 1 1 1.2 4.1" /><path d="M3 3.5v3.8h3.8" /></>,
  };

  return <svg className={`ts-inline-icon ${className}`} viewBox="0 0 16 16" aria-hidden="true">{paths[type]}</svg>;
}

function ConfigureModal({ config, initialSeconds, onCancel, onApply, agentCount }) {
  const [seconds, setSeconds] = useState(initialSeconds);
  const { title, subtitle, icon, badgeLabel, presets, min, max, defaultSeconds, note, quickLabel, fineTuneTitle, pendingLabel, resetLabel } = config;
  const percent = ((seconds - min) / (max - min)) * 100;

  return (
    <div className="lightbox-overlay" onClick={onCancel}>
      <div className="table-card ts-modal" onClick={(e) => e.stopPropagation()}>
        <div className="ts-modal-header">
          <div className="ts-modal-header-left">
            <div className="ts-modal-icon"><SettingsIcon type={icon} /></div>
            <div>
              <div className="ts-modal-title-row">
                <h2>{title}</h2>
                <span className="pill ts-badge-enforced">{badgeLabel}</span>
              </div>
              <p className="subtitle">{subtitle}</p>
            </div>
          </div>
          <button className="ts-icon-btn" onClick={onCancel} type="button" aria-label="Close">
            <span aria-hidden="true">&times;</span>
          </button>
        </div>

        <div className="ts-modal-body">
          <div className="ts-section-label-row">
            <span className="ts-section-label">Preset intervals</span>
            <span className="subtitle">{quickLabel}</span>
          </div>

          <div className="ts-preset-grid">
            {presets.map((preset) => (
              <button
                key={preset}
                type="button"
                className={`ts-preset-btn ${seconds === preset ? "ts-preset-btn-active" : ""}`}
                onClick={() => setSeconds(preset)}
              >
                {formatDuration(preset)}
                {preset === defaultSeconds && <span className="ts-preset-default">Default</span>}
              </button>
            ))}
          </div>

          <div className="ts-finetune-card">
            <div className="ts-finetune-header">
              <div>
                <div className="ts-finetune-title">{fineTuneTitle}</div>
                <div className="subtitle">Specify custom range ({min} - {max} seconds)</div>
              </div>
              <label className="ts-custom-seconds">
                <span className="subtitle">Custom seconds:</span>
                <input
                  type="number"
                  min={min}
                  max={max}
                  value={seconds}
                  onChange={(e) => setSeconds(clamp(Number(e.target.value) || min, min, max))}
                />
                <span className="subtitle">sec</span>
              </label>
            </div>
            <input
              type="range"
              className="ts-slider"
              min={min}
              max={max}
              step={5}
              value={seconds}
              onChange={(e) => setSeconds(clamp(Number(e.target.value), min, max))}
              style={{ "--ts-slider-percent": `${percent}%` }}
              aria-label={title}
            />
            <div className="ts-slider-labels">
              <span>1m (60s)</span><span>5m (300s)</span><span>10m (600s)</span><span>15m (900s)</span><span>30m (1800s)</span>
            </div>
          </div>

          <div className="ts-pending-banner">
            <div>
              <span className="subtitle">{pendingLabel}: </span>
              <strong>{formatDuration(seconds)} ({seconds}s)</strong>
              <div className="subtitle">{note.replace("{count}", agentCount)}</div>
            </div>
            <button type="button" className="ts-reset-link" onClick={() => setSeconds(defaultSeconds)}>
              <SettingsIcon type="reset" />
              {resetLabel}
            </button>
          </div>
        </div>

        <div className="modal-actions ts-modal-footer">
          <button type="button" className="btn-secondary" onClick={onCancel}>Cancel</button>
          <button type="button" className="btn-primary" onClick={() => onApply(seconds)}>
            <SettingsIcon type="check" /> Apply Changes
          </button>
        </div>
      </div>
    </div>
  );
}

export default function TrackerSettings() {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [settings, setSettings] = useState(null);
  const [activeModal, setActiveModal] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    Promise.all([getCurrentUser(), getSettings()])
      .then(([user, fetchedSettings]) => {
        setCurrentUser(user);
        setSettings(fetchedSettings);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleApply(field, seconds) {
    setError("");
    setSuccess("");
    setSaving(true);
    try {
      const payload = {
        screenshot_interval_seconds: settings.screenshot_interval_seconds,
        idle_timeout_seconds: settings.idle_timeout_seconds,
        retention_days: settings.retention_days,
        screenshot_masking_enabled: settings.screenshot_masking_enabled,
        [field]: seconds,
      };
      const updated = await updateSettings(payload);
      setSettings(updated);
      setSuccess("Saved. Agents pick up the new setting within about 10 seconds.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
      setActiveModal(null);
    }
  }

  async function handlePrivacyChange(changes) {
    setError("");
    setSuccess("");
    setSaving(true);
    try {
      const updated = await updateSettings({ ...settings, ...changes });
      setSettings(updated);
      setSuccess("Privacy policy saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="loading-state">Loading...</div>;

  if (!["superadmin", "admin"].includes(currentUser?.role)) {
    return (
      <div>
        <h1>Tracker Management</h1>
        <p className="subtitle">Only admins can view or change tracker settings.</p>
      </div>
    );
  }

  const agentCount = currentUser?.org_agent_count ?? "your organization's";

  return (
    <div className="tracker-settings-page">
      <div className="page-title-row">
        <h1>Tracker Management</h1>
        <div className="ts-status-chip"><span className="ts-status-dot" /> <span>Status: {agentCount} Active Agents <strong>Syncing</strong></span></div>
      </div>

      {error && <div className="alert-error">{error}</div>}
      {success && <div className="alert-success">{success}</div>}

      <div className="ts-card-grid">
        <div className="table-card ts-card">
          <div className="ts-card-header">
            <div className="ts-card-icon"><SettingsIcon type="camera" /></div>
            <div>
              <div className="ts-modal-title-row">
                <h3>Screenshot Interval</h3>
                <span className="pill ts-badge-enforced">Enforced</span>
              </div>
              <p className="subtitle">Organization-wide sync cadence</p>
            </div>
          </div>
          <p className="subtitle">Defines how frequently each employee&apos;s background tracker takes and synchronizes desktop snapshots to the secure cloud.</p>
          <div className="ts-stat-box">
            <div>
              <div className="ts-stat-label">ACTIVE CADENCE</div>
              <div className="ts-stat-value">{formatDuration(settings.screenshot_interval_seconds)} ({settings.screenshot_interval_seconds}s)</div>
            </div>
            <div className="ts-stat-auto"><SettingsIcon type="policy" /> Auto-synced</div>
          </div>
          <div className="ts-card-footer">
            <span className="subtitle">Applies to {agentCount} active agents</span>
            <button type="button" className="btn-primary" onClick={() => setActiveModal("screenshot")}><SettingsIcon type="pencil" /> Configure Interval</button>
          </div>
        </div>

        <div className="table-card ts-card">
          <div className="ts-card-header">
            <div className="ts-card-icon"><SettingsIcon type="clock" /></div>
            <div>
              <div className="ts-modal-title-row">
                <h3>Idle Timeout</h3>
                <span className="pill ts-badge-enforced">Auto-Pause</span>
              </div>
              <p className="subtitle">Inactivity threshold filter</p>
            </div>
          </div>
          <p className="subtitle">Defines idle duration before automatic session freeze triggers, keeping tracking stats accurate when employees are away.</p>
          <div className="ts-stat-box">
            <div>
              <div className="ts-stat-label">ACTIVE INACTIVITY LIMIT</div>
              <div className="ts-stat-value">{formatDuration(settings.idle_timeout_seconds)} ({settings.idle_timeout_seconds}s)</div>
            </div>
            <div className="ts-stat-auto"><SettingsIcon type="tune" /> Auto-pause</div>
          </div>
          <div className="ts-card-footer">
            <span className="subtitle">Pauses idle logging</span>
            <button type="button" className="btn-primary" onClick={() => setActiveModal("idle")}><SettingsIcon type="pencil" /> Configure Idle Timeout</button>
          </div>
        </div>

        <div className="table-card ts-card">
          <div className="ts-card-header"><div><h3>Screenshot Privacy</h3><p className="subtitle">Control image retention and masking.</p></div></div>
          <label className="profile-row"><span>Retention days</span><input type="number" min="1" max="3650" value={settings.retention_days} onChange={(e) => setSettings({ ...settings, retention_days: Number(e.target.value) })} /></label>
          <label className="profile-row"><span>Blur screenshots before storage</span><input type="checkbox" checked={settings.screenshot_masking_enabled} onChange={(e) => setSettings({ ...settings, screenshot_masking_enabled: e.target.checked })} /></label>
          <button className="btn-primary" type="button" onClick={() => handlePrivacyChange({ retention_days: settings.retention_days, screenshot_masking_enabled: settings.screenshot_masking_enabled })}>Save Privacy Policy</button>
        </div>
      </div>

      {activeModal === "screenshot" && (
        <ConfigureModal
          config={{
            title: "Configure Screenshot Interval",
            subtitle: "Set global capture frequency for all organization agents",
            icon: "camera",
            badgeLabel: "Enforced",
            presets: SCREENSHOT_PRESETS,
            min: 30,
            max: 3600,
            defaultSeconds: 60,
            note: "Propagates to {count} active desktop instances",
            quickLabel: "Quick select common frequencies",
            fineTuneTitle: "Fine-tune Interval",
            pendingLabel: "Pending value",
            resetLabel: "Reset to Default",
          }}
          initialSeconds={settings.screenshot_interval_seconds}
          agentCount={agentCount}
          onCancel={() => setActiveModal(null)}
          onApply={(seconds) => handleApply("screenshot_interval_seconds", seconds)}
        />
      )}

      {activeModal === "idle" && (
        <ConfigureModal
          config={{
            title: "Configure Idle Timeout",
            subtitle: "Set inactivity threshold before auto-pausing tracking",
            icon: "clock",
            badgeLabel: "Auto-Pause",
            presets: IDLE_PRESETS,
            min: 30,
            max: 3600,
            defaultSeconds: 300,
            note: "Applies to {count} active agents on next refresh",
            quickLabel: "Quick select common idle thresholds",
            fineTuneTitle: "Fine-tune Timeout",
            pendingLabel: "Organization default setting",
            resetLabel: "Reset to Default",
          }}
          initialSeconds={settings.idle_timeout_seconds}
          agentCount={agentCount}
          onCancel={() => setActiveModal(null)}
          onApply={(seconds) => handleApply("idle_timeout_seconds", seconds)}
        />
      )}

      {saving && <p className="subtitle">Saving...</p>}
    </div>
  );
}
