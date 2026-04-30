"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { session, loading } = useAuth();

  useEffect(() => {
    if (!loading && !session) {
      router.replace(`/login?next=${encodeURIComponent(pathname || "/")}`);
    }
  }, [loading, session, router, pathname]);

  if (loading || !session) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center text-sm text-muted-foreground">
        Checking your session...
      </div>
    );
  }

  return <>{children}</>;
}
