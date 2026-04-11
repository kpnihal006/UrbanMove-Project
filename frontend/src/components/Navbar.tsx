"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { signOut } from "firebase/auth";
import { auth } from "@/lib/firebase";
import clsx from "clsx";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/map",       label: "Live Map"  },
];

export default function Navbar() {
  const pathname = usePathname();
  const router   = useRouter();

  const handleSignOut = async () => {
    await signOut(auth);
    router.push("/login");
  };

  return (
    <nav className="fixed top-0 inset-x-0 z-50 h-14 bg-gray-900/80 backdrop-blur border-b border-gray-800 flex items-center px-4 gap-6">
      {/* Logo */}
      <Link href="/dashboard" className="flex items-center gap-2 font-bold text-white">
        <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center">
          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
        </div>
        UrbanMove
      </Link>

      {/* Links */}
      <div className="flex items-center gap-1 ml-2">
        {NAV_LINKS.map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            className={clsx(
              "px-3 py-1.5 rounded-lg text-sm font-medium transition",
              pathname.startsWith(href)
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-white hover:bg-gray-800",
            )}
          >
            {label}
          </Link>
        ))}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Live indicator */}
      <div className="flex items-center gap-1.5 text-xs text-green-400">
        <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
        Live
      </div>

      {/* Sign out */}
      <button
        onClick={handleSignOut}
        className="text-sm text-gray-400 hover:text-white transition px-3 py-1.5 rounded-lg hover:bg-gray-800"
      >
        Sign out
      </button>
    </nav>
  );
}
