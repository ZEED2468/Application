import { create } from "zustand";
import type { IntegrationTemplate } from "@jd/shared-types";

/** UI-only state for the AI Integrations dashboard (dialog / wizard). Server data
 *  lives in TanStack Query. */
interface IntegrationsUiState {
  formOpen: boolean;
  template: IntegrationTemplate | null;
  editingId: string | null;
  openCreate: (t: IntegrationTemplate) => void;
  openEdit: (t: IntegrationTemplate | null, id: string) => void;
  close: () => void;
}

export const useIntegrationsUi = create<IntegrationsUiState>((set) => ({
  formOpen: false,
  template: null,
  editingId: null,
  openCreate: (t) => set({ formOpen: true, template: t, editingId: null }),
  openEdit: (t, id) => set({ formOpen: true, template: t, editingId: id }),
  close: () => set({ formOpen: false, template: null, editingId: null }),
}));
