import type { LlmKey, LlmKeyInput } from "@jd/shared-types";
import { api, path } from "../client";

export const settingsService = {
  async listLlmKeys(): Promise<LlmKey[]> {
    return api.get(path("/api/settings/llm-keys")).json<LlmKey[]>();
  },

  async upsertLlmKey(input: LlmKeyInput): Promise<LlmKey> {
    return api
      .post(path("/api/settings/llm-keys"), { json: input })
      .json<LlmKey>();
  },

  async validateLlmKey(provider: string): Promise<LlmKey> {
    return api
      .post(path(`/api/settings/llm-keys/${provider}/validate`), { timeout: 30000 })
      .json<LlmKey>();
  },

  async setPreferred(provider: string): Promise<LlmKey> {
    return api
      .put(path(`/api/settings/llm-keys/${provider}/preferred`))
      .json<LlmKey>();
  },

  async deleteLlmKey(provider: string): Promise<void> {
    await api.delete(path(`/api/settings/llm-keys/${provider}`));
  },
};
