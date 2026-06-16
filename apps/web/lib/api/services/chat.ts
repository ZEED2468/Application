import type {
  ChatAnswerRequest,
  ChatGenerateResult,
  ChatSession,
} from "@jd/shared-types";
import { api, path } from "../client";

export const chatService = {
  async createSession(jdText: string): Promise<ChatSession> {
    return api
      .post(path("/api/chat/sessions"), { json: { jd_text: jdText } })
      .json<ChatSession>();
  },

  async getSession(id: string): Promise<ChatSession> {
    return api.get(path(`/api/chat/sessions/${id}`)).json<ChatSession>();
  },

  async answer(id: string, body: ChatAnswerRequest): Promise<ChatSession> {
    return api
      .post(path(`/api/chat/sessions/${id}/answer`), { json: body })
      .json<ChatSession>();
  },

  async generate(id: string): Promise<ChatGenerateResult> {
    return api
      .post(path(`/api/chat/sessions/${id}/generate`))
      .json<ChatGenerateResult>();
  },
};
