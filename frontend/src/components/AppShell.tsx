import { useEffect } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Icon } from "./Icons";

const NAV = [
  { to: "/", label: "Overview", icon: "overview" as const, end: true },
  { to: "/documents", label: "Documents", icon: "document" as const },
  { to: "/analyses/new", label: "New analysis", icon: "plus" as const },
  { to: "/graph", label: "Graph explorer", icon: "graph" as const },
];

const TITLES: Record<string, string> = {
  "/": "Overview",
  "/documents": "Documents",
  "/analyses/new": "New analysis",
  "/graph": "Graph explorer",
};

function pageTitle(pathname: string): string {
  if (TITLES[pathname]) return TITLES[pathname];
  if (pathname.startsWith("/analyses/")) return "Review workspace";
  if (/^\/documents\/[^/]+\/ask$/.test(pathname)) return "Document assistant";
  return "Aarthik Gyan";
}

export function AppShell() {
  const location = useLocation();
  const title = pageTitle(location.pathname);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [location.pathname]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <span>
            <strong>Aarthik Gyan</strong>
            <small>Financial intelligence</small>
          </span>
        </Link>

        <nav className="side-nav" aria-label="Main navigation">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
            >
              <Icon name={item.icon} size={17} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-note">
          <span className="note-label">Human review</span>
          <p>Every estimate pauses for an analyst before a report is finalised.</p>
        </div>

        <div className="sidebar-footer">
          <span>Review workspace</span>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div>
            <p className="topbar-kicker">Aarthik Gyan / workspace</p>
            <h1>{title}</h1>
          </div>
          <div className="topbar-meta">
            <span className="pill pill-quiet">
              <Icon name="shield" size={14} />
              Human-reviewed
            </span>
          </div>
        </header>

        <main className="page">
          <Outlet />
        </main>

        <footer className="page-footer">
          <span>Aarthik Gyan</span>
          <span>Analytical estimates, not professional financial advice.</span>
        </footer>
      </div>
    </div>
  );
}
