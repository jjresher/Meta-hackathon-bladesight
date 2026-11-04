import { Link } from "react-router-dom";

import { ApiError } from "../api/client";
import type { AsyncState } from "../hooks/useAsyncData";
import { ToneGlyph } from "./icons";

export function Loading({ what }: { what: string }) {
  return (
    <div className="state skeleton" role="status">
      <p className="skeleton__status">Loading {what}…</p>
      <span className="skeleton__bar skeleton__bar--title" aria-hidden="true" />
      <span className="skeleton__bar" aria-hidden="true" />
      <span className="skeleton__bar skeleton__bar--block" aria-hidden="true" />
    </div>
  );
}

export function ErrorState({ what, error }: { what: string; error: Error }) {
  const missing = error instanceof ApiError && error.notFound;
  return (
    <div className="state state--error" role="alert">
      <p className="state__title">
        <ToneGlyph tone="alert" size={14} />
        {missing ? `${what} not found` : `Could not load ${what}`}
      </p>
      <p className="state__detail">{error.message}</p>
      <Link to="/" className="state__link">
        Back to the fleet
      </Link>
    </div>
  );
}

/** Renders the loading and error states of an async load; calls `children` once data is ready. */
export function Async<T>({
  state,
  what,
  children,
}: {
  state: AsyncState<T>;
  what: string;
  children: (data: T) => React.ReactNode;
}) {
  if (state.status === "loading") return <Loading what={what} />;
  if (state.status === "error") return <ErrorState what={what} error={state.error} />;
  return <>{children(state.data)}</>;
}
