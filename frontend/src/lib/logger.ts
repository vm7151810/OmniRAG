/**
 * ===============================================================================
 * MODULE: logger.ts
 * PROJECT: OmniRAG Enterprise Agentic Support Chatbot
 * LAYER: Frontend Utility Layer (Client & Server Logging Standard)
 * ===============================================================================
 * 
 * DESCRIPTION:
 *     Client and server side logging utility for Next.js 15. Emits structured 
 *     JSON log telemetry matching backend schema. Client-side logs are dispatched to 
 *     the `/api/log` proxy endpoint.
 * 
 * KEY RESPONSIBILITIES:
 *     1. Validating environment context (`window !== undefined` for browser vs server).
 *     2. Formatting structured JSON payloads containing module, action, trace_id, and data.
 *     3. Dispatching POST requests to `/api/log` when executing in browser runtime.
 * ===============================================================================
 */

// Interface defining the standardized structured log payload schema
interface LogPayload {
  module: string;                  // Source filename string (e.g. 'ChatContainer.tsx')
  action: string;                  // Log action event title (e.g. 'chat_submitted')
  trace_id: string;                // Request trace ID string
  data: Record<string, unknown>;   // Telemetry data object dictionary
}

export const logger = {
  /**
   * Logs an informational telemetry event.
   * 
   * @param payload LogPayload object containing module, action, trace_id, and data.
   */
  info: (payload: LogPayload) => {
    // Generate ISO-8601 timestamp string
    const timestamp = new Date().toISOString();
    
    // Step 1: Check if running in browser window environment
    if (typeof window !== "undefined") {
      // Dispatch log payload via HTTP POST to /api/log proxy endpoint
      fetch("/api/log", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ...payload, timestamp }),
      }).catch(() => {
        // Silently fail if logging endpoint is temporarily unreachable
      });
    } else {
      // Step 2: Running in Server runtime
      if (process.env.DEBUG === "true") {
        // Print serialized JSON log string to server stdout
        console.log(JSON.stringify({ ...payload, timestamp }));
      }
    }
  },
  
  /**
   * Logs an error telemetry event using standard payload schema.
   * 
   * @param payload LogPayload object containing module, action, trace_id, and data.
   */
  error: (payload: LogPayload) => {
    // Both info and error use the same structured JSON schema
    logger.info(payload);
  }
};
