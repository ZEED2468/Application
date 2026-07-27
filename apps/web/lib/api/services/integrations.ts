import type { Integration, IntegrationTemplate } from "@jd/shared-types";
import { api, path } from "../client";

export interface IntegrationInput {
  template?: string | null;
  name?: string;
  provider?: string;
  base_url?: string;
  api_key?: string;
  model?: string;
  config?: Record<string, unknown>;
}

export const integrationsService = {
  async templates(): Promise<IntegrationTemplate[]> {
    return api.get(path("/api/integrations/templates")).json<IntegrationTemplate[]>();
  },
  async list(): Promise<Integration[]> {
    return api.get(path("/api/integrations")).json<Integration[]>();
  },
  async create(body: IntegrationInput): Promise<Integration> {
    return api.post(path("/api/integrations"), { json: body }).json<Integration>();
  },
  async update(id: string, body: IntegrationInput): Promise<Integration> {
    return api.put(path(`/api/integrations/${id}`), { json: body }).json<Integration>();
  },
  async remove(id: string): Promise<void> {
    await api.delete(path(`/api/integrations/${id}`));
  },
  async setDefault(id: string): Promise<Integration> {
    return api.put(path(`/api/integrations/${id}/default`)).json<Integration>();
  },
  async validate(id: string): Promise<Integration> {
    return api.post(path(`/api/integrations/${id}/validate`), { timeout: 30000 }).json<Integration>();
  },
  async discoverModels(id: string): Promise<Integration> {
    return api.get(path(`/api/integrations/${id}/models/discover`), { timeout: 30000 }).json<Integration>();
  },
  async addModel(id: string, model: string): Promise<Integration> {
    return api.post(path(`/api/integrations/${id}/models`), { json: { model } }).json<Integration>();
  },
};
