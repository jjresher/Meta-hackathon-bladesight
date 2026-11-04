import { STAGE_SHORT, modelLabel, stagesByModel } from "../lib/models";
import { useRun } from "../lib/run";

/**
 * Which stored run the whole app shows, and which model ran each stage of it (from
 * `/api/replays`). Hidden when the API stores a single replay or does not list them.
 */
export default function RunBar() {
  const { current, replays, choose } = useRun();
  if (replays.length < 2 || !current) return null;
  const groups = stagesByModel(current.stages, STAGE_SHORT);

  return (
    <div className="run-bar" data-testid="run-bar">
      <fieldset className="run-pick">
        <legend className="run-pick__legend">Run</legend>
        {replays.map((replay) => {
          const agent = replay.stages.find((s) => s.stage === "agent");
          const label = agent ? modelLabel(agent.model, agent.provider) : replay.label;
          const on = replay.provider === current.provider;
          return (
            <label key={replay.provider} className={`run-pick__item${on ? " is-active" : ""}`} title={replay.label}>
              <input
                type="radio"
                name="run-provider"
                value={replay.provider}
                checked={on}
                onChange={() => choose(replay.provider)}
                data-testid={`run-${replay.provider}`}
              />
              {label}
            </label>
          );
        })}
      </fieldset>
      <p className="run-bar__stages" data-testid="run-stages">
        <span className="visually-hidden">Which model ran each stage: </span>
        {groups.map(([label, stages], i) => (
          <span key={label} className="run-bar__group">
            {i > 0 && <span aria-hidden="true"> · </span>}
            <span className="run-bar__stage-names">{stages.join(", ")}:</span> {label}
          </span>
        ))}
      </p>
    </div>
  );
}
