import type { Metadata } from "next";
import Script from "next/script";
import TelegramInit from "./TelegramInit";
import "./globals.css";

export const metadata: Metadata = {
  title: "Каталог",
  description: "Каталог товаров",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body>
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="beforeInteractive"
        />
        <TelegramInit />
        {children}
      </body>
    </html>
  );
}
