import type { Metadata } from "next";
import type { ReactNode } from "react";

import { brand } from "@/lib/brand";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: brand.name, template: `%s · ${brand.shortName}` },
  description: brand.tagline,
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body style={{ ["--brand" as string]: brand.primaryColor }}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
