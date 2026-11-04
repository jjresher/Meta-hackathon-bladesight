import { useEffect, useState } from "react";

export type AsyncState<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; error: Error };

/**
 * Runs `loader` on mount and whenever `deps` change. A result that arrives after the component
 * unmounted or the deps changed is ignored, so a fast navigation never shows stale data.
 */
export function useAsyncData<T>(loader: () => Promise<T>, deps: readonly unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading" });

  useEffect(() => {
    let active = true;
    setState({ status: "loading" });
    loader().then(
      (data) => {
        if (active) setState({ status: "ready", data });
      },
      (err: unknown) => {
        if (active) setState({ status: "error", error: err instanceof Error ? err : new Error(String(err)) });
      },
    );
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
