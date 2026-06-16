"use client";

import * as React from "react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { Toaster } from "sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30 * 1000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: "var(--white)",
            color: "var(--coffee-900)",
            border: "1px solid var(--coffee-300)",
            fontFamily:
              'var(--font-eb-garamond), "EB Garamond", Garamond, Georgia, serif',
          },
        }}
      />
    </QueryClientProvider>
  );
}
