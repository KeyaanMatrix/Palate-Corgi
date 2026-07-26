import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Palate — your taste, remembered",
  description:
    "Palate turns the reservations and cancellations already in your inbox into a taste graph and a trip that feels like yours.",
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
