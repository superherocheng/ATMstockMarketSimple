import { createContext, useContext, useState, type ReactNode, useCallback } from 'react';

interface DrawerContextType {
  open: boolean;
  setOpen: (v: boolean) => void;
  toggle: () => void;
}

const MoreDrawerContext = createContext<DrawerContextType>({
  open: false,
  setOpen: () => {},
  toggle: () => {},
});

export function MoreDrawerProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const toggle = useCallback(() => setOpen((v) => !v), []);
  return (
    <MoreDrawerContext.Provider value={{ open, setOpen, toggle }}>
      {children}
    </MoreDrawerContext.Provider>
  );
}

export function useMoreDrawer() {
  return useContext(MoreDrawerContext);
}
