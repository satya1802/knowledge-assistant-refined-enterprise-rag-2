import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import Login from "@/screens/Login";
import Account from "@/screens/Account";
import KnowledgeBase from "@/screens/KnowledgeBase";
import Chat from "@/screens/Chat";
import Users from "@/screens/Users";
import Settings from "@/screens/Settings";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  [
    "block rounded-[var(--brand-radius)] px-3 py-2 text-sm font-medium transition-colors",
    isActive ? "bg-[var(--brand-hover)] text-[var(--brand-fg)]" : "text-[var(--brand-fg-muted)]",
  ].join(" ");

export default function App() {
  return (
    <div className="flex min-h-screen">
      <aside
        className="w-56 shrink-0 border-r p-4"
        style={{
          backgroundColor: "var(--brand-surface)",
          borderColor: "var(--brand-border)",
        }}
      >
        <p
          className="mb-4 px-3 text-sm font-semibold"
          style={{ fontFamily: "var(--brand-font-heading)" }}
        >
          {"Knowledge Assistant Refined Enterprise RAG (2)"}
        </p>
        <nav className="flex flex-col gap-1">
          <NavLink to="/login" className={navLinkClass}>
            {"Login"}
          </NavLink>
          <NavLink to="/account" className={navLinkClass}>
            {"Account"}
          </NavLink>
          <NavLink to="/knowledge-base" className={navLinkClass}>
            {"Knowledge Base"}
          </NavLink>
          <NavLink to="/chat" className={navLinkClass}>
            {"Chat"}
          </NavLink>
          <NavLink to="/users" className={navLinkClass}>
            {"User Management"}
          </NavLink>
          <NavLink to="/settings" className={navLinkClass}>
            {"Settings"}
          </NavLink>
        </nav>
      </aside>
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/account" element={<Account />} />
          <Route path="/knowledge-base" element={<KnowledgeBase />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/users" element={<Users />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </main>
    </div>
  );
}
