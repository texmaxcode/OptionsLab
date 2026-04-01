"use client";

import { useState, useEffect, useRef, type ReactNode } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { isAuthenticated, removeToken } from "@/lib/auth";

const NAV_LINKS: { href: string; label: string }[] = [
  { href: "/dashboard", label: "Overview" },
  { href: "/dashboard/data", label: "Data & Symbols" },
  { href: "/dashboard/volatility", label: "Volatility" },
  { href: "/dashboard/economic", label: "Macro & Economics" },
  { href: "/dashboard/research", label: "Research & AI" },
  { href: "/dashboard/backtests", label: "Backtests" },
  { href: "/dashboard/trade", label: "Trade" },
  { href: "/dashboard/settings", label: "Settings" },
];

export default function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const headerRef = useRef<HTMLElement>(null);
  const [mobileHeaderHeight, setMobileHeaderHeight] = useState(0);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
    }
  }, [router]);

  // Track the actual header height so the mobile menu positions correctly.
  useEffect(() => {
    const header = headerRef.current;
    if (!header) return;
    const observer = new ResizeObserver(() => {
      setMobileHeaderHeight(header.offsetHeight);
    });
    observer.observe(header);
    setMobileHeaderHeight(header.offsetHeight);
    return () => observer.disconnect();
  }, []);

  // Close menu on route change.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMobileMenuOpen(false);
  }, [pathname]);

  const handleLogout = () => {
    removeToken();
    router.replace("/login");
  };

  const navLinkClass = (href: string) => {
    const isActive = pathname === href;
    return isActive
      ? "border-l-2 border-emerald-500 bg-emerald-600/10 text-emerald-300 font-semibold pl-[calc(0.625rem-2px)]"
      : "border-l-2 border-transparent text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 pl-[calc(0.625rem-2px)]";
  };

  return (
    <div className="dark min-h-screen bg-zinc-950 flex min-w-0">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-52 lg:w-56 flex-col gap-0 border-r border-zinc-800 bg-zinc-950 p-3 flex-shrink-0">
        <Link
          href="/"
          className="flex flex-shrink-0 m-0 p-0 mb-3 justify-center items-center focus:outline-none focus:ring-2 focus:ring-emerald-500 rounded"
        >
          <Image
            src="/ol_logo.png"
            alt="OptionsLab Backtesting Platform"
            width={200}
            height={160}
            className="block h-28 lg:h-32 w-auto max-w-full object-contain m-0 p-0"
            priority
          />
        </Link>
        <nav className="flex-1 space-y-0.5 min-h-0">
          {NAV_LINKS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`block rounded-r-md pr-2.5 py-1.5 text-sm transition-colors ${navLinkClass(href)}`}
            >
              {label}
            </Link>
          ))}
          <a
            href="/user-manual/index.html"
            target="_blank"
            rel="noopener noreferrer"
            className="block rounded-r-md pr-2.5 py-1.5 text-sm transition-colors border-l-2 border-transparent text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 pl-[calc(0.625rem-2px)]"
          >
            User manual
          </a>
        </nav>
        <button
          type="button"
          onClick={handleLogout}
          className="mt-2 w-full flex items-center gap-2 rounded-md border border-zinc-700 px-2.5 py-2 text-sm font-medium text-zinc-300 hover:bg-red-900/30 hover:border-red-700/50 hover:text-red-300 transition-colors"
        >
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15M12 9l-3 3m0 0 3 3m-3-3h12.75" />
          </svg>
          Sign out
        </button>
      </aside>

      <main className="flex-1 flex flex-col min-w-0 bg-zinc-950">
        {/* Mobile header */}
        <header
          ref={headerRef}
          className="md:hidden flex flex-col border-b border-zinc-800 bg-zinc-950 px-3 pt-2 pb-3 flex-shrink-0 w-full"
        >
          <Link
            href="/"
            className="flex justify-center focus:outline-none focus:ring-2 focus:ring-emerald-500 rounded"
          >
            <Image
              src="/ol_logo.png"
              alt="OptionsLab Backtesting Platform"
              width={240}
              height={120}
              className="h-20 w-auto max-w-[360px] object-contain"
              priority
            />
          </Link>
          <button
            type="button"
            onClick={() => setMobileMenuOpen((o) => !o)}
            className="mt-2 w-full flex items-center justify-center gap-2 rounded-md border border-zinc-700 bg-zinc-800/80 px-4 py-2.5 text-sm font-medium text-zinc-200 hover:bg-zinc-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            aria-expanded={mobileMenuOpen}
            aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
          >
            {mobileMenuOpen ? (
              <>
                <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
                Close menu
              </>
            ) : (
              <>
                <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                </svg>
                Menu
              </>
            )}
          </button>
        </header>

        {/* Mobile nav drawer — positioned right below the header */}
        {mobileMenuOpen && (
          <>
            <div
              className="md:hidden fixed inset-0 z-40 bg-zinc-950/60"
              style={{ top: mobileHeaderHeight }}
              onClick={() => setMobileMenuOpen(false)}
              aria-hidden
            />
            <nav
              className="md:hidden fixed left-0 right-0 z-50 border-b border-zinc-800 bg-zinc-950 p-3 space-y-0.5 shadow-lg"
              style={{ top: mobileHeaderHeight }}
              aria-label="Main navigation"
            >
              {NAV_LINKS.map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  className={`block rounded-r-md pr-2.5 py-1.5 text-sm transition-colors ${navLinkClass(href)}`}
                >
                  {label}
                </Link>
              ))}
              <a
                href="/user-manual/index.html"
                target="_blank"
                rel="noopener noreferrer"
                className="block rounded-r-md pr-2.5 py-1.5 text-sm transition-colors border-l-2 border-transparent text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 pl-[calc(0.625rem-2px)]"
              >
                User manual
              </a>
              <button
                type="button"
                onClick={handleLogout}
                className="mt-1 w-full flex items-center gap-2 rounded-md border border-zinc-700 px-2.5 py-2 text-sm font-medium text-zinc-300 hover:bg-red-900/30 hover:border-red-700/50 hover:text-red-300 transition-colors"
              >
                <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15M12 9l-3 3m0 0 3 3m-3-3h12.75" />
                </svg>
                Sign out
              </button>
            </nav>
          </>
        )}

        <div className="flex-1 flex flex-col min-h-0 min-w-0 p-3 sm:p-4 md:p-5 overflow-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
