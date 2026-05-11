/**
 * Comprehensive client-side logging utility for OfferHunter AI.
 * Handles all frontend events, button clicks, API calls, and errors.
 * All events are timestamped and sent to the backend.
 */

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
const FRONTEND_LOG_ENDPOINT = `${API_URL}/debug/logs/frontend`;
const FRONTEND_LOG_FALLBACK_ENDPOINT = "/api/debug/logs/frontend";
const SESSION_ID = typeof window !== "undefined" ? generateSessionId() : "";

function generateSessionId(): string {
  if (typeof window === "undefined") return "";
  const stored = sessionStorage.getItem("__offerhunter_session_id");
  if (stored) return stored;
  const newId = crypto.randomUUID ? crypto.randomUUID() : `session-${Date.now()}-${Math.random()}`;
  sessionStorage.setItem("__offerhunter_session_id", newId);
  return newId;
}

export interface LogEvent {
  timestamp: string;
  session_id: string;
  event_type: "button_click" | "api_call" | "api_response" | "error" | "performance" | "user_action";
  component: string;
  action?: string;
  endpoint?: string;
  method?: string;
  status_code?: number;
  duration_ms?: number;
  error_message?: string;
  error_type?: string;
  details?: Record<string, unknown>;
  level: "info" | "warning" | "error" | "debug";
}

class ClientLogger {
  private logBuffer: LogEvent[] = [];
  private bufferSize = 50;
  private flushInterval = 5000; // 5 seconds
  private userId: string | null = null;

  constructor() {
    if (typeof window !== "undefined") {
      // Auto-flush logs periodically
      setInterval(() => this.flush(), this.flushInterval);
      
      // Flush on page unload
      window.addEventListener("beforeunload", () => {
        this.flush();
      });
      
      // Flush when buffer reaches size limit
      this.setupAutoFlush();
    }
  }

  setUserId(userId: string | null) {
    this.userId = userId;
  }

  private setupAutoFlush() {
    // Flush when buffer reaches limit
    const originalPush = this.logBuffer.push.bind(this.logBuffer);
    const self = this;
    this.logBuffer.push = function (...items: LogEvent[]) {
      const result = originalPush(...items);
      if (self.logBuffer.length >= self.bufferSize) {
        self.flush();
      }
      return result;
    };
  }

  private safeSerialize(value: unknown): unknown {
    try {
      const serialized = JSON.stringify(value ?? {});
      if (serialized.length <= 3000) return value;
      return `${serialized.slice(0, 3000)}...[truncated]`;
    } catch {
      return String(value);
    }
  }

  private async postLogs(body: string): Promise<void> {
    // Primary target: backend FastAPI logging endpoint.
    try {
      const primary = await fetch(FRONTEND_LOG_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
        keepalive: true,
      });
      if (primary.ok) {
        return;
      }
    } catch {
      // Fall through to local fallback endpoint.
    }

    // Fallback target: local Next.js API route that appends to root logs file.
    await fetch(FRONTEND_LOG_FALLBACK_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    });
  }

  private createLogEntry(event: Partial<LogEvent>): LogEvent {
    return {
      timestamp: new Date().toISOString(),
      session_id: SESSION_ID,
      event_type: (event.event_type as LogEvent["event_type"]) || "user_action",
      component: event.component || "unknown",
      level: event.level || "info",
      ...event,
    };
  }

  logButtonClick(
    component: string,
    action: string,
    details?: Record<string, unknown>,
    userId?: string
  ) {
    const entry = this.createLogEntry({
      event_type: "button_click",
      component,
      action,
      details: this.safeSerialize(details),
      level: "info",
    });
    this.logBuffer.push(entry);
    console.log(`[${component}] Button clicked: ${action}`, details);
  }

  logApiCall(
    endpoint: string,
    method: string = "GET",
    details?: Record<string, unknown>,
    userId?: string
  ) {
    const entry = this.createLogEntry({
      event_type: "api_call",
      component: "api-client",
      endpoint,
      method,
      details: this.safeSerialize(details),
      level: "info",
    });
    this.logBuffer.push(entry);
    console.log(`[API] ${method} ${endpoint}`, details);
  }

  logApiResponse(
    endpoint: string,
    method: string,
    statusCode: number,
    durationMs: number,
    details?: Record<string, unknown>,
    userId?: string
  ) {
    const entry = this.createLogEntry({
      event_type: "api_response",
      component: "api-client",
      endpoint,
      method,
      status_code: statusCode,
      duration_ms: durationMs,
      details: this.safeSerialize(details),
      level: statusCode >= 400 ? "warning" : "info",
    });
    this.logBuffer.push(entry);
    console.log(`[API] ${method} ${endpoint} - ${statusCode} (${durationMs}ms)`, details);
  }

  logError(
    errorType: string,
    message: string,
    context?: Record<string, unknown>,
    errorStack?: string,
    userId?: string
  ) {
    const entry = this.createLogEntry({
      event_type: "error",
      component: "client",
      error_type: errorType,
      error_message: message,
      details: {
        context: this.safeSerialize(context),
        stack: errorStack?.substring(0, 1000),
      },
      level: "error",
    });
    this.logBuffer.push(entry);
    console.error(`[ERROR] ${errorType}: ${message}`, context, errorStack);
  }

  logPerformance(
    operation: string,
    durationMs: number,
    threshold?: number,
    details?: Record<string, unknown>,
    userId?: string
  ) {
    const isSlow = threshold ? durationMs > threshold : false;
    const entry = this.createLogEntry({
      event_type: "performance",
      component: "performance",
      action: operation,
      duration_ms: durationMs,
      details: {
        ...this.safeSerialize(details),
        is_slow: isSlow,
        threshold,
      },
      level: isSlow ? "warning" : "info",
    });
    this.logBuffer.push(entry);
    if (isSlow) {
      console.warn(`[PERF] ${operation} took ${durationMs}ms (threshold: ${threshold}ms)`, details);
    }
  }

  logUserAction(
    action: string,
    component: string,
    details?: Record<string, unknown>,
    userId?: string
  ) {
    const entry = this.createLogEntry({
      event_type: "user_action",
      component,
      action,
      details: this.safeSerialize(details),
      level: "info",
    });
    this.logBuffer.push(entry);
    console.log(`[${component}] User action: ${action}`, details);
  }

  private async flush() {
    if (this.logBuffer.length === 0 || typeof window === "undefined") return;

    const logsToSend = [...this.logBuffer];
    this.logBuffer = [];

    try {
      const body = JSON.stringify({
        logs: logsToSend,
        user_id: this.userId,
        session_id: SESSION_ID,
      });

      await this.postLogs(body);
    } catch (error) {
      console.error("[Logger] Failed to send logs:", error);
      // Re-add logs to buffer for retry
      this.logBuffer.unshift(...logsToSend);
    }
  }

  async flushNow() {
    await this.flush();
  }

  getBufferSize(): number {
    return this.logBuffer.length;
  }
}

// Global logger instance
export const clientLogger = new ClientLogger();

/**
 * Helper function to wrap fetch calls with automatic logging
 */
export async function fetchWithLogging(
  input: RequestInfo | URL,
  init?: RequestInit & { userId?: string; skipLogging?: boolean },
  component?: string
): Promise<Response> {
  if (init?.skipLogging) {
    return fetch(input, init);
  }

  const url = typeof input === "string" ? input : input.toString();
  const method = init?.method || "GET";
  const startTime = performance.now();
  const endpoint = url.replace(API_URL, "");

  try {
    clientLogger.logApiCall(endpoint, method, {
      url,
      headers: init?.headers,
      component,
    });

    const response = await fetch(input, init);
    const duration = performance.now() - startTime;

    clientLogger.logApiResponse(
      endpoint,
      method,
      response.status,
      duration,
      {
        url,
        component,
        contentType: response.headers.get("content-type"),
      },
      init?.userId
    );

    return response;
  } catch (error) {
    const duration = performance.now() - startTime;
    clientLogger.logError(
      "fetch_failed",
      error instanceof Error ? error.message : "Unknown fetch error",
      {
        url,
        method,
        duration,
        component,
      },
      error instanceof Error ? error.stack : undefined
    );
    throw error;
  }
}

export default clientLogger;
