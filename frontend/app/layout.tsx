import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "JomKecek",
  description: "Kelantan dialect and knowledge chatbot"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ms">
      <body>{children}</body>
    </html>
  );
}
