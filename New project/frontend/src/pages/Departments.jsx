import { useEffect, useState } from "react";
import { Building2, Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { createDepartment, deleteDepartment, getCurrentUser, listDepartments, updateDepartment } from "../api";

export default function Departments() {
  const [currentUser, setCurrentUser] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [name, setName] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadDepartments() {
    const departmentList = await listDepartments();
    setDepartments(departmentList);
  }

  useEffect(() => {
    Promise.all([getCurrentUser(), listDepartments()])
      .then(([user, departmentList]) => {
        setCurrentUser(user);
        setDepartments(departmentList);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (!loading && !["superadmin", "admin"].includes(currentUser?.role)) {
    return <main className="department-page"><h1>Departments</h1><p className="subtitle">Department creation is restricted to Admins and Super Admins.</p></main>;
  }

  const isSuperAdmin = currentUser?.role === "superadmin";
  const pageScopeLabel = isSuperAdmin ? "Organization departments" : "Your departments";

  async function handleCreate(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setSaving(true);
    try {
      await createDepartment(name.trim());
      setName("");
      await loadDepartments();
      setNotice("Department created.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleRename(event, departmentId) {
    event.preventDefault();
    setError("");
    setNotice("");
    setSaving(true);
    try {
      await updateDepartment(departmentId, editingName.trim());
      setEditingId(null);
      setEditingName("");
      await loadDepartments();
      setNotice("Department updated.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(department) {
    setError("");
    setNotice("");
    try {
      await deleteDepartment(department.id);
      await loadDepartments();
      setNotice(`${department.name} deleted.`);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="department-page">
      <header className="department-header">
        <div className="department-heading-icon"><Building2 size={22} aria-hidden="true" /></div>
        <div><h1>Departments</h1><p className="subtitle">{isSuperAdmin ? "View and manage all departments." : "Create and manage departments only you and Super Admins can see."}</p></div>
      </header>

      {error && <div className="alert-error" role="alert">{error}</div>}
      {notice && <div className="alert-success" role="status">{notice}</div>}

      {["superadmin", "admin"].includes(currentUser?.role) && (
        <section className="department-create table-card">
          <div><h2>Create department</h2><p className="subtitle">{isSuperAdmin ? "Departments are available when assigning members." : "Only you and Super Admins can see departments you create."}</p></div>
          <form onSubmit={handleCreate}>
            <input aria-label="Department name" placeholder="Department name" maxLength={120} required value={name} onChange={(event) => setName(event.target.value)} />
            <button type="submit" className="btn-primary" disabled={saving || !name.trim()}><Plus size={16} />Create Department</button>
          </form>
        </section>
      )}

      <section className="department-list table-card">
        <div className="department-list-heading"><h2>{pageScopeLabel}</h2><span>{departments.length} total</span></div>
        {loading ? <p className="department-empty">Loading departments...</p> : departments.length ? (
          <div className="department-rows">
            {departments.map((department) => (
              <div className="department-row" key={department.id}>
                <div className="department-name-cell"><span className="department-row-icon"><Building2 size={17} /></span>
                  {editingId === department.id ? (
                    <form className="department-rename-form" onSubmit={(event) => handleRename(event, department.id)}>
                      <input autoFocus required maxLength={120} value={editingName} onChange={(event) => setEditingName(event.target.value)} aria-label={`Rename ${department.name}`} />
                      <button type="submit" disabled={saving || !editingName.trim()} title="Save name" aria-label="Save name"><Check size={16} /></button>
                      <button type="button" onClick={() => setEditingId(null)} title="Cancel" aria-label="Cancel rename"><X size={16} /></button>
                    </form>
                  ) : <strong>{department.name}</strong>}
                </div>
                {isSuperAdmin && editingId !== department.id && (
                  <div className="department-row-actions">
                    <button type="button" onClick={() => { setEditingId(department.id); setEditingName(department.name); }} title={`Edit ${department.name}`} aria-label={`Edit ${department.name}`}><Pencil size={16} /></button>
                    <button type="button" className="department-delete" onClick={() => handleDelete(department)} title={`Delete ${department.name}`} aria-label={`Delete ${department.name}`}><Trash2 size={16} /></button>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : <p className="department-empty">No departments yet. Create one to assign members.</p>}
      </section>
    </main>
  );
}