import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { DashboardPage } from "./pages/DashboardPage";
import { ReviewPage } from "./pages/ReviewPage";

const JOB_STORAGE_KEY = "nas-diff.recent-jobs";

function readRecentJobs() {
  try {
    const raw = window.localStorage.getItem(JOB_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((value) => typeof value === "string") : [];
  } catch {
    return [];
  }
}

function routeLabel(pathname) {
  if (pathname === "/advanced") {
    return "Advanced";
  }
  if (pathname === "/review") {
    return "Review & Actions";
  }
  return "Simple Scan";
}

export default function App() {
  const location = useLocation();
  const [recentJobIds, setRecentJobIds] = useState(() => readRecentJobs());
  const [activeJobId, setActiveJobId] = useState(() => readRecentJobs()[0] || "");
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    window.localStorage.setItem(JOB_STORAGE_KEY, JSON.stringify(recentJobIds));
  }, [recentJobIds]);

  useEffect(() => {
    setIsMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!isMenuOpen) {
      return undefined;
    }

    function handlePointerDown(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsMenuOpen(false);
      }
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setIsMenuOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isMenuOpen]);

  const summary = useMemo(() => {
    if (!activeJobId) {
      return `${routeLabel(location.pathname)} active`;
    }
    return `${routeLabel(location.pathname)} · active job: ${activeJobId}`;
  }, [activeJobId, location.pathname]);

  function addRecentJob(jobId) {
    setActiveJobId(jobId);
    setRecentJobIds((prev) => {
      const next = [jobId, ...prev.filter((value) => value !== jobId)];
      return next.slice(0, 8);
    });
  }

  function selectJob(jobId) {
    if (!jobId) {
      return;
    }
    addRecentJob(jobId);
  }

  function removeRecentJob(jobId) {
    setRecentJobIds((prev) => {
      const next = prev.filter((value) => value !== jobId);
      setActiveJobId((current) => (current === jobId ? (next[0] || "") : current));
      return next;
    });
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1>NAS Diff Control Plane</h1>
          <p>{summary}</p>
        </div>
        <div className="topbar__actions" ref={menuRef}>
          <div className="topbar__current-route" aria-live="polite">
            <span className="hint">Flow</span>
            <strong>{routeLabel(location.pathname)}</strong>
          </div>
          <button
            type="button"
            className={`menu-toggle ${isMenuOpen ? "menu-toggle--open" : ""}`}
            aria-label="Open navigation menu"
            aria-expanded={isMenuOpen}
            aria-controls="primary-navigation"
            onClick={() => setIsMenuOpen((prev) => !prev)}
          >
            <span />
            <span />
            <span />
          </button>
          {isMenuOpen ? (
            <nav id="primary-navigation" className="menu-popover" aria-label="Primary">
              <NavLink to="/" end>
                Simple Scan
              </NavLink>
              <NavLink to="/advanced">Advanced</NavLink>
              <NavLink to="/review">Review & Actions</NavLink>
            </nav>
          ) : null}
        </div>
      </header>

      <main className="content">
        <Routes>
          <Route
            path="/"
            element={
              <DashboardPage
                variant="simple"
                activeJobId={activeJobId}
                recentJobIds={recentJobIds}
                onSelectJob={selectJob}
                onJobCreated={addRecentJob}
                onJobDeleted={removeRecentJob}
              />
            }
          />
          <Route
            path="/advanced"
            element={
              <DashboardPage
                variant="advanced"
                activeJobId={activeJobId}
                recentJobIds={recentJobIds}
                onSelectJob={selectJob}
                onJobCreated={addRecentJob}
                onJobDeleted={removeRecentJob}
              />
            }
          />
          <Route path="/scan" element={<Navigate to="/" replace />} />
          <Route
            path="/review"
            element={<ReviewPage activeJobId={activeJobId} recentJobIds={recentJobIds} onSelectJob={selectJob} />}
          />
        </Routes>
      </main>
    </div>
  );
}
