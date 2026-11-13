"use client";

import React from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Calendar, ExternalLink, BookOpen } from "lucide-react";

export function KnowledgeBaseModal({ trigger }: { trigger?: React.ReactNode }) {
  const policies = [
    {
      name: "Returns & Refunds Policy",
      file: "returns_policy.pdf",
      summary: "30-day refund window from delivery, original packaging condition, restocking fees, and non-returnable items.",
    },
    {
      name: "12-Month Limited Warranty",
      file: "warranty_policy.pdf",
      summary: "Covers hardware defects and battery malfunctions. Excludes water damage, accidental drops, and third-party repairs. RMA workflow.",
    },
    {
      name: "Pricing & Discounts Policy",
      file: "pricing_discounts_policy.pdf",
      summary: "14-day price matching guarantee, 10% bulk discount on 5+ units, student and corporate partner discount programs.",
    },
    {
      name: "Product FAQ & Troubleshooting",
      file: "product_faq.pdf",
      summary: "Hardware specifications, battery life, firmware update instructions, and Bluetooth pairing reset steps for Pulse Headphones & Horizon Display.",
    },
    {
      name: "HR Leave & Time-Off Policy",
      file: "hr_leave_policy.pdf",
      summary: "15 days annual PTO accrual, sick leave medical note requirements, and parental leave eligibility guidelines.",
    },
  ];

  const sampleOrders = [
    { id: "ORD-1207", customer: "Marcus Vance", product: "Northwind Pulse", amount: "$149", status: "Delivered", date: "2026-05-18" },
    { id: "ORD-1045", customer: "Sneha Reddy", product: "Horizon Smart Display", amount: "$299", status: "Pending", date: "2026-06-02" },
    { id: "ORD-1140", customer: "Chloe Bennett", product: "Apex Mechanical Keyboard", amount: "$129", status: "Delivered", date: "2026-03-10" },
    { id: "ORD-1002", customer: "Alice Smith", product: "Ergo Pro Wireless Mouse", amount: "$79", status: "Cancelled", date: "2026-01-14" },
  ];

  return (
    <Sheet>
      <SheetTrigger
        render={
          (trigger as React.ReactElement) || (
            <Button variant="outline" className="w-full justify-between px-3.5 py-2 h-auto text-xs font-normal border-border/70 hover:bg-muted/40 transition-colors">
              <span className="flex items-center gap-2 text-foreground font-medium">
                <BookOpen className="h-3.5 w-3.5 text-muted-foreground" />
                <span>Knowledge Base & Schema</span>
              </span>
              <span className="font-mono text-[10px] uppercase text-muted-foreground">Archive ↗</span>
            </Button>
          )
        }
      />
      <SheetContent side="right" className="w-full sm:max-w-xl p-0 flex flex-col h-full max-h-screen min-h-0 bg-background border-l border-border/80 overflow-hidden">
        <SheetHeader className="p-4 sm:p-6 pb-3 sm:pb-4 border-b border-border/70 shrink-0">
          <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1">
            Documentation Archive
          </div>
          <SheetTitle className="text-base sm:text-lg font-semibold tracking-tight text-foreground">
            Knowledge Base & Database Explorer
          </SheetTitle>
          <SheetDescription className="text-xs text-muted-foreground">
            Complete index of source PDF policy documents and SQLite orders schema.
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6">
          <div className="space-y-5 sm:space-y-6 pb-6">
            
            {/* System Anchor Date Banner */}
            <div className="p-3 sm:p-3.5 rounded border border-border/70 bg-muted/30 text-xs space-y-1">
              <div className="flex items-center gap-2">
                <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="font-mono text-[10px] uppercase tracking-wider font-semibold text-foreground">
                  Reference Date Anchor: 15 June 2026
                </span>
              </div>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                All policy calculations (e.g. 30-day return eligibility and 12-month warranty windows) are evaluated relative to this fixed system timestamp.
              </p>
            </div>

            {/* Section 1: Policy Documents */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                  01 / Unstructured Policy Corpus (5 Documents)
                </h3>
              </div>
              <div className="space-y-2">
                {policies.map((p, idx) => (
                  <div key={idx} className="p-3 rounded border border-border/60 hover:border-border transition-colors text-xs space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-foreground">{p.name}</span>
                      <a
                        href={`/policies/${p.file}`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-foreground shrink-0 underline underline-offset-2"
                      >
                        <span>PDF</span>
                        <ExternalLink className="h-2.5 w-2.5" />
                      </a>
                    </div>
                    <p className="text-[11px] text-muted-foreground leading-relaxed">{p.summary}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Section 2: SQLite Orders Database */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                  02 / Structured Schema (SQLite orders Table)
                </h3>
              </div>
              
              <div className="p-3 sm:p-3.5 rounded border border-border/60 space-y-3 text-xs">
                <div className="flex justify-between items-center text-muted-foreground text-[11px]">
                  <span>Table: <strong className="text-foreground font-mono">orders</strong> (200 records)</span>
                  <div className="flex items-center gap-2">
                    <span className="sm:hidden font-mono text-[9px] uppercase text-muted-foreground/60">← swipe →</span>
                    <span className="font-mono text-[10px] uppercase text-muted-foreground border border-border/60 px-1.5 py-0.5 rounded">
                      Read-Only Guard
                    </span>
                  </div>
                </div>
                
                {/* Schema description */}
                <div className="p-2.5 bg-muted/40 rounded font-mono text-[11px] text-muted-foreground overflow-x-auto leading-relaxed border border-border/40 touch-pan-x">
                  order_id (TEXT), customer (TEXT), product (TEXT), amount (INT), status (TEXT), order_date (DATE)
                </div>

                {/* Sample Rows Table */}
                <div className="overflow-x-auto pt-1 touch-pan-x -mx-1 px-1">
                  <table className="w-full min-w-[480px] text-left border-collapse text-[11px]">
                    <thead>
                      <tr className="border-b border-border/60 text-muted-foreground font-mono text-[10px] uppercase">
                        <th className="pb-2 font-medium">Order ID</th>
                        <th className="pb-2 font-medium">Customer</th>
                        <th className="pb-2 font-medium">Product</th>
                        <th className="pb-2 font-medium">Amount</th>
                        <th className="pb-2 font-medium">Status</th>
                        <th className="pb-2 font-medium">Date</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/40 text-foreground">
                      {sampleOrders.map((order, i) => (
                        <tr key={i} className="hover:bg-muted/20 transition-colors">
                          <td className="py-2 font-mono text-foreground font-medium">{order.id}</td>
                          <td className="py-2">{order.customer}</td>
                          <td className="py-2 text-muted-foreground">{order.product}</td>
                          <td className="py-2 font-mono tabular-nums">{order.amount}</td>
                          <td className="py-2">
                            <span className="font-mono text-[10px] uppercase text-muted-foreground">
                              {order.status}
                            </span>
                          </td>
                          <td className="py-2 text-muted-foreground font-mono">{order.date}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Prompt Ideas Tip Box */}
            <div className="p-3 rounded border border-border/40 text-[11px] text-muted-foreground leading-relaxed">
              <strong className="text-foreground font-medium">Cross-Modal Verification:</strong> Test asking about customer order history (e.g. <em>&quot;Did order ORD-1207 qualify for a return?&quot;</em>) to observe the agent retrieve the SQL delivery date and compare against the 30-day PDF policy.
            </div>

          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
