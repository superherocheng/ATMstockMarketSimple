import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useEtfShareStatus, useFetchStatus, useInvalidateOnFetchDone } from "@/hooks/useApi";
import Overview from "@/pages/Overview";
import ETFDetail from "@/pages/ETFDetail";

const navCls = ({ isActive }: { isActive: boolean }) =>
  isActive ? "text-foreground font-medium" : "text-muted-foreground hover:text-foreground";

function TopBar() {
  const status = useFetchStatus();
  const share = useEtfShareStatus();

  // DONE 只在「刚点击的刷新跑完」这一刻闪现（running→done 转换），
  // 不是每次进页面都显示；下一次刷新开始时自动清除。
  const [justDone, setJustDone] = useState(false);
  const prevRunning = useRef(false);
  useEffect(() => {
    const running = !!status.data?.running;
    if (prevRunning.current && !running) setJustDone(true);
    if (running) setJustDone(false);
    prevRunning.current = running;
  }, [status.data?.running]);

  const rawDate = share.data?.latest_trading_date;
  const dateDisplay =
    rawDate && rawDate.length === 8 ? `${rawDate.slice(4, 6)}-${rawDate.slice(6, 8)}` : null;
  const fresh = share.data?.summary?.fresh;
  const total = share.data?.summary?.total;
  const shareDisplay = fresh != null && total != null ? `${fresh}/${total}` : null;

  return (
    <nav className="sticky top-0 z-20 mx-auto max-w-7xl px-6 pt-3">
      <div className="flex h-14 items-center gap-3 rounded-lg border border-border bg-card/70 px-4 shadow-sm backdrop-blur-xl sm:gap-6 sm:px-6">
        <Link to="/" className="font-bold tracking-tight text-foreground">
          ATMstockMarket
        </Link>
        <div className="flex items-center gap-5 text-sm">
          <NavLink to="/" className={navCls} end>
            概览
          </NavLink>
          <NavLink to="/etf" className={navCls}>
            ETF
          </NavLink>
        </div>
        <div className="ml-auto flex items-center gap-3 font-mono text-xs text-muted-foreground">
          {dateDisplay && (
            <span className="hidden sm:inline" title="最新数据日期">
              数据 {dateDisplay}
            </span>
          )}
          {shareDisplay && (
            <span className="hidden sm:inline" title="ETF份额覆盖（已更新/总数）">
              份额 {shareDisplay}
            </span>
          )}
          {status.data?.running ? (
            <span>刷新中 {status.data.progress}%</span>
          ) : justDone ? (
            <span>✓ DONE</span>
          ) : null}
        </div>
      </div>
    </nav>
  );
}

export default function App() {
  useInvalidateOnFetchDone();
  return (
    <div className="min-h-screen text-foreground">
      <TopBar />
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/etf" element={<ETFDetail />} />
        {/* /analysis removed — redirect any old link/bookmark home */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
