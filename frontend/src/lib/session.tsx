"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./api";
import type { Me } from "./types";

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/auth/me"), staleTime: 60_000, retry: false });
}

/** UI hint only: the backend enforces every permission. */
export function useCan() {
  const { data } = useMe();
  return (perm: string) => !!data?.permissions.includes(perm);
}

export function useRefreshAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries();
}
