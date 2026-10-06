import type { Metadata } from "next";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import "./research-workspace.css";
import "./financial-labs.css";
import WalletSessionGuard from "./WalletSessionGuard";

export const metadata: Metadata = {
  title: "ORAKT · 观因",
  description: "Evidence-linked global event and market intelligence.",
  icons: { icon: "/brand/orakt-line.svg", shortcut: "/brand/orakt-line.svg", apple: "/brand/apple-touch-line.png" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}<WalletSessionGuard /></body></html>;
}
