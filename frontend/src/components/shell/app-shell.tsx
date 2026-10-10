"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  Building2,
  ClipboardList,
  Database,
  FileBarChart,
  Gauge,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  SearchCheck,
  Server,
  Upload,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Spinner } from "@/components/ui/feedback";
import { api } from "@/lib/api";
import { brand } from "@/lib/brand";
import { useMe } from "@/lib/session";
import type { Me } from "@/lib/types";

type NavItem = { href: string; label: string; icon: ReactNode; perm?: string; platform?: boolean };
type NavGroup = { title: string; items: NavItem[] };

const NAV: NavGroup[] = [
  { title: "General", items: [{ href: "/dashboard", label: "Panel ejecutivo", icon: <LayoutDashboard />, perm: "dashboard.read" }] },
  {
    title: "Datos",
    items: [
      { href: "/imports/new", label: "Importar datos", icon: <Upload />, perm: "data.import" },
      { href: "/imports", label: "Importaciones", icon: <History />, perm: "data.read" },
      { href: "/datasets", label: "Conjuntos de datos", icon: <Database />, perm: "data.read" },
    ],
  },
  {
    title: "Análisis",
    items: [
      { href: "/findings", label: "Hallazgos", icon: <SearchCheck />, perm: "findings.read" },
      { href: "/kpis", label: "Indicadores", icon: <Gauge />, perm: "kpi.read" },
      { href: "/reports", label: "Reportes", icon: <FileBarChart />, perm: "reports.generate" },
    ],
  },
  {
    title: "Administración",
    items: [
      { href: "/settings/users", label: "Usuarios", icon: <Users />, perm: "users.read" },
      { href: "/settings/organization", label: "Organización", icon: <Building2 />, perm: "org.settings.read" },
      { href: "/audit", label: "Auditoría", icon: <ClipboardList />, perm: "audit.read" },
      { href: "/platform", label: "Plataforma", icon: <Server />, platform: true },
    ],
  },
];

function visible(item: NavItem, me: Me): boolean {
  if (item.platform) return me.user.is_platform_admin;
  return !item.perm || me.permissions.includes(item.perm);
}

function isActive(pathname: string, href: string): boolean {
  if (href === "/imports") return pathname === "/imports" || /^\/imports\/\d+/.test(pathname);
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: ReactNode }) {
  const { data: me, isLoading, error } = useMe();
  const pathname = usePathname();
  const router = useRouter();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);

  const logout = useMutation({
    mutationFn: () => api("/auth/logout", { method: "POST" }),
    onSettled: () => {
      qc.clear();
      router.replace("/login");
    },
  });
  const switchOrg = useMutation({
    mutationFn: (organization_id: number) => api<Me>("/auth/switch-organization", { body: { organization_id } }),
    onSuccess: () => {
      qc.clear();
      router.replace("/dashboard");
    },
  });

  if (isLoading || !me) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        {error ? <p className="text-sm text-muted">No se pudo cargar la sesión.</p> : <Spinner label="Cargando sesión…" />}
      </div>
    );
  }

  const nav = (
    <nav aria-label="Navegación principal" className="space-y-5">
      {NAV.map((group) => {
        const items = group.items.filter((i) => visible(i, me));
        if (!items.length) return null;
        return (
          <div key={group.title}>
            <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{group.title}</div>
            <ul className="space-y-0.5">
              {items.map((item) => (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={() => setOpen(false)}
                    aria-current={isActive(pathname, item.href) ? "page" : undefined}
                    className={clsx(
                      "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm [&_svg]:h-4 [&_svg]:w-4",
                      isActive(pathname, item.href) ? "bg-white/10 font-medium text-white" : "text-slate-300 hover:bg-white/5 hover:text-white",
                    )}
                  >
                    {item.icon}
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );

  const sidebar = (
    <div className="flex h-full flex-col bg-slate-900 px-3 py-4">
      <Link href="/dashboard" className="mb-6 flex items-center gap-2 px-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/brand/logo.svg" alt="" className="h-7 w-7" />
        <div className="leading-tight">
          <div className="text-sm font-semibold text-white">{brand.shortName}</div>
          <div className="text-[11px] text-slate-400">{brand.name}</div>
        </div>
      </Link>
      <div className="flex-1 overflow-y-auto">{nav}</div>
      <div className="mt-4 border-t border-white/10 px-3 pt-3 text-[11px] text-slate-500">v0.1 · primera versión funcional</div>
    </div>
  );

  return (
    <div className="min-h-screen lg:pl-60">
      <aside className="fixed inset-y-0 left-0 hidden w-60 lg:block">{sidebar}</aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setOpen(false)} aria-hidden />
          <aside className="absolute inset-y-0 left-0 w-64">{sidebar}</aside>
        </div>
      )}
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-panel/95 px-4 backdrop-blur lg:px-8">
        <button className="rounded p-1.5 text-ink hover:bg-slate-100 lg:hidden" onClick={() => setOpen(!open)} aria-label="Abrir menú">
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
        <div className="min-w-0 flex-1">
          {me.memberships.length > 1 ? (
            <label className="flex items-center gap-2 text-sm">
              <span className="sr-only">Organización activa</span>
              <Building2 className="h-4 w-4 text-muted" aria-hidden />
              <select
                className="max-w-xs truncate rounded-md border border-line bg-white px-2 py-1 text-sm"
                value={me.organization?.id ?? ""}
                onChange={(e) => switchOrg.mutate(Number(e.target.value))}
              >
                {me.memberships.map((m) => (
                  <option key={m.organization_id} value={m.organization_id}>
                    {m.organization_name}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <div className="flex items-center gap-2 truncate text-sm font-medium">
              <Building2 className="h-4 w-4 text-muted" aria-hidden />
              {me.organization?.name ?? "Sin organización"}
            </div>
          )}
        </div>
        <div className="hidden text-right text-xs leading-tight sm:block">
          <div className="font-medium text-ink">{me.user.display_name}</div>
          <div className="text-muted">{me.role_label ?? (me.user.is_platform_admin ? "Administrador de plataforma" : "")}</div>
        </div>
        <Link href="/change-password" className="hidden rounded px-2 py-1 text-xs text-muted hover:bg-slate-100 md:inline">
          Contraseña
        </Link>
        <button
          onClick={() => logout.mutate()}
          className="flex items-center gap-1.5 rounded px-2 py-1.5 text-sm text-muted hover:bg-slate-100 hover:text-ink"
        >
          <LogOut className="h-4 w-4" aria-hidden />
          <span className="hidden sm:inline">Salir</span>
        </button>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
        {!me.organization && !me.user.is_platform_admin ? (
          <p className="text-sm text-muted">Tu usuario no tiene una organización activa. Contacta a tu administrador.</p>
        ) : (
          children
        )}
      </main>
    </div>
  );
}
