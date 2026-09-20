import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent Coordination",
  description: "Research control room for multi-agent runs",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
