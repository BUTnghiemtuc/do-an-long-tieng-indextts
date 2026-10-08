import { useSyncExternalStore } from "react";
import { authApi, UNAUTHORIZED_EVENT, type Me } from "./api";

export interface AuthState {
  ready: boolean;
  user: Me | null;
  setupRequired: boolean;
  allowRegistration: boolean;
  offline: boolean;
}

let state: AuthState = { ready: false, user: null, setupRequired: false, allowRegistration: true, offline: false };
const listeners = new Set<() => void>();

function set(patch: Partial<AuthState>) {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
}

/** Hỏi server: đã khởi tạo chưa, có cho đăng ký không, phiên hiện tại là ai. */
export async function refreshAuth(): Promise<AuthState> {
  try {
    const st = await authApi.status();
    set({ ready: true, user: st.user, setupRequired: st.setup_required, allowRegistration: st.allow_registration, offline: false });
  } catch {
    set({ ready: true, user: null, offline: true });
  }
  return state;
}

export async function logout() {
  try {
    await authApi.logout();
  } finally {
    set({ user: null });
  }
}

export function setUser(user: Me | null) {
  set({ user });
}

addEventListener(UNAUTHORIZED_EVENT, () => {
  if (state.user) set({ user: null });
});

export function useAuth(): AuthState {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
  );
}
