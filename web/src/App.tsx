import { NavLink, Route, Routes } from "react-router-dom";

import { api, SCHEMA_VERSION } from "./api/client";
import { BrandMark } from "./components/icons";
import { useAsyncData } from "./hooks/useAsyncData";
import EvalScreen from "./screens/EvalScreen";
import FleetScreen from "./screens/FleetScreen";
import InspectionScreen from "./screens/InspectionScreen";
import RunsScreen from "./screens/RunsScreen";
import WorkOrdersScreen from "./screens/WorkOrdersScreen";

const NAV = [
  { to: "/", label: "Fleet", end: true },
  { to: "/work-orders", label: "Work orders", end: false },
  { to: "/runs", label: "Agent trace", end: false },
  { to: "/eval", label: "Evaluation", end: false },
];

function ModeBadge() {
  const health = useAsyncData(() => api.health(), []);
  if (health.status === "loading") return null;
  if (health.status === "error") {
    return (
      <span className="mode mode--down" role="status" title={health.error.message}>
        API unreachable
      </span>
    );
  }
  const { mode, schema_version: schema } = health.data;
  return (
    <span
      className={`mode mode--${mode}`}
      role="status"
      title={
        mode === "replay"
          ? "Recorded results are served: no live model call is made while you browse."
          : "Live mode: the API can call models."
      }
    >
      {mode === "replay" ? "Replay mode" : "Live mode"}
      {schema !== SCHEMA_VERSION && <span className="mode__warn"> · schema {schema}, UI expects {SCHEMA_VERSION}</span>}
    </span>
  );
}

export default function App() {
  return (
    <div className="app-shell">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="app-header">
        <NavLink to="/" className="app-brand" aria-label="BladeSight, fleet">
          <BrandMark size={30} />
          <span className="app-brand__text">
            <span className="app-brand__name">BladeSight</span>
            <span className="app-brand__tagline">Synthetic farm of real DTU photos</span>
          </span>
        </NavLink>
        <nav className="app-nav" aria-label="Primary">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "app-nav__link is-active" : "app-nav__link")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <ModeBadge />
      </header>

      <main id="main" className="app-main">
        <Routes>
          <Route path="/" element={<FleetScreen />} />
          <Route path="/inspections/:id" element={<InspectionScreen />} />
          <Route path="/work-orders" element={<WorkOrdersScreen />} />
          <Route path="/runs" element={<RunsScreen />} />
          <Route path="/runs/:id" element={<RunsScreen />} />
          <Route path="/eval" element={<EvalScreen />} />
          <Route path="*" element={<FleetScreen />} />
        </Routes>
      </main>

      <footer className="app-footer">
        Built for the Meta Global AI Developer Hackathon · dataset: DTU wind turbine blade inspection images, CC BY-NC 4.0 ·
        severity is advisory
      </footer>
    </div>
  );
}
