/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Origin of the API for a dev build; empty means same-origin. */
  readonly VITE_API_BASE?: string;
}
