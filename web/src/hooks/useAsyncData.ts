import { useEffect, useState } from "react";

type State<T> =
  | { status: "loading"; data: null; error: null }
  | { status: "ready"; data: T; error: null }
  | { status: "error"; data: null; error: Error };

/**
 * Minimal async-data hook used by the screens. It guards against setting state
 * after unmount (which would log a React warning) and re-runs when the
 * dependency key changes. `loader` is expected to be a stable reference to an
 * API client method result; `deps` keys the reload.
 */
export function useAsyncData<T>(loader: () => Promise<T>, deps: readonly unknown[]): State<T> {
  const [state, setState] = useState<State<T>>({ status: "loading", data: null, error: null });

  useEffect(() => {
    let active = true;
    setState({ status: "loading", data: null, error: null });
    loader()
      .then((data) => {
        if (active) setState({ status: "ready", data, error: null });
      })
      .catch((err: unknown) => {
        if (active) {
          const error = err instanceof Error ? err : new Error(String(err));
          setState({ status: "error", data: null, error });
        }
      });
    return () => {
      active = false;
    };
    // The caller passes the correct dependency key for the loader.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
