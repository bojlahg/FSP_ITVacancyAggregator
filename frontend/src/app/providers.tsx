import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { bootstrapSession } from "@/api/client";
import { RouteFallback } from "@/components/RouteFallback";
import { useAuth } from "@/lib/auth";

/** До восстановления сессии (POST /auth/refresh) маршруты не рендерятся: guard'ы видят только итоговый статус. */
function SessionGate({ children }: { children: ReactNode }) {
  const { status } = useAuth();

  useEffect(() => {
    void bootstrapSession();
  }, []);

  return status === "unknown" ? <RouteFallback /> : children;
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <SessionGate>{children}</SessionGate>
    </QueryClientProvider>
  );
}
