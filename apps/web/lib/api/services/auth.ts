import type { LoginRequest, MeResponse, RegisterRequest } from "@jd/shared-types";
import { api, path } from "../client";

export const authService = {
  async login(body: LoginRequest): Promise<MeResponse> {
    return api.post(path("/api/auth/login"), { json: body }).json<MeResponse>();
  },

  async register(body: RegisterRequest): Promise<MeResponse> {
    return api
      .post(path("/api/auth/register"), { json: body })
      .json<MeResponse>();
  },

  async me(): Promise<MeResponse> {
    return api.get(path("/api/auth/me")).json<MeResponse>();
  },

  async logout(): Promise<void> {
    await api.post(path("/api/auth/logout"), { throwHttpErrors: false });
  },

  async refresh(): Promise<boolean> {
    const res = await api.post(path("/api/auth/refresh"), {
      throwHttpErrors: false,
    });
    return res.ok;
  },
};
