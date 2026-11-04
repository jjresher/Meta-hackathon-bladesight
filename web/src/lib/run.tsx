import { createContext, useContext, useEffect, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { api, type RunProvider } from "../api/client";
import { useAsyncData } from "../hooks/useAsyncData";
import type { ReplaySet } from "../types";

const PROVIDERS: readonly RunProvider[] = ["meta", "baseten"];
const isProvider = (value: string | null): value is RunProvider =>
  value != null && (PROVIDERS as readonly string[]).includes(value);

interface RunContext {
  /** What to pass to the API: undefined means "the API's default replay". */
  provider: RunProvider | undefined;
  /** The replay being shown, once `/api/replays` answered (null on an API without it). */
  current: ReplaySet | null;
  replays: ReplaySet[];
  choose: (provider: RunProvider, pathname?: string) => void;
}

const Ctx = createContext<RunContext>({ provider: undefined, current: null, replays: [], choose: () => {} });

/**
 * The global run selector state. The URL (`?provider=meta|baseten`) is the source of truth; a
 * choice made here sticks across in-app links, which do not carry the parameter, by putting it
 * back on the URL. With no choice the API's default replay is served (`ReplaySet.default`).
 */
export function RunScope({ children }: { children: React.ReactNode }) {
  const [params] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const fromUrl = params.get("provider");
  const [sticky, setSticky] = useState<RunProvider | undefined>(isProvider(fromUrl) ? fromUrl : undefined);
  const provider = isProvider(fromUrl) ? fromUrl : sticky;

  useEffect(() => {
    if (isProvider(fromUrl) && fromUrl !== sticky) setSticky(fromUrl);
    if (!fromUrl && sticky) {
      const next = new URLSearchParams(location.search);
      next.set("provider", sticky);
      navigate({ pathname: location.pathname, search: `?${next}`, hash: location.hash }, { replace: true });
    }
  }, [fromUrl, sticky, location, navigate]);

  const loaded = useAsyncData(() => api.replays().catch(() => [] as ReplaySet[]), []);
  const replays = loaded.status === "ready" ? loaded.data : [];
  const current = replays.find((r) => r.provider === provider) ?? replays.find((r) => r.default) ?? null;

  const choose = (next: RunProvider, to?: string) => {
    setSticky(next);
    const search = new URLSearchParams(location.search);
    search.set("provider", next);
    // A run id belongs to one replay: go to the chosen replay's latest run instead.
    const pathname = to ?? (location.pathname.startsWith("/runs/") ? "/runs" : location.pathname);
    navigate({ pathname, search: `?${search}`, hash: location.hash });
  };

  return <Ctx.Provider value={{ provider, current, replays, choose }}>{children}</Ctx.Provider>;
}

export const useRun = (): RunContext => useContext(Ctx);
