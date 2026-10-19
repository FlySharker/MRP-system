import type { Metadata } from "next";
import "katex/dist/katex.min.css";
import "./globals.css";
import { I18nProvider } from "@/components/i18n-provider";
import { PageCloseHandler } from "@/components/page-close-handler";

export const metadata: Metadata = {
  title: "MRP Insight Console",
  description: "MRP anomaly detection and diagnostic analysis dashboard.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" data-scroll-behavior="smooth">
      <body>
        <I18nProvider>{children}</I18nProvider>
        <PageCloseHandler />
      </body>
    </html>
  );
}
