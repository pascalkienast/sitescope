import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SiteScope — Red Flag Report Generator",
  description:
    "Agentic AI-powered site due diligence using distributed geodata",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        {/* MapLibre GL CSS */}
        <link
          rel="stylesheet"
          href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css"
        />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
