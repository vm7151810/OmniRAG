/**
 * ===============================================================================
 * COMPONENT: ChatContainer.tsx
 * PROJECT: OmniRAG Enterprise Agentic Support Chatbot
 * LAYER: Frontend Interactive Layer (Streaming SSE Consumer & UI Renderer)
 * ===============================================================================
 * 
 * DESCRIPTION:
 *     The primary chat component for the OmniRAG interface. It reads incoming SSE 
 *     streams from the backend `POST /chat` endpoint, dynamically renders streaming 
 *     tokens, updates active reasoning indicators, formats markdown content, 
 *     displays generated SQL queries, and renders document citations.
 * 
 * KEY RESPONSIBILITIES:
 *     1. Consuming `text/event-stream` chunks via `ReadableStreamDefaultReader` and `TextDecoder`.
 *     2. Parsing 6 discrete event types: `intent`, `token`, `tool_call`, `tool_result`, `done`, `error`.
 *     3. Updating message state dynamically with non-mutative state copies.
 *     4. Auto-scrolling to the latest message using `scrollIntoView`.
 *     5. Rendering markdown responses via `ReactMarkdown` and custom CSS blocks.
 * ===============================================================================
 */

"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { toast } from "sonner";
import { logger } from "@/lib/logger";
import ReactMarkdown from "react-markdown";

// Interface representing structured citation metadata from RAG
export interface CitationDetail {
  id: number;
  source: string;
  title: string;
  page?: number;
  excerpt?: string;
  url?: string;
}

// Interface representing a single chat message object in the UI
export interface Message {
  id: string;              // Unique message identifier string (timestamp based)
  role: "user" | "assistant"; // Message sender role
  content: string;         // Accumulated text message content
  isGenerating?: boolean;  // Boolean flag indicating active SSE stream generation
  activeTool?: string;     // Active tool progress message string (e.g. 'Querying order database...')
  citations?: string[];    // Array of citation strings returned by rag_search tool
  citationDetails?: CitationDetail[]; // Rich structured citation objects
  sql?: string;            // Generated raw SQL string returned by sql_query tool
  modelUsed?: string;      // The actual LLM model name that generated the response
  isError?: boolean;       // Flag indicating error status
}

export function ChatContainer({
  initialQuery = "",
  onClearInitialQuery,
}: {
  initialQuery?: string;
  onClearInitialQuery?: () => void;
}) {
  // State 1: Master array of conversation messages
  const [messages, setMessages] = useState<Message[]>([]);
  // State 2: Current text input value in input form
  const [input, setInput] = useState("");
  // State 3: Global loading boolean indicating active HTTP request / streaming
  const [isLoading, setIsLoading] = useState(false);
  // Ref: Reference element attached to bottom anchor for smooth auto-scrolling
  const scrollRef = useRef<HTMLDivElement>(null);

  // Rotating suggestions for chat input placeholder
  const promptPlaceholders = [
    "Ask a policy question: 'What is the refund window?'",
    "Ask database analytics: 'How many orders are pending?'",
    "Ask hybrid agent: 'Did order ORD-1207 qualify for a return?'",
    "Ask warranty specs: 'What is covered under the 12-month warranty?'",
    "Ask revenue totals: 'Show top 5 customers by total spending'",
    "Ask product FAQ: 'How do I factory reset Pulse headphones?'",
  ];
  const [placeholderIndex, setPlaceholderIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setPlaceholderIndex((prev) => (prev + 1) % promptPlaceholders.length);
    }, 4000);
    return () => clearInterval(interval);
  }, [promptPlaceholders.length]);

  // Effect 1: Trigger auto-send if an example query prop is passed from sidebar
  useEffect(() => {
    if (initialQuery) {
      handleSend(initialQuery);
      if (onClearInitialQuery) onClearInitialQuery();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery]);

  // Effect 2: Automatically scroll chat area to bottom whenever messages array updates
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Core handler function for submitting user messages and consuming SSE streams
  const handleSend = async (text: string) => {
    // Prevent empty queries or duplicate submissions while loading
    if (!text.trim() || isLoading) return;

    // Step 1: Create User Message Object
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: text.trim(),
    };

    // Step 2: Create Placeholder Assistant Message Object
    const aiMessageId = (Date.now() + 1).toString();
    const aiMessage: Message = {
      id: aiMessageId,
      role: "assistant",
      content: "",
      isGenerating: true,
    };

    // Append user message and placeholder assistant message to state
    setMessages((prev) => [...prev, userMessage, aiMessage]);
    setInput("");
    setIsLoading(true);

    // Emit structured logging event for query submission
    logger.info({
      module: "ChatContainer.tsx",
      action: "chat_submitted",
      trace_id: `req-${userMessage.id}`,
      data: { query: text },
    });

    try {
      // Step 3: Dispatch POST request to backend /chat endpoint
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: text,
          session_id: "default",
        }),
      });

      // Verify HTTP response status
      if (!response.ok) {
        let errorMsg = `HTTP Error ${response.status}`;
        try {
          const errorData = await response.json();
          if (errorData.detail) {
            errorMsg = typeof errorData.detail === "string" ? errorData.detail : JSON.stringify(errorData.detail);
          } else if (errorData.message) {
            errorMsg = errorData.message;
          }
        } catch {
          errorMsg = response.statusText || errorMsg;
        }
        throw new Error(errorMsg);
      }

      // Ensure response body reader is available
      if (!response.body) {
        throw new Error("No response body");
      }

      // Step 4: Initialize SSE stream reader and UTF-8 decoder
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      // Stream reading loop
      while (true) {
        const { done, value } = await reader.read();
        // Exit loop when stream is fully consumed
        if (done) break;

        // Decode binary chunk to text and append to buffer
        buffer += decoder.decode(value, { stream: true });
        
        // Split buffer by newline characters into complete lines
        const lines = buffer.split("\n");
        // Retain remaining incomplete partial line in buffer
        buffer = lines.pop() || "";

        // Process each line in chunk
        for (const line of lines) {
          // Verify line starts with standard SSE 'data: ' prefix
          if (line.startsWith("data: ")) {
            const dataStr = line.substring(6).trim();
            if (!dataStr) continue;

            try {
              // Parse JSON event payload
              const event = JSON.parse(dataStr);
              
              // Update state matching placeholder assistant message ID
              setMessages((prev) =>
                prev.map((msg) => {
                  if (msg.id === aiMessageId) {
                    const newMsg = { ...msg };
                    
                    // Event Case 1: Incremental LLM Token Stream
                    if (event.type === "token") {
                      newMsg.content += event.content;
                    } 
                    // Event Case 2: Tool Execution Started
                    else if (event.type === "tool_call") {
                      let toolText = "Working...";
                      if (event.tool === "rag_search") toolText = "🔍 Searching policy documents...";
                      if (event.tool === "sql_query") toolText = "🗃️ Querying order database...";
                      newMsg.activeTool = toolText;
                    } 
                    // Event Case 3: Tool Execution Result
                    else if (event.type === "tool_result") {
                      if (event.tool === "sql_query" && event.sql) {
                        newMsg.sql = event.sql; // Store raw SQL string for viewer block
                      }
                      newMsg.activeTool = undefined; // Clear active tool indicator
                    } 
                    // Event Case 4: Stream Execution Complete
                    else if (event.type === "done") {
                      newMsg.isGenerating = false;
                      newMsg.activeTool = undefined;
                      if (event.citations) {
                        newMsg.citations = event.citations; // Store citations array
                      }
                      if (event.citation_details) {
                        newMsg.citationDetails = event.citation_details; // Store rich citation details
                      }
                      if (event.model_used) {
                        newMsg.modelUsed = event.model_used; // Store active LLM model name
                      }
                      
                      // Log successful completion
                      logger.info({
                        module: "ChatContainer.tsx",
                        action: "stream_completed",
                        trace_id: `req-${userMessage.id}`,
                        data: { tool_used: event.tool_used, model_used: event.model_used },
                      });
                    } 
                    // Event Case 5: Stream Execution Error
                    else if (event.type === "error") {
                      newMsg.isGenerating = false;
                      newMsg.activeTool = undefined;
                      newMsg.isError = true;
                      
                      const rawError = event.message || "An unexpected error occurred";
                      const isRateLimit = rawError.includes("429") || rawError.includes("RESOURCE_EXHAUSTED");
                      
                      // Construct informative in-chat error message
                      if (isRateLimit) {
                        newMsg.content = "⚠️ **Google Gemini Free Tier Quota Notice**:\n\nThe current model has reached its Google AI Studio free tier quota. OmniRAG's automatic fallback chain attempted secondary models. Please wait a moment for the quota window to reset, or try another question.";
                      } else {
                        newMsg.content = `⚠️ **Assistant Error**:\n\n${rawError}\n\n*Please verify your input or retry in a moment.*`;
                      }

                      toast.error(isRateLimit ? "API Rate Limit: Quota reached" : `Error: ${rawError.slice(0, 80)}...`);
                      
                      logger.error({
                        module: "ChatContainer.tsx",
                        action: "stream_error",
                        trace_id: `req-${userMessage.id}`,
                        data: { code: event.code, message: event.message },
                      });
                    }
                    
                    return newMsg;
                  }
                  return msg;
                })
              );
            } catch (e) {
              console.error("Failed to parse SSE line", line, e);
            }
          }
        }
      }
    } catch (error: unknown) {
      // Handle network connection or stream parse errors
      const errMessage = error instanceof Error ? error.message : "Failed to reach backend";
      toast.error(`Connection Error: ${errMessage}`);
      
      // Update placeholder assistant message in-chat with clear error guidance
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMessageId
            ? {
                ...m,
                isGenerating: false,
                activeTool: undefined,
                isError: true,
                content: `⚠️ **Connection Error**: ${errMessage}.\n\nPlease ensure the backend server is running on port 8000 (\`uvicorn app.main:app\`) and retry.`,
              }
            : m
        )
      );
      
      logger.error({
        module: "ChatContainer.tsx",
        action: "connection_error",
        trace_id: `req-${userMessage.id}`,
        data: { message: error instanceof Error ? error.message : "Unknown error" },
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full border border-border/80 rounded-md bg-card/20 overflow-hidden w-full mx-auto">
      {/* Scrollable Chat Area */}
      <ScrollArea className="flex-1 p-3 sm:p-6">
        <div className="flex flex-col gap-4 sm:gap-5 pb-3 sm:pb-4">
          {/* Empty State Banner */}
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center min-h-[260px] sm:min-h-[400px] px-2 sm:px-4 py-4 sm:py-8 text-center max-w-xl mx-auto space-y-5 sm:space-y-8">
              <div className="space-y-1.5 sm:space-y-2">
                <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/80">
                  OmniRAG Canvas · Enterprise Intelligence
                </div>
                <h2 className="text-lg sm:text-2xl font-semibold tracking-tight text-foreground leading-snug">
                  Query policies, orders, or ask cross-modal questions.
                </h2>
                <p className="text-xs text-muted-foreground leading-relaxed max-w-md mx-auto">
                  Integrated reasoning over 5 unstructured PDF policy documents and 200 SQLite customer order records.
                </p>
              </div>

              {/* Monochromatic Quick-Start Rows */}
              <div className="w-full flex flex-col gap-2 text-left">
                <button
                  type="button"
                  onClick={() => handleSend("What is the refund window and required conditions?")}
                  className="w-full p-2.5 sm:p-3 rounded border border-border/60 hover:border-border hover:bg-muted/40 transition-colors flex items-center justify-between gap-2 sm:gap-3 group"
                >
                  <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
                    <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground border border-border/60 px-1.5 py-0.5 rounded shrink-0">
                      Policy
                    </span>
                    <span className="text-xs font-medium text-foreground/90 group-hover:text-foreground truncate">
                      What is the refund window and required conditions?
                    </span>
                  </div>
                  <span className="font-mono text-[10px] text-muted-foreground shrink-0 hidden sm:inline">
                    returns_policy.pdf ↗
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => handleSend("Show the top 5 customers by total spending")}
                  className="w-full p-2.5 sm:p-3 rounded border border-border/60 hover:border-border hover:bg-muted/40 transition-colors flex items-center justify-between gap-2 sm:gap-3 group"
                >
                  <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
                    <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground border border-border/60 px-1.5 py-0.5 rounded shrink-0">
                      SQL
                    </span>
                    <span className="text-xs font-medium text-foreground/90 group-hover:text-foreground truncate">
                      Show the top 5 customers by total spending
                    </span>
                  </div>
                  <span className="font-mono text-[10px] text-muted-foreground shrink-0 hidden sm:inline">
                    orders table ↗
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => handleSend("Did order ORD-1207 qualify for a return?")}
                  className="w-full p-2.5 sm:p-3 rounded border border-border/60 hover:border-border hover:bg-muted/40 transition-colors flex items-center justify-between gap-2 sm:gap-3 group"
                >
                  <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
                    <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground border border-border/60 px-1.5 py-0.5 rounded shrink-0">
                      Hybrid
                    </span>
                    <span className="text-xs font-medium text-foreground/90 group-hover:text-foreground truncate">
                      Did order ORD-1207 qualify for a return?
                    </span>
                  </div>
                  <span className="font-mono text-[10px] text-muted-foreground shrink-0 hidden sm:inline">
                    cross-reference ↗
                  </span>
                </button>
              </div>
            </div>
          ) : (
            // Render list of messages
            messages.map((msg) => {
              let cleanContent = msg.content;
              if (msg.sql && cleanContent.startsWith(msg.sql)) {
                cleanContent = cleanContent.substring(msg.sql.length).trim();
              }
              return (
              <div
                key={msg.id}
                className={`flex gap-2 sm:gap-3 ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                {/* Assistant Monogram Avatar */}
                {msg.role === "assistant" && (
                  <div className="h-6 w-6 rounded bg-foreground text-background font-mono text-[9px] font-semibold flex items-center justify-center shrink-0 mt-0.5 select-none">
                    AI
                  </div>
                )}
                
                {/* Message Bubble Container */}
                <div
                  className={`rounded px-3.5 sm:px-5 py-2.5 sm:py-3 text-xs sm:text-sm ${
                    msg.role === "user"
                      ? "bg-foreground text-background font-normal rounded-tr-none max-w-[88%] sm:max-w-[75%]"
                      : msg.isError
                      ? "bg-destructive/10 border border-destructive/30 text-foreground rounded-tl-none max-w-[96%] sm:max-w-[85%]"
                      : "bg-card border border-border/70 rounded-tl-none max-w-[96%] sm:max-w-[85%]"
                  }`}
                >
                  {/* Model Name Stamp on Assistant Messages */}
                  {msg.role === "assistant" && (
                    <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-widest text-muted-foreground/80 pb-1.5 sm:pb-2 mb-2 border-b border-border/40">
                      <span>Agent / {msg.modelUsed || "gemini-2.5-flash"}</span>
                      <span className="text-[9px] text-muted-foreground/50 tracking-normal font-sans hidden xs:inline">Live Verified</span>
                    </div>
                  )}

                  {/* Active Tool Reasoning Badge Indicator */}
                  {msg.activeTool && (
                    <div className="flex items-center gap-2 text-[11px] font-mono text-muted-foreground bg-muted/40 px-2 py-1 rounded mb-2 border border-border/40">
                      <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                      <span>{msg.activeTool}</span>
                    </div>
                  )}
                  
                  {/* Markdown Assistant Content Renderer */}
                  <div className="mt-1 markdown text-xs sm:text-sm leading-relaxed text-foreground/90 [&>p]:mb-2.5 last:[&>p]:mb-0 [&>ul]:list-disc [&>ul]:ml-4 [&>ul]:mb-2.5 [&>ol]:list-decimal [&>ol]:ml-4 [&>ol]:mb-2.5 [&>pre]:bg-zinc-950 [&>pre]:text-zinc-100 [&>pre]:p-3 [&>pre]:rounded [&>pre]:overflow-x-auto [&>code]:bg-muted [&>code]:px-1 [&>code]:rounded break-words">
                    <ReactMarkdown
                      components={{
                        // eslint-disable-next-line @typescript-eslint/no-unused-vars
                        a: ({ node: _node, href, children, ...props }) => {
                          if (href?.startsWith("#cite-")) {
                            return (
                              <a
                                href={href}
                                className="inline-flex items-center justify-center rounded font-mono text-[9px] font-bold text-muted-foreground hover:text-foreground bg-muted/60 hover:bg-muted border border-border/60 px-1 py-0.2 mx-0.5 align-super no-underline transition-colors"
                                title="Go to citation"
                                {...props}
                              >
                                {children}
                              </a>
                            );
                          }
                          return (
                            <a href={href} className="underline underline-offset-2 hover:text-foreground transition-colors" {...props}>
                              {children}
                            </a>
                          );
                        }
                      }}
                    >
                      {cleanContent.replace(/\[(\d+)\]/g, '[$1](#cite-$1)')}
                    </ReactMarkdown>
                  </div>
                  
                  {/* Animated Bouncing Loading Dots before first token arrives */}
                  {msg.isGenerating && !msg.activeTool && msg.content === "" && (
                    <div className="flex space-x-1.5 py-1">
                      <div className="w-1.5 h-1.5 bg-foreground/60 rounded-full animate-bounce" />
                      <div className="w-1.5 h-1.5 bg-foreground/60 rounded-full animate-bounce [animation-delay:0.2s]" />
                      <div className="w-1.5 h-1.5 bg-foreground/60 rounded-full animate-bounce [animation-delay:0.4s]" />
                    </div>
                  )}

                  {/* SQL Query Viewer Component Block */}
                  {msg.sql && (
                    <div className="mt-3 pt-2 text-xs space-y-1">
                      <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
                        SQL Executed (Read-Only)
                      </div>
                      <pre className="bg-zinc-950 text-zinc-100 p-2.5 rounded font-mono text-xs overflow-x-auto border border-zinc-800 leading-relaxed touch-pan-x">
                        {msg.sql}
                      </pre>
                    </div>
                  )}

                  {/* Document Citation Drawer Component Block */}
                  {((msg.citationDetails && msg.citationDetails.length > 0) || (msg.citations && msg.citations.length > 0)) && (
                    <div className="mt-4 pt-3 border-t border-border/50 text-xs space-y-2">
                      <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                        Document Citations
                      </div>

                      {msg.citationDetails && msg.citationDetails.length > 0 ? (
                        <div className="space-y-1.5">
                          {msg.citationDetails.map((cite, idx) => (
                            <div
                              key={idx}
                              id={`cite-${cite.id || idx + 1}`}
                              className="p-2 sm:p-2.5 rounded border border-border/50 text-xs space-y-1.5 transition-colors hover:border-border scroll-mt-4 bg-muted/20"
                            >
                              <div className="flex items-center justify-between gap-1.5">
                                <div className="flex items-center gap-1.5 min-w-0">
                                  <span className="font-mono text-[10px] text-muted-foreground font-semibold shrink-0">
                                    [{cite.id || idx + 1}]
                                  </span>
                                  <span className="font-medium text-foreground truncate">{cite.title}</span>
                                </div>
                                <a
                                  href={cite.url || `/policies/${cite.source}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-foreground shrink-0 underline underline-offset-2 max-w-[120px] sm:max-w-none truncate"
                                >
                                  <span className="truncate">{cite.source}</span>
                                  <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                                </a>
                              </div>
                              {cite.excerpt && (
                                <details className="mt-1 text-[11px] text-muted-foreground rounded bg-muted/30 p-2 border border-border/30">
                                  <summary className="cursor-pointer hover:text-foreground font-medium select-none text-[10px] font-mono uppercase tracking-wider">
                                    View Policy Excerpt
                                  </summary>
                                  <p className="mt-1 italic leading-relaxed text-foreground/80 font-sans">
                                    &ldquo;{cite.excerpt}&rdquo;
                                  </p>
                                </details>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <ol className="list-decimal list-inside space-y-1 text-muted-foreground font-mono text-[11px]">
                          {msg.citations?.map((cite, idx) => {
                            const [source] = cite.split(" - ");
                            const hasPdf = source && source.endsWith(".pdf");
                            return (
                              <li key={idx} id={`cite-${idx + 1}`} className="scroll-mt-3">
                                <span>{cite}</span>
                                {hasPdf && (
                                  <a
                                    href={`/policies/${source}`}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="ml-2 text-foreground underline underline-offset-2 inline-flex items-center gap-0.5 text-[10px]"
                                  >
                                    <span>[View PDF]</span>
                                    <ExternalLink className="h-2.5 w-2.5" />
                                  </a>
                                )}
                              </li>
                            );
                          })}
                        </ol>
                      )}
                    </div>
                  )}
                </div>

                {/* User Monogram Avatar */}
                {msg.role === "user" && (
                  <div className="h-6 w-6 rounded bg-muted border border-border/70 text-muted-foreground font-mono text-[9px] font-semibold flex items-center justify-center shrink-0 mt-0.5 select-none">
                    YOU
                  </div>
                )}
              </div>
            );
          })
          )}
          {/* Scroll Anchor Target Ref */}
          <div ref={scrollRef} />
        </div>
      </ScrollArea>

      {/* Input Form Footer Bar */}
      <div className="p-2.5 sm:p-4 bg-background border-t border-border/70">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend(input);
          }}
          className="flex gap-2 relative"
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={promptPlaceholders[placeholderIndex]}
            disabled={isLoading}
            className="flex-1 pr-12 text-base sm:text-sm h-10 border-border/80 focus-visible:ring-1 focus-visible:ring-foreground/30 bg-muted/20 placeholder:truncate"
          />
          <Button
            type="submit"
            disabled={isLoading || !input.trim()}
            size="icon"
            className="absolute right-1 top-1 h-8 w-8 bg-foreground text-background hover:bg-foreground/90 transition-colors"
          >
            {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
          </Button>
        </form>
      </div>
    </div>
  );
}
