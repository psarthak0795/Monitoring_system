import { useEffect, useState } from "react";
  import { useSearchParams } from "react-router-dom";
  import { listScreenshots } from "../api";
  import useScreenshotImageUrls from "../hooks/useScreenshotImageUrls";

  export default function Screenshots() {
    const [searchParams] = useSearchParams();
    const timeEntryId = searchParams.get("time_entry_id") || undefined;
    const userId = searchParams.get("user_id") || undefined;
    const [shots, setShots] = useState([]);
    const [selected, setSelected] = useState(null);
    const imageUrls = useScreenshotImageUrls(shots);

    useEffect(() => {
      let mounted = true;
      const refresh = () => listScreenshots(userId, timeEntryId).then((items) => {
        if (mounted) setShots(items);
      });
      refresh();
      const interval = setInterval(refresh, 10000);
      return () => {
        mounted = false;
        clearInterval(interval);
      };
    }, [userId, timeEntryId]);

    useEffect(() => {
      function onKeyDown(e) {
        if (e.key === "Escape") setSelected(null);
      }
      window.addEventListener("keydown", onKeyDown);
      return () => window.removeEventListener("keydown", onKeyDown);
    }, []);

    return (
      <div>
        <h1>Screenshots</h1>
        <div className="screenshot-grid">
          {shots.map((s) => (
            <div key={s.id} className="card">
              <img
                src={imageUrls[s.id] || undefined}
                alt={`Screenshot ${s.id}`}
                onClick={() => setSelected(s)}
              />
              <div>{new Date(s.captured_at).toLocaleString()}</div>
              <div>IP: {s.ip_address}</div>
            </div>
          ))}
          {shots.length === 0 && <p>No screenshots found.</p>}
        </div>

        {selected && (
          <div className="lightbox-overlay" onClick={() => setSelected(null)}>
            <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
              <button className="lightbox-close" onClick={() => setSelected(null)}>✕</button>
              <img src={imageUrls[selected.id] || undefined} alt={`Screenshot ${selected.id}`} />
              <div className="lightbox-caption">
                {new Date(selected.captured_at).toLocaleString()} — IP: {selected.ip_address}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }