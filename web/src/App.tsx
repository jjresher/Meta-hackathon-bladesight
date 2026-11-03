import { NavLink, Route, Routes } from "react-router-dom";

import { api } from "./api/client";
import EvalScreen from "./screens/EvalScreen";
import FleetScreen from "./screens/FleetScreen";
import InspectionScreen from "./screens/InspectionScreen";
import ReportsScreen from "./screens/ReportsScreen";
import RunsScreen from "./screens/RunsScreen";

const NAV = [
  { to: "/", label: "Fleet", end: true },
  { to: "/reports", label: "Work orders", end: false },
  { to: "/runs", label: "Agent trace", end: false },
  { to: "/eval", label: "Evaluation", end: false },
];

/**
 * Application shell and router. Screen bodies are built out in later features;
 * this shell wires all five routes and the honest farm label.
 */
export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">
          <span className="app-brand__mark" aria-hidden="true">
            BS
          </span>
          <div>
            <p className="app-brand__name">BladeSight</p>
            <p className="app-brand__tagline">{api.getFarmLabel()}</p>
          </div>
        </div>
        <nav className="app-nav" aria-label="Primary">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                isActive ? "app-nav__link app-nav__link--active" : "app-nav__link"
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<FleetScreen />} />
          <Route path="/inspections/:id" element={<InspectionScreen />} />
          <Route path="/reports" element={<ReportsScreen />} />
          <Route path="/runs" element={<RunsScreen />} />
          <Route path="/eval" element={<EvalScreen />} />
          <Route path="*" element={<FleetScreen />} />
        </Routes>
      </main>
    </div>
  );
}
