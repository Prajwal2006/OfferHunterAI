/**
 * React hook for tracking button clicks and component interactions.
 * Automatically logs all tracked actions with context.
 */

import { useCallback, useRef, useEffect } from "react";
import clientLogger from "./client-logger";

export interface UseTrackingOptions {
  component: string;
  userId?: string;
  logToConsole?: boolean;
}

export interface TrackingCallbacks {
  trackClick: (action: string, details?: Record<string, unknown>) => void;
  trackEvent: (eventType: string, action: string, details?: Record<string, unknown>) => void;
  trackError: (error: Error | string, context?: Record<string, unknown>) => void;
  trackPerformance: (operation: string, durationMs: number, threshold?: number) => void;
}

/**
 * Hook for tracking user interactions in a component
 */
export function useTracking(options: UseTrackingOptions): TrackingCallbacks {
  const { component, userId, logToConsole = true } = options;
  const isInitializedRef = useRef(false);

  useEffect(() => {
    if (!isInitializedRef.current && userId) {
      clientLogger.setUserId(userId);
      isInitializedRef.current = true;
    }
  }, [userId]);

  const trackClick = useCallback(
    (action: string, details?: Record<string, unknown>) => {
      clientLogger.logButtonClick(component, action, details, userId);
      if (logToConsole) {
        console.log(`[${component}] Clicked: ${action}`, details);
      }
    },
    [component, userId, logToConsole]
  );

  const trackEvent = useCallback(
    (eventType: string, action: string, details?: Record<string, unknown>) => {
      clientLogger.logUserAction(action, component, { ...details, event_type: eventType }, userId);
      if (logToConsole) {
        console.log(`[${component}] ${eventType}: ${action}`, details);
      }
    },
    [component, userId, logToConsole]
  );

  const trackError = useCallback(
    (error: Error | string, context?: Record<string, unknown>) => {
      const errorMessage = typeof error === "string" ? error : error.message;
      const errorStack = error instanceof Error ? error.stack : undefined;
      clientLogger.logError(
        "component_error",
        errorMessage,
        { ...context, component },
        errorStack,
        userId
      );
    },
    [component, userId]
  );

  const trackPerformance = useCallback(
    (operation: string, durationMs: number, threshold?: number) => {
      clientLogger.logPerformance(`${component}:${operation}`, durationMs, threshold, {
        component,
      });
    },
    [component]
  );

  return {
    trackClick,
    trackEvent,
    trackError,
    trackPerformance,
  };
}

/**
 * Higher-order component to automatically track click events on elements
 */
export function withClickTracking<P extends { [key: string]: unknown }>(
  WrappedComponent: React.ComponentType<P>,
  component: string
): React.FC<P> {
  return (props: P) => {
    const tracking = useTracking({ component });

    // Create a modified version of props that intercepts onClick handlers
    const modifiedProps = { ...props };

    // Look for onClick handlers in the props
    if (typeof props === "object" && props !== null) {
      for (const key in props) {
        if (key.startsWith("on") && typeof props[key] === "function") {
          // Wrap event handlers to track clicks
          const originalHandler = props[key] as Function;
          (modifiedProps as any)[key] = function (event: any) {
            const actionName = key.replace(/^on/, "").toLowerCase();
            tracking.trackClick(actionName, {
              element: event.target?.className,
              text: event.target?.textContent?.substring(0, 100),
            });
            return originalHandler(event);
          };
        }
      }
    }

    return <WrappedComponent {...(modifiedProps as P)} />;
  };
}

export default useTracking;
