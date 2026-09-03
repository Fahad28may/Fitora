import { createContext, useContext, useEffect, useState, type PropsWithChildren } from "react";

import { authApi } from "../api/auth";
import type { UserOut } from "../api/types";
import { tokenStorage } from "./tokenStorage";

interface AuthContextValue {
  user: UserOut | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: PropsWithChildren): React.JSX.Element {
  const [user, setUser] = useState<UserOut | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function hydrate(): Promise<void> {
      const accessToken = await tokenStorage.getAccessToken();
      if (!accessToken) {
        if (!cancelled) setIsLoading(false);
        return;
      }
      try {
        const me = await authApi.me();
        if (!cancelled) setUser(me);
      } catch {
        await tokenStorage.clear();
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void hydrate();
    return () => {
      cancelled = true;
    };
  }, []);

  async function login(email: string, password: string): Promise<void> {
    const { user: loggedInUser, tokens } = await authApi.login(email, password);
    await tokenStorage.setTokens(tokens.access_token, tokens.refresh_token);
    setUser(loggedInUser);
  }

  async function register(email: string, password: string): Promise<void> {
    const { user: newUser, tokens } = await authApi.register(email, password);
    await tokenStorage.setTokens(tokens.access_token, tokens.refresh_token);
    setUser(newUser);
  }

  async function logout(): Promise<void> {
    const refreshToken = await tokenStorage.getRefreshToken();
    if (refreshToken) {
      try {
        await authApi.logout(refreshToken);
      } catch {
        // Best-effort server-side session revocation — local state is
        // cleared regardless so the user is signed out on this device.
      }
    }
    await tokenStorage.clear();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
