import { useEffect, useState } from "react";
import { acknowledgeAlert, listAlerts } from "../api";

function formatDate(value) {
  return new Date(value).toLocaleString();
}

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [status, setStatus] = useState("open");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadAlerts() {
    setLoading(true);
    try {
      setAlerts(await listAlerts(status));
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAlerts();
  }, [status]);

  async function handleAcknowledge(alertId) {
    await acknowledgeAlert(alertId);
    await loadAlerts();
  }

  return (
    <div>
      <div className="page-title-row">
        <div>
          <h1>Security Alerts</h1>
          <p className="subtitle">Review evidence-based signals from employee devices.</p>
        </div>
        <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Alert status">
          <option value="open">Open</option>
          <option value="acknowledged">Acknowledged</option>
        </select>
      </div>
      {error && <div className="alert-error">{error}</div>}
      {loading && <div className="loading-state">Loading...</div>}
      {!loading && alerts.length === 0 && <div className="card empty-state">No alerts in this view.</div>}
      {!loading && alerts.length > 0 && (
        <div className="table-card alert-list">
          <table>
            <thead><tr><th>Severity</th><th>Type</th><th>Message</th><th>Evidence</th><th>Created</th><th /></tr></thead>
            <tbody>
              {alerts.map((alert) => (
                <tr key={alert.id}>
                  <td><span className={`pill pill-${alert.severity}`}>{alert.severity}</span></td>
                  <td>{alert.alert_type}</td>
                  <td>{alert.message}</td>
                  <td><code>{JSON.stringify(alert.evidence || {})}</code></td>
                  <td>{formatDate(alert.created_at)}</td>
                  <td>{alert.status === "open" && <button className="btn-view" onClick={() => handleAcknowledge(alert.id)}>Acknowledge</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}