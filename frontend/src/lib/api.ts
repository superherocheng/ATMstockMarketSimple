import axios, { type AxiosError } from "axios";

// Relative "/api" base works in BOTH:
//   - dev:  Vite proxies /api -> http://localhost:5656 (vite.config.ts)
//   - prod: FastAPI serves the SPA same-origin, /api is local.
// NEVER hardcode a host — that breaks one of the two modes.
export const api = axios.create({
  baseURL: "/api",
  timeout: 15_000,
});

// Attach the Bearer token if the build injected one (production write-ops).
// Dev runs without API_TOKEN (internal mode), so this is a no-op there.
api.interceptors.request.use((config) => {
  const token = import.meta.env.VITE_API_TOKEN;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  // Cache-buster: the backend sends Cache-Control: max-age=300 on /api GETs,
  // so the browser would otherwise serve a stale body for up to 5 min — defeating
  // a react-query refetch triggered after a data-refresh job. Appending _<ts>
  // makes react-query's staleTime the single freshness authority; backend Redis
  // still caches, so this only adds a network hop when react-query actually refetches.
  config.params = { ...(config.params ?? {}), _: Date.now() };
  return config;
});

// Normalize failures into a friendly Error. The backend's global handler returns
// { success:false, error, timestamp } on 5xx; some paths return {error} or {detail}.
// Pull the best message we can so react-query isError / mutation onError show
// something useful instead of "Request failed with status code N".
api.interceptors.response.use(
  (r) => {
    // _cached_persistent returns HTTP 200 with body {error:...} on compute failure
    // (documented in schemas.py). Detect that bare envelope here so every read hook
    // sees isError instead of rendering a half-shaped payload (white screen).
    const d = r.data;
    if (
      d && typeof d === "object" && !Array.isArray(d) &&
      Object.keys(d).length === 1 && typeof (d as { error?: unknown }).error === "string"
    ) {
      return Promise.reject(new Error((d as { error: string }).error));
    }
    return r;
  },
  (err: AxiosError<{ error?: string; detail?: string }>) => {
    const data = err.response?.data;
    const status = err.response?.status;
    const friendly =
      data?.error ??
      data?.detail ??
      (status === 401
        ? "未授权：API Token 缺失或无效"
        : status === 403
          ? "CSRF 校验失败或跨域被拒"
          : status === 429
            ? "请求过于频繁，稍后再试"
            : err.message);
    return Promise.reject(new Error(friendly));
  },
);
