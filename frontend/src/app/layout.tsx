/**
 * ===============================================================================
 * COMPONENT: layout.tsx
 * PROJECT: OmniRAG Enterprise Agentic Support Chatbot
 * LAYER: Frontend Presentation Layer (Root Layout Component)
 * ===============================================================================
 * 
 * DESCRIPTION:
 *     Root layout component for Next.js 15 App Router. Configures Google Inter font 
 *     variable (`--font-sans`), Geist local fonts, global metadata titles, and the Sonner 
 *     toaster notification system.
 * 
 * KEY RESPONSIBILITIES:
 *     1. Defining global page HTML metadata (title, description).
 *     2. Loading Inter font variable `--font-sans` and applying `font-sans` utility class.
 *     3. Rendering `Toaster` component for toast notification popups across the app.
 * ===============================================================================
 */

import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { Inter } from "next/font/google";
import { cn } from "@/lib/utils";
import { Toaster } from "@/components/ui/sonner";

// Load Google Inter font with latin subset and custom CSS variable --font-sans
const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });

// Load Geist Sans variable font
const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});

// Load Geist Mono variable font
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

// Define root metadata object for browser title bar and SEO
export const metadata: Metadata = {
  title: "OmniRAG Enterprise ChatBot",
  description: "Hybrid Text and SQL Enterprise Agentic Support Chatbot",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={cn("font-sans", inter.variable)}>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {/* Render child pages */}
        {children}
        {/* Global toast notification system */}
        <Toaster />
      </body>
    </html>
  );
}
