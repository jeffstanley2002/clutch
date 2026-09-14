import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Clutch — Code review & interview practice",
  description:
    "Review your Python code, understand the findings, and practice explaining your decisions.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
