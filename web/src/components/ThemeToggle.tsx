import { AnimatePresence, motion } from "motion/react";
import { Moon, Sun } from "lucide-react";
import { useRef } from "react";
import { useTheme } from "../lib/theme";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const ref = useRef<HTMLButtonElement>(null);
  const dark = theme === "dark";
  return (
    <button
      ref={ref}
      onClick={() => toggle(ref.current)}
      aria-label={dark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}
      title={dark ? "Giao diện sáng" : "Giao diện tối"}
      className="relative inline-flex h-9 w-[68px] items-center rounded-full border border-line bg-surface-2 p-1 transition hover:border-line-strong"
    >
      <motion.span
        layout
        transition={{ type: "spring", stiffness: 500, damping: 32 }}
        className="grid size-7 place-items-center rounded-full bg-surface shadow-md ring-1 ring-line"
        style={{ marginLeft: dark ? "auto" : 0 }}
      >
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={theme}
            initial={{ rotate: -90, scale: 0, opacity: 0 }}
            animate={{ rotate: 0, scale: 1, opacity: 1 }}
            exit={{ rotate: 90, scale: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {dark ? <Moon className="size-4 text-accent" /> : <Sun className="size-4 text-accent-strong" />}
          </motion.span>
        </AnimatePresence>
      </motion.span>
    </button>
  );
}
