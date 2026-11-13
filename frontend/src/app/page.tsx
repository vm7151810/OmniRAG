/**
 * ===============================================================================
 * COMPONENT: page.tsx
 * PROJECT: OmniRAG Enterprise Agentic Support Chatbot
 * LAYER: Frontend Presentation Layer (Main Glassmorphism Home Page)
 * ===============================================================================
 * 
 * DESCRIPTION:
 *     Main landing page for the OmniRAG Enterprise Support Chatbot UI. 
 *     Manages initial health polling (`/health`) during Render container cold starts, 
 *     renders the left-hand information sidebar (project architecture, system date anchor 
 *     15 June 2026, example prompt buttons), and embeds the right-hand ChatContainer.
 * 
 * KEY RESPONSIBILITIES:
 *     1. Executing health check polling (`healthStatus`) every 2 seconds until backend responds.
 *     2. Displaying cold-start loading screen during backend startup delay.
 *     3. Rendering sidebar information, tool explanation cards, and example query buttons.
 *     4. Passing selected example queries to `ChatContainer` via `initialQuery` state prop.
 * ===============================================================================
 */

"use client";

import { useEffect, useState } from "react";
import { ChatContainer } from "@/components/chat/ChatContainer";
import { KnowledgeBaseModal } from "@/components/ui/KnowledgeBaseModal";
import { Loader2 } from "lucide-react";

export default function Home() {
  // State 1: Tracks backend health status ("polling" | "ready" | "error")
  const [healthStatus, setHealthStatus] = useState<"polling" | "ready" | "error">("polling");
  // State 2: Stores selected example prompt string to pre-fill and trigger in ChatContainer
  const [initialQuery, setInitialQuery] = useState<string>("");
  // State 3: Selected category filter for prompt suggestions
  const [selectedCategory, setSelectedCategory] = useState<"all" | "rag" | "sql" | "hybrid">("all");
  // State 4: Active mobile view segment ("chat" | "info") for screens below lg breakpoint
  const [mobileView, setMobileView] = useState<"chat" | "info">("chat");

  // Effect: Poll backend /health endpoint until 200 OK is received
  useEffect(() => {
    // Resolve backend API URL from environment variable or default to localhost:8000
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    let isPolling = true;
    let isRequestInFlight = false;

    // Asynchronous health check fetcher
    const checkHealth = async () => {
      // Prevent overlapping requests if the network is extremely slow
      if (isRequestInFlight) return;
      isRequestInFlight = true;
      
      try {
        // Cache-buster: Append timestamp to force the browser to bypass any connection-failure caches
        const res = await fetch(`${apiUrl}/health?t=${Date.now()}`, { 
            cache: 'no-store' 
        });

        // If backend responds with HTTP 200 OK, transition status to 'ready'
        if (res.ok) {
          setHealthStatus("ready");
          isPolling = false; // Stop further polling iterations
        }
      } catch {
        // Silently catch fetch errors while backend is spinning up
      } finally {
        isRequestInFlight = false; // Release the lock
      }
    };

    // Trigger immediate initial health check
    checkHealth();

    // Set recurring 2-second interval polling timer
    const interval = setInterval(() => {
      if (isPolling) checkHealth();
      else clearInterval(interval);
    }, 2000);

    // Clean up interval timer on component unmount
    return () => clearInterval(interval);
  }, []);

  // Conditional Rendering: Display cold-start loading screen while backend is spinning up
  if (healthStatus === "polling") {
    return (
      <main className="flex min-h-[100dvh] flex-col items-center justify-center p-4 bg-muted/30">
        <div className="flex flex-col items-center gap-6 max-w-md text-center">
          {/* Animated spinner icon */}
          <Loader2 className="h-12 w-12 animate-spin text-primary" />
          <div className="space-y-2">
            <h2 className="text-2xl font-bold tracking-tight">Waking up the AI engine...</h2>
            <p className="text-muted-foreground">
              Our backend is currently cold-starting on Render. This usually takes about 50 seconds. Hang tight!
            </p>
          </div>
        </div>
      </main>
    );
  }

  // Pre-defined sample queries organized by technical capability
  const categorizedPrompts = [
    {
      category: "rag" as const,
      badgeCode: "RAG",
      prompt: "What is the refund window and required conditions?",
      desc: "Retrieves 30-day window from returns_policy.pdf",
    },
    {
      category: "rag" as const,
      badgeCode: "RAG",
      prompt: "What is covered under the 12-month warranty vs excluded?",
      desc: "Searches warranty_policy.pdf for coverage exclusions",
    },
    {
      category: "rag" as const,
      badgeCode: "RAG",
      prompt: "How do I factory reset my Northwind Pulse headphones?",
      desc: "Pulls Bluetooth reset steps from product_faq.pdf",
    },
    {
      category: "sql" as const,
      badgeCode: "SQL",
      prompt: "How many orders are pending?",
      desc: "Executes SQL query over SQLite orders table",
    },
    {
      category: "sql" as const,
      badgeCode: "SQL",
      prompt: "Show the top 5 customers by total spending",
      desc: "Performs SQL aggregation with GROUP BY and SUM",
    },
    {
      category: "sql" as const,
      badgeCode: "SQL",
      prompt: "What is the total revenue from delivered orders?",
      desc: "Filters status='Delivered' and calculates revenue",
    },
    {
      category: "hybrid" as const,
      badgeCode: "HYBRID",
      prompt: "Did order ORD-1207 qualify for a return?",
      desc: "Chains SQL order lookup with PDF policy eligibility",
    },
    {
      category: "hybrid" as const,
      badgeCode: "HYBRID",
      prompt: "Check if order ORD-1140 can get a free warranty replacement",
      desc: "Evaluates purchase date against 12-month warranty window",
    },
    {
      category: "hybrid" as const,
      badgeCode: "HYBRID",
      prompt: "Did customer Marcus Vance receive a bulk discount on his orders?",
      desc: "Correlates order quantity with pricing discount policy",
    },
  ];

  const visiblePrompts = selectedCategory === "all" 
    ? categorizedPrompts 
    : categorizedPrompts.filter((p) => p.category === selectedCategory);

  return (
    <main className="h-[100dvh] min-h-[100dvh] max-h-[100dvh] bg-background text-foreground flex flex-col selection:bg-zinc-200 dark:selection:bg-zinc-800 overflow-hidden">
      <div className="w-full max-w-7xl mx-auto px-3 sm:px-6 lg:px-12 py-2.5 sm:py-6 lg:py-8 flex flex-col h-full max-h-[1100px]">
        
        {/* Top Minimal Editorial Meta Bar */}
        <header className="flex items-center justify-between pb-2.5 sm:pb-4 mb-2 sm:mb-6 border-b border-border/70 text-[11px] font-mono tracking-wider text-muted-foreground shrink-0">
          <div className="flex items-center gap-2 sm:gap-3">
            <span className="font-semibold text-foreground tracking-widest uppercase text-xs sm:text-sm">OmniRAG</span>
            <span className="text-border">/</span>
            <span className="hidden sm:inline">Enterprise Intelligence</span>
            <span className="sm:hidden text-[10px] text-muted-foreground/80">Support</span>
          </div>
          <div className="flex items-center gap-2 sm:gap-4 text-[10px] uppercase">
            <span className="hidden md:inline">Pinecone AWS</span>
            <span className="text-border hidden md:inline">·</span>
            <span>Anchor: <strong className="text-foreground">15 Jun 2026</strong></span>
          </div>
        </header>

        {/* Mobile Segmented View Switcher (< lg only) */}
        <div className="grid grid-cols-2 lg:hidden p-1 bg-muted/40 rounded border border-border/60 mb-2.5 shrink-0 text-xs font-mono">
          <button
            type="button"
            onClick={() => setMobileView("chat")}
            className={`py-2 rounded transition-all text-center font-medium ${
              mobileView === "chat" 
                ? "bg-foreground text-background shadow-xs" 
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Conversation
          </button>
          <button
            type="button"
            onClick={() => setMobileView("info")}
            className={`py-2 rounded transition-all text-center font-medium ${
              mobileView === "info" 
                ? "bg-foreground text-background shadow-xs" 
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Directory & Schema
          </button>
        </div>

        {/* Asymmetrical Main Layout: 4 Columns Left / 8 Columns Right */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-10 flex-1 min-h-0">
          
          {/* Left Column: Editorial Information & Prompt Index (Always visible on lg, toggled on mobile) */}
          <aside className={`lg:col-span-4 flex-col gap-4 sm:gap-6 h-full overflow-y-auto pr-1 pb-4 ${
            mobileView === "info" ? "flex" : "hidden lg:flex"
          }`}>
            
            {/* Editorial Title & Scope */}
            <div className="space-y-1.5 sm:space-y-2 shrink-0">
              <h1 className="text-xl sm:text-2xl lg:text-3xl font-semibold tracking-tight text-foreground leading-tight">
                Policy & Database Assistant
              </h1>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Autonomous agent routing natural language between unstructured PDF policies and structured SQLite order analytics.
              </p>
            </div>

            {/* Knowledge Base Trigger */}
            <div className="shrink-0">
              <KnowledgeBaseModal />
            </div>

            {/* System Architectural Index */}
            <div className="p-3.5 sm:p-4 rounded border border-border/70 bg-card/40 space-y-3 shrink-0">
              <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
                01 / System Capabilities
              </div>
              <div className="space-y-2.5 text-xs">
                <div className="flex items-start gap-2.5 pb-2.5 border-b border-border/40">
                  <span className="font-mono text-[10px] text-muted-foreground shrink-0 pt-0.5">RAG</span>
                  <div>
                    <span className="font-medium text-foreground">Vector Policy Retrieval</span>
                    <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">5 indexed PDF policy documents with exact parent citations.</p>
                  </div>
                </div>
                <div className="flex items-start gap-2.5 pb-2.5 border-b border-border/40">
                  <span className="font-mono text-[10px] text-muted-foreground shrink-0 pt-0.5">SQL</span>
                  <div>
                    <span className="font-medium text-foreground">Structured Analytics</span>
                    <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">Automated Text-to-SQL generation with dual read-only guards.</p>
                  </div>
                </div>
                <div className="flex items-start gap-2.5">
                  <span className="font-mono text-[10px] text-muted-foreground shrink-0 pt-0.5">ACT</span>
                  <div>
                    <span className="font-medium text-foreground">Cross-Modal Reasoning</span>
                    <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">Correlates order dates with policy eligibility rules.</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Prompt Directory Section */}
            <div className="space-y-3 flex-1 min-h-0 flex flex-col">
              <div className="flex items-center justify-between shrink-0">
                <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
                  02 / Prompt Index
                </span>

                {/* Minimalist Monospace Category Filters */}
                <div className="flex gap-1">
                  {(
                    [
                      { id: "all", label: "All" },
                      { id: "rag", label: "Policy" },
                      { id: "sql", label: "SQL" },
                      { id: "hybrid", label: "Hybrid" },
                    ] as const
                  ).map((cat) => (
                    <button
                      key={cat.id}
                      type="button"
                      onClick={() => setSelectedCategory(cat.id)}
                      className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded transition-colors ${
                        selectedCategory === cat.id
                          ? "bg-foreground text-background font-semibold"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {cat.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Minimalist Prompts List - Auto-switches to chat view on mobile selection */}
              <div className="flex flex-col gap-1.5 overflow-y-auto pr-0.5 flex-1 min-h-0">
                {visiblePrompts.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setInitialQuery(item.prompt);
                      setMobileView("chat"); // Auto-switch to chat view on mobile for seamless experience
                    }}
                    className="w-full text-left p-2.5 rounded border border-border/50 hover:border-border hover:bg-muted/40 transition-all group flex flex-col gap-1"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs font-medium text-foreground/90 group-hover:text-foreground leading-snug">
                        {item.prompt}
                      </span>
                      <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/70 shrink-0 border border-border/40 px-1 py-0.2 rounded">
                        {item.badgeCode}
                      </span>
                    </div>
                    <span className="text-[10px] text-muted-foreground leading-normal line-clamp-1">
                      {item.desc}
                    </span>
                  </button>
                ))}
              </div>
            </div>

          </aside>

          {/* Right Column: Expansive Chat Canvas (Always visible on lg, toggled on mobile) */}
          <section className={`lg:col-span-8 h-full flex-col min-h-0 ${
            mobileView === "chat" ? "flex" : "hidden lg:flex"
          }`}>
            <ChatContainer 
              initialQuery={initialQuery} 
              onClearInitialQuery={() => setInitialQuery("")} 
            />
          </section>

        </div>
      </div>
    </main>
  );
}
