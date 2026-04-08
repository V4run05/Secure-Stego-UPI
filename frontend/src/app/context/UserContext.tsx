import { createContext, useContext, useState, useEffect, ReactNode } from "react";

export interface User {
  userId: string;
  fullName: string;
  isRegistered: boolean;
}

interface UserContextValue {
  user: User | null;
  setUser: (u: User | null) => void;
  logout: () => void;
}

export const UserContext = createContext<UserContextValue>({
  user: null,
  setUser: () => {},
  logout: () => {},
});

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<User | null>(() => {
    try {
      const stored = sessionStorage.getItem("currentUser");
      return stored ? (JSON.parse(stored) as User) : null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    if (user) {
      sessionStorage.setItem("currentUser", JSON.stringify(user));
    } else {
      sessionStorage.removeItem("currentUser");
    }
  }, [user]);

  const setUser = (u: User | null) => setUserState(u);

  const logout = () => {
    setUserState(null);
    sessionStorage.clear();
  };

  return (
    <UserContext.Provider value={{ user, setUser, logout }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  return useContext(UserContext);
}
