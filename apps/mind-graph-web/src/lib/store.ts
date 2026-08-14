/** UI state. Small, serialisable into a saved View (Frontend/06 §3.1). */
import { create } from "zustand";

export type Surface = "bench" | "map" | "sources" | "log" | "share";
export type SideTab = "explain" | "review" | "sources";

interface UI {
  surface: Surface;
  side: SideTab;
  selected: string | null;
  lens: string | undefined;
  reducedMotion: boolean;
  highContrast: boolean;
  cvdSafe: boolean;
  set: (p: Partial<UI>) => void;
}

export const useUI = create<UI>((set) => ({
  surface: "bench",
  side: "explain",
  selected: null,
  lens: undefined,
  reducedMotion: false,
  highContrast: false,
  cvdSafe: false,
  set: (p) => set(p),
}));
