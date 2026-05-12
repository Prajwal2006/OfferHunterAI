"use client";

import { useEffect } from "react";
import clientLogger from "@/lib/client-logger";
import { useAuth } from "@/components/AuthProvider";

const LOG_ENDPOINT_PATH = "/debug/logs/frontend";

type PatchedWindow = Window & {
  __offerhunter_fetch_patched__?: boolean;
  __offerhunter_original_fetch__?: typeof fetch;
};

type ParsedError = {
  message: string;
  name?: string;
  stack?: string;
  raw?: string;
};

function toActionName(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_:-]/g, "")
    .slice(0, 120) || "unknown_action";
}

function pickActionableElement(target: EventTarget | null): HTMLElement | null {
  if (!(target instanceof HTMLElement)) return null;
  return target.closest(
    "button, a, [role='button'], input[type='button'], input[type='submit']"
  ) as HTMLElement | null;
}

function parseUnknownError(error: unknown): ParsedError {
  if (error instanceof Error) {
    return {
      message: error.message || error.name || "Unknown error",
      name: error.name,
      stack: error.stack,
    };
  }

  if (typeof error === "string") {
    return { message: error };
  }

  if (typeof error === "object" && error !== null) {
    const asRecord = error as Record<string, unknown>;
    const name = typeof asRecord.name === "string" ? asRecord.name : undefined;
    const message = typeof asRecord.message === "string" ? asRecord.message : undefined;
    let raw = "";
    try {
      raw = JSON.stringify(error);
    } catch {
      raw = String(error);
    }
    return {
      message: message || name || raw || "Unknown fetch error object",
      name,
      raw,
    };
  }

  return { message: "Unknown fetch error" };
}

function isAbortLikeError(error: unknown, signal?: AbortSignal): boolean {
  const parsed = parseUnknownError(error);
  if (signal?.aborted) return true;
  if (parsed.name && /abort/i.test(parsed.name)) return true;
  if (/abort|aborted|timeout/i.test(parsed.message)) return true;
  return false;
}

function isOptionalReviewFetch(url: string): boolean {
  return url.includes("/outreach/contacts/") || url.includes("/outreach/personalization/");
}

export function GlobalInteractionLogger() {
  const { session } = useAuth();

  useEffect(() => {
    clientLogger.setUserId(session?.user?.id ?? null);
  }, [session?.user?.id]);

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      const el = pickActionableElement(event.target);
      if (!el) return;

      const text = (el.textContent || "").trim().slice(0, 200);
      const href = el instanceof HTMLAnchorElement ? el.href : undefined;
      const explicitAction = el.getAttribute("data-action") || el.getAttribute("aria-label") || text;
      const action = toActionName(explicitAction || "clicked");

      clientLogger.logButtonClick("global-ui", action, {
        path: window.location.pathname,
        id: el.id || undefined,
        class_name: el.className || undefined,
        tag: el.tagName.toLowerCase(),
        text,
        href,
      });

      // Ensure users can see click logs quickly in the backend log file.
      void clientLogger.flushNow();
    };

    document.addEventListener("click", handleClick, true);
    return () => {
      document.removeEventListener("click", handleClick, true);
    };
  }, []);

  useEffect(() => {
    const win = window as PatchedWindow;
    if (win.__offerhunter_fetch_patched__) return;

    const originalFetch = window.fetch.bind(window);
    win.__offerhunter_original_fetch__ = originalFetch;
    win.__offerhunter_fetch_patched__ = true;

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof Request
            ? input.url
            : input.toString();
      const method = init?.method || "GET";

      if (url.includes(LOG_ENDPOINT_PATH)) {
        return originalFetch(input, init);
      }

      const started = performance.now();
      clientLogger.logApiCall(url, method, {
        path: window.location.pathname,
      });

      try {
        const response = await originalFetch(input, init);
        const durationMs = Math.round(performance.now() - started);
        clientLogger.logApiResponse(url, method, response.status, durationMs, {
          path: window.location.pathname,
        });
        return response;
      } catch (error) {
        const durationMs = Math.round(performance.now() - started);
        const parsed = parseUnknownError(error);

        // Timeouts/aborts are expected in some flows; log them as user action instead of hard error.
        if (isAbortLikeError(error, init?.signal ?? undefined)) {
          clientLogger.logUserAction("global_fetch_aborted", "global-fetch", {
            url,
            method,
            duration_ms: durationMs,
            path: window.location.pathname,
            error_name: parsed.name,
            error_message: parsed.message,
          });
          throw error;
        }

        if (isOptionalReviewFetch(url)) {
          clientLogger.logUserAction("global_optional_fetch_failed", "global-fetch", {
            url,
            method,
            duration_ms: durationMs,
            path: window.location.pathname,
            error_name: parsed.name,
            error_message: parsed.message,
          });
        } else {
          clientLogger.logError(
            "global_fetch_failed",
            parsed.message,
            {
              url,
              method,
              duration_ms: durationMs,
              path: window.location.pathname,
              error_name: parsed.name,
              raw_error: parsed.raw,
            },
            parsed.stack
          );
        }
        throw error;
      }
    };

    return () => {
      if (win.__offerhunter_original_fetch__) {
        window.fetch = win.__offerhunter_original_fetch__;
      }
      win.__offerhunter_fetch_patched__ = false;
      win.__offerhunter_original_fetch__ = undefined;
    };
  }, []);

  return null;
}
