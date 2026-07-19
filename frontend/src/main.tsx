import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
// Fontsource: index.css references 'DM Sans Variable' / 'Noto Serif Variable' in
// font-family stacks — these imports actually load the faces. Without them the
// browser silently falls back to generic sans/serif (the npm packages were dead weight).
import "@fontsource-variable/dm-sans";
import "@fontsource-variable/noto-serif";
import "./index.css";

// Daily-grade market data; backend caches 4–24h and sends Cache-Control: max-age=300.
// 1-minute staleTime avoids hammering the 200rpm rate limiter for unchanged data.
// (Agent 4 shortens this only for /api/fetch/status while a job is running.)
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
    // Belt-and-suspenders: any mutation without its own onError still logs.
    mutations: {
      onError: (e) => console.error("[mutation]", (e as Error).message),
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
