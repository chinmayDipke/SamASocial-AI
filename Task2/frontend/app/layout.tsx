import type { Metadata } from "next";
import { DM_Mono, Fraunces, Public_Sans } from "next/font/google";

import "./globals.css";

/*
  Three faces, three jobs: a high-contrast serif for the plan's own structure, a
  document grotesque for anything you read, click or type, and a mono for
  anything a machine produced and you would check -- numbers, levels, hostnames.
*/

/*
  The plan's structure. No `weight` here on purpose: `axes` is only accepted for
  a variable font whose weight is left unset, so asking for ["500","600"] as
  well would fail the build. The variable face already carries 100-900, and the
  quirk axes (SOFT 0, WONK 0) are pinned in `.plan-title` so titles read
  engraved rather than playful.
*/
const fraunces = Fraunces({
  subsets: ["latin"],
  axes: ["SOFT", "WONK", "opsz"],
  variable: "--font-fraunces",
  display: "swap",
});

// Public Sans was drawn for public-sector documents. On a syllabus surface that
// provenance is the point -- sober, legible at 13px, and audibly not Inter.
const publicSans = Public_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-public-sans",
  display: "swap",
});

const dmMono = DM_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-dm-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Course Planner — plan a course by talking it through",
  description:
    "Answer four questions and an assistant drafts a full course: modules, lesson topics, public resources and end-of-module assessments. Every line is editable in place.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${fraunces.variable} ${publicSans.variable} ${dmMono.variable}`}
    >
      <body className="antialiased">{children}</body>
    </html>
  );
}
