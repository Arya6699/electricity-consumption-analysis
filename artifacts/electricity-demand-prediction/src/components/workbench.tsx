import { useState, type ReactNode } from 'react';
import { Link, useLocation } from 'wouter';
import { Activity, BarChart3, ChevronDown, Database, Menu, Zap, X } from 'lucide-react';

const navigation = [
  { href: '/dashboard', label: 'Overview', icon: BarChart3 },
  { href: '/dataset', label: 'Dataset lab', icon: Database },
  { href: '/prediction', label: 'Demand forecast', icon: Zap },
  { href: '/models', label: 'Model evaluation', icon: Activity },
];

export function Shell({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const active = navigation.find((item) => location === item.href)?.label ?? 'Overview';
  return (
    <div className="app-shell min-h-[100dvh] md:flex">
      <aside className="sidebar hidden w-[248px] shrink-0 flex-col md:flex">
        <Link href="/dashboard" className="flex items-center gap-3 px-6 py-7" data-testid="link-brand">
          <span className="brand-mark flex h-10 w-10 items-center justify-center rounded-xl"><Zap size={21} strokeWidth={2.4} /></span>
          <span><span className="block font-[var(--app-font-serif)] text-[15px] font-extrabold tracking-[-.04em]">Wattwise</span><span className="mt-0.5 block text-[10px] tracking-[.12em] text-white/50">ENERGY ANALYTICS LAB</span></span>
        </Link>
        <div className="px-5 pb-3 pt-7 eyebrow text-white/40">Workspace</div>
        <nav className="flex flex-1 flex-col gap-1 px-3">
          {navigation.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} className={`nav-item flex items-center gap-3 rounded-lg px-3 py-3 text-[13px] font-medium ${location === href ? 'active' : ''}`} data-testid={`link-nav-${label.toLowerCase().replaceAll(' ', '-')}`}>
              <Icon size={17} strokeWidth={1.8} /><span>{label}</span>{location === href && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[hsl(var(--sidebar-primary))]" />}
            </Link>
          ))}
        </nav>
        <div className="mx-4 mb-4 rounded-xl border border-white/10 bg-white/[.04] p-4">
          <div className="eyebrow text-white/40">Academic project</div>
          <p className="mt-2 text-xs leading-relaxed text-white/70">Explore real-world load patterns and make forecasting explainable.</p>
          <div className="mt-4 flex items-center gap-2 text-[10px] text-white/45"><span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--sidebar-primary))]" /> CSE–AIML workbench</div>
        </div>
        <div className="border-t border-white/10 px-6 py-4 text-[10px] text-white/40">ELECTRICITY DEMAND STUDY <span className="float-right">01</span></div>
      </aside>
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex h-[68px] items-center justify-between border-b border-[hsl(var(--border))] bg-[hsl(var(--background)/.94)] px-4 backdrop-blur-md sm:px-8">
          <div className="flex items-center gap-3">
            <button className="field flex h-9 w-9 items-center justify-center md:hidden" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} onClick={() => setMenuOpen(!menuOpen)} data-testid="button-mobile-navigation">{menuOpen ? <X size={17} /> : <Menu size={17} />}</button>
            <div className="text-xs text-[hsl(var(--muted-foreground))]">Wattwise <span className="mx-2">/</span><span className="font-semibold text-[hsl(var(--foreground))]">{active}</span></div>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-3 py-1.5 text-[11px] text-[hsl(var(--muted-foreground))]"><span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--primary))]" /> Analytics ready <ChevronDown size={13} /></div>
        </header>
        {menuOpen && <nav className="sidebar absolute z-30 flex w-full flex-col gap-1 p-3 shadow-xl md:hidden">{navigation.map(({ href, label, icon: Icon }) => <Link key={href} href={href} onClick={() => setMenuOpen(false)} className={`nav-item flex items-center gap-3 rounded-lg px-3 py-3 text-sm ${location === href ? 'active' : ''}`}><Icon size={17} />{label}</Link>)}</nav>}
        <main className="mx-auto max-w-[1440px] px-4 pb-12 pt-7 sm:px-8 lg:px-10">{children}</main>
        <footer className="mx-auto flex max-w-[1440px] items-center justify-between border-t border-[hsl(var(--border))] px-4 py-5 text-[10px] text-[hsl(var(--muted-foreground))] sm:px-8 lg:px-10"><span>ELECTRICITY CONSUMPTION ANALYTICS & DEMAND PREDICTION</span><span className="mono">ACADEMIC ANALYTICS</span></footer>
      </div>
    </div>
  );
}

export function Heading({ kicker, title, description, action }: { kicker: string; title: string; description: string; action?: ReactNode }) {
  return <div className="mb-7 flex flex-wrap items-end justify-between gap-4 page-enter"><div><div className="eyebrow mb-2">{kicker}</div><h1 className="font-[var(--app-font-serif)] text-[30px] font-bold tracking-[-.045em] text-[hsl(var(--foreground))] sm:text-[36px]">{title}</h1><p className="mt-2 max-w-2xl text-sm text-[hsl(var(--muted-foreground))]">{description}</p></div>{action}</div>;
}

export function LoadingBlock({ rows = 3 }: { rows?: number }) {
  return <div className="space-y-3" aria-label="Loading data" data-testid="status-loading">{Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton h-11 rounded-lg" />)}</div>;
}

export function QueryMessage({ error, retry }: { error: boolean; retry: () => void }) {
  if (!error) return null;
  return <div className="panel flex items-center justify-between gap-4 p-4 text-sm" role="alert" data-testid="status-query-error"><span>We could not load this data. Check the API connection and try again.</span><button className="btn-primary rounded-lg px-3 py-2 text-xs font-semibold" onClick={retry} data-testid="button-retry">Retry</button></div>;
}

export function StatCard({ label, value, unit, note, icon: Icon, accent = false }: { label: string; value: string | number | null | undefined; unit?: string; note?: string; icon: typeof Zap; accent?: boolean }) {
  return <article className={`panel relative overflow-hidden p-5 ${accent ? 'bg-[hsl(var(--primary)/.08)]' : ''}`} data-testid={`card-stat-${label.toLowerCase().replaceAll(' ', '-')}`}><div className="flex items-start justify-between"><span className="eyebrow">{label}</span><span className={`flex h-8 w-8 items-center justify-center rounded-lg ${accent ? 'bg-[hsl(var(--primary)/.15)] text-[hsl(var(--primary))]' : 'bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]'}`}><Icon size={16} /></span></div><div className="mt-5 font-[var(--app-font-serif)] text-[26px] font-bold tracking-[-.04em]">{value === null || value === undefined ? '—' : typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : value}<span className="ml-1.5 text-xs font-medium text-[hsl(var(--muted-foreground))]">{unit}</span></div>{note && <div className="mt-1.5 text-[11px] text-[hsl(var(--muted-foreground))]">{note}</div>}</article>;
}
