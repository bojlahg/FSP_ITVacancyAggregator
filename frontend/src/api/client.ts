import createClient, { type Middleware } from "openapi-fetch";
import { authStore } from "@/lib/auth";
import type { paths } from "./schema";

const authMiddleware: Middleware = {
  onRequest({ request }) {
    const { accessToken } = authStore.get();
    if (accessToken) {
      request.headers.set("Authorization", `Bearer ${accessToken}`);
    }
    return request;
  },
  // TODO: на 401 — POST /auth/refresh (refresh-токен в httpOnly cookie) и повтор запроса.
};

export const api = createClient<paths>({
  baseUrl: "/api/v1",
  credentials: "include",
});

api.use(authMiddleware);
