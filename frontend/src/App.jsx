import { useEffect, useMemo, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";

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

export default function App() {
  const [recentJobIds, setRecentJobIds] = useState(() => readRecentJobs());
  const [activeJobId, setActiveJobId] = useState(() => readRecentJobs()[0] || "");

  useEffect(() => {
    window.localStorage.setItem(JOB_STORAGE_KEY, JSON.stringify(recentJobIds));
  }, [recentJobIds]);

  const summary = useMemo(() => {
    if (!activeJobId) {
      return "No active scan job selected";
    }
    return `Active job: ${activeJobId}`;
  }, [activeJobId]);

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
        <nav className="nav">
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/review">Review & Actions</NavLink>
        </nav>
      </header>

      <main className="content">
        <Routes>
          <Route
            path="/"
            element={
              <DashboardPage
                activeJobId={activeJobId}
                recentJobIds={recentJobIds}
                onSelectJob={selectJob}
                onJobCreated={addRecentJob}
                onJobDeleted={removeRecentJob}
              />
            }
          />
          <Route
            path="/review"
            element={<ReviewPage activeJobId={activeJobId} recentJobIds={recentJobIds} onSelectJob={selectJob} />}
          />
        </Routes>
      </main>
    </div>
  );
}
