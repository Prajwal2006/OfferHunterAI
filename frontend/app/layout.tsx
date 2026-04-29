import type { Metadata } from "next";
import "./globals.css";
import Navigation from "@/components/Navigation";

export const metadata: Metadata = {
  title: "OfferHunter AI — Multi-Agent Job Outreach System",
  description:
    "AI-powered multi-agent system for job discovery, personalized outreach, and pipeline tracking.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col gradient-bg grid-pattern">
        <Navigation />
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
