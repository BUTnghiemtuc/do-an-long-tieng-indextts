import { motion } from "motion/react";
import { ArrowLeft, ShieldAlert, WifiOff } from "lucide-react";
import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { Toaster } from "sonner";
import { Header } from "./components/Header";
import { Button, EqBars } from "./components/ui";
import { api } from "./lib/api";
import { refreshAuth, useAuth } from "./lib/auth";
import { currentHash, navigate, redirect, useRoute } from "./lib/router";
import { useTheme } from "./lib/theme";
import { ForceChangePassword, LoginPage, RegisterPage, SetupPage } from "./pages/AuthPages";
import { Home } from "./pages/Home";

// Trang nặng (wavesurfer, bảng quản trị) tải riêng để trang chủ và đăng nhập mở nhanh.
const JobPage = lazy(() => import("./pages/JobPage").then((m) => ({ default: m.JobPage })));
const AdminPage = lazy(() => import("./pages/admin/AdminPage").then((m) => ({ default: m.AdminPage })));
const AccountPage = lazy(() => import("./pages/AccountPage").then((m) => ({ default: m.AccountPage })));

function Splash() {
  return (
    <div className="grid min-h-dvh place-items-center">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }} className="flex flex-col items-center gap-3 text-accent">
        <EqBars n={6} className="h-7" />
        <span className="text-sm font-semibold text-muted">Đang mở phòng lồng tiếng…</span>
      </motion.div>
    </div>
  );
}

function Message({ icon, title, text, action }: { icon: ReactNode; title: string; text: ReactNode; action?: ReactNode }) {
  return (
    <>
      <Header />
      <div className="mx-auto flex max-w-md flex-col items-center px-4 py-24 text-center">
        <span className="grid size-14 place-items-center rounded-2xl bg-surface-2 text-muted [&>svg]:size-7">{icon}</span>
        <h1 className="mt-5 text-2xl font-extrabold tracking-tight">{title}</h1>
        <p className="mt-2 text-muted">{text}</p>
        {action && <div className="mt-6">{action}</div>}
      </div>
    </>
  );
}

function Footer({ disclaimer }: { disclaimer?: string }) {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-2 px-4 py-6 text-xs text-muted sm:px-6">
        <span>vidub · Đồ án lồng tiếng phim tự động sang tiếng Việt với IndexTTS</span>
        {disclaimer && <span>{disclaimer}</span>}
      </div>
    </footer>
  );
}

function Routes({ disclaimer }: { disclaimer?: string }) {
  const route = useRoute();
  const auth = useAuth();
  const publicRoute = route.name === "login" || route.name === "register" || route.name === "setup";

  // Chuyển hướng bắt buộc theo trạng thái đăng nhập.
  useEffect(() => {
    if (!auth.ready || auth.offline) return;
    if (auth.setupRequired) redirect("#/setup");
    else if (!auth.user && !publicRoute) redirect(`#/login?next=${encodeURIComponent(currentHash())}`);
    else if (auth.user && publicRoute) redirect("#/");
  }, [auth.ready, auth.offline, auth.setupRequired, auth.user, publicRoute]);

  if (!auth.ready) return <Splash />;
  if (auth.offline)
    return (
      <Message
        icon={<WifiOff />}
        title="Không kết nối được máy chủ"
        text={
          <>
            Kiểm tra <code className="rounded bg-surface-2 px-1.5 font-mono text-xs">uvicorn server.app:app</code> đã chạy chưa.
          </>
        }
        action={<Button onClick={() => refreshAuth()}>Thử lại</Button>}
      />
    );
  if (auth.setupRequired) return route.name === "setup" ? <SetupPage /> : <Splash />;
  if (!auth.user) {
    if (route.name === "register") return <RegisterPage />;
    if (route.name === "login") return <LoginPage next={route.next} />;
    return <Splash />;
  }
  if (auth.user.must_change_password) return <ForceChangePassword />;

  switch (route.name) {
    case "home":
      return (
        <>
          <Header />
          <Home />
          <Footer disclaimer={disclaimer} />
        </>
      );
    case "job":
      return <JobPage key={route.id} id={route.id} disclaimer={disclaimer} />;
    case "account":
      return <AccountPage />;
    case "admin":
      if (auth.user.role !== "admin")
        return (
          <Message
            icon={<ShieldAlert />}
            title="Không có quyền truy cập"
            text="Trang quản trị chỉ dành cho quản trị viên. Nếu bạn cần quyền này, hãy liên hệ người quản lý hệ thống."
            action={
              <Button icon={<ArrowLeft className="size-4" />} onClick={() => navigate("#/")}>
                Về dự án của tôi
              </Button>
            }
          />
        );
      return <AdminPage tab={route.tab} />;
    case "notfound":
      return (
        <Message
          icon={<span className="font-mono text-lg font-bold">404</span>}
          title="Không tìm thấy trang"
          text="Đường dẫn này không tồn tại hoặc đã bị xoá."
          action={
            <Button icon={<ArrowLeft className="size-4" />} onClick={() => navigate("#/")}>
              Về trang chủ
            </Button>
          }
        />
      );
    default:
      return <Splash />;
  }
}

export function App() {
  const { theme } = useTheme();
  const [disclaimer, setDisclaimer] = useState<string>();
  useEffect(() => {
    refreshAuth();
    api.meta().then((m) => setDisclaimer(m.disclaimer)).catch(() => {});
  }, []);

  return (
    <>
      <div className="film-grain" aria-hidden />
      <Suspense fallback={<Splash />}>
        <Routes disclaimer={disclaimer} />
      </Suspense>
      <Toaster theme={theme} position="bottom-right" richColors closeButton toastOptions={{ style: { fontFamily: "var(--font-sans)", borderRadius: 14 } }} />
    </>
  );
}
