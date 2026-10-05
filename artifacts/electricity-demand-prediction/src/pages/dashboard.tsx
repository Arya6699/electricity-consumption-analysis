import { useState } from 'react';
import { Activity, CalendarDays, Clock3, Database, Download, Gauge, TrendingDown, TrendingUp, Zap } from 'lucide-react';
import { useGetElectricityConsumptionAnalysis, getGetElectricityConsumptionAnalysisQueryKey, useGetElectricityHourlyConsumption, useGetElectricityMonthlyConsumption, useGetElectricityPeakDemand, useGetElectricityStatistics } from '@workspace/api-client-react';
import { Heading, LoadingBlock, QueryMessage, StatCard } from '@/components/workbench';
import { Panel, SeriesChart } from '@/components/charts';

export default function Dashboard() {
  const [filters, setFilters] = useState({ start_date: '', end_date: '', month: '', year: '', hour: '', day_of_week: '' });
  const params = { start_date: filters.start_date || undefined, end_date: filters.end_date || undefined, month: filters.month ? Number(filters.month) : undefined, year: filters.year ? Number(filters.year) : undefined, hour: filters.hour ? Number(filters.hour) : undefined, day_of_week: filters.day_of_week ? Number(filters.day_of_week) : undefined };
  const stats = useGetElectricityStatistics();
  const analysis = useGetElectricityConsumptionAnalysis(params, { query: { queryKey: getGetElectricityConsumptionAnalysisQueryKey(params) } });
  const peaks = useGetElectricityPeakDemand();
  const monthly = useGetElectricityMonthlyConsumption();
  const hourly = useGetElectricityHourlyConsumption();
  const clear = () => setFilters({ start_date: '', end_date: '', month: '', year: '', hour: '', day_of_week: '' });
  return <div className="page-enter">
    <Heading kicker="System overview / 01" title="Electricity Consumption Analytics & Demand Prediction" description="A working view of consumption patterns, peak demand and the next-step forecast." action={<button className="field flex items-center gap-2 px-3 py-2 text-xs" onClick={() => window.print()} data-testid="button-export-overview"><Download size={14} /> Export view</button>} />
    {(stats.isError || analysis.isError || peaks.isError) && <QueryMessage error retry={() => { void stats.refetch(); void analysis.refetch(); void peaks.refetch(); }} />}
    <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <StatCard label="Total consumption" value={stats.data?.total_consumption} unit={stats.data?.units} icon={Zap} accent note={`${stats.data?.rows_after_cleaning?.toLocaleString() ?? '—'} cleaned observations`} />
      <StatCard label="Average demand" value={stats.data?.average_consumption} unit={stats.data?.units} icon={Activity} note="Across the analyzed dataset" />
      <StatCard label="Peak demand" value={stats.data?.peak_demand} unit={stats.data?.units} icon={TrendingUp} note={peaks.data?.peak_timestamp ? new Date(peaks.data.peak_timestamp).toLocaleString() : 'Highest recorded interval'} />
      <StatCard label="Minimum demand" value={stats.data?.minimum_demand} unit={stats.data?.units} icon={TrendingDown} note={peaks.data?.minimum_timestamp ? new Date(peaks.data.minimum_timestamp).toLocaleString() : 'Lowest recorded interval'} />
      <StatCard label="Next interval" value={stats.data?.predicted_next_demand} unit={stats.data?.units} icon={Gauge} note="Model estimate, when available" />
    </div>
    <section className="panel mb-5 p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2"><CalendarDays size={15} className="text-[hsl(var(--primary))]" /><span className="text-xs font-semibold">Analysis filters</span><span className="text-[11px] text-[hsl(var(--muted-foreground))]">Apply dimensions to grouped series</span></div><button onClick={clear} className="text-[11px] font-semibold text-[hsl(var(--primary))]" data-testid="button-clear-filters">Clear filters</button></div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {[['start_date','From','date'],['end_date','To','date'],['month','Month','number'],['year','Year','number'],['hour','Hour','number'],['day_of_week','Weekday','number']].map(([key,label,type]) => <label key={key} className="grid gap-1 text-[10px] font-medium text-[hsl(var(--muted-foreground))]">{label}<input className="field h-9 w-full px-2 text-xs" type={type} min={key==='month'?1:key==='hour'||key==='day_of_week'?0:undefined} max={key==='month'?12:key==='hour'?23:key==='day_of_week'?6:undefined} value={filters[key as keyof typeof filters]} onChange={(e) => setFilters((old) => ({ ...old, [key]: e.target.value }))} data-testid={`input-filter-${key}`} /></label>)}
      </div>
    </section>
    <div className="grid gap-5 xl:grid-cols-[1.65fr_1fr]">
      <Panel title="Consumption trend" eyebrow="Signal / time series" action={<span className="mono text-[10px] text-[hsl(var(--muted-foreground))]">{analysis.data?.units || stats.data?.units || '—'}</span>}>{analysis.isLoading ? <LoadingBlock rows={4} /> : <SeriesChart data={analysis.data?.trend} unit={analysis.data?.units} height={292} />}</Panel>
      <Panel title="When the system peaks" eyebrow="Demand profile"><div className="mb-4 grid grid-cols-2 gap-3">{[['Peak',peaks.data?.peak_demand,peaks.data?.peak_timestamp],['Minimum',peaks.data?.minimum_demand,peaks.data?.minimum_timestamp]].map(([label,val,time]) => <div key={String(label)} className="rounded-lg bg-[hsl(var(--muted)/.65)] p-3"><div className="eyebrow">{label}</div><div className="mt-2 text-xl font-bold">{val == null ? '—' : Number(val).toLocaleString()}<span className="ml-1 text-[10px] font-normal text-[hsl(var(--muted-foreground))]">{peaks.data?.units}</span></div><div className="mt-1 text-[10px] text-[hsl(var(--muted-foreground))]">{time ? new Date(String(time)).toLocaleString() : 'Awaiting observations'}</div></div>)}</div><div className="mb-2 flex items-center gap-2 text-xs font-semibold"><Clock3 size={14} className="text-[hsl(var(--accent))]" /> Highest observed intervals</div>{peaks.data?.top_peaks?.length ? peaks.data.top_peaks.slice(0,5).map((peak,i)=><div className="flex items-center justify-between border-t border-[hsl(var(--border))] py-2 text-xs" key={`${peak.label}-${i}`}><span className="text-[hsl(var(--muted-foreground))]">{peak.label}</span><span className="mono font-medium">{peak.value.toLocaleString()} {peaks.data?.units}</span></div>) : <div className="py-5 text-center text-xs text-[hsl(var(--muted-foreground))]">Peak periods will appear when data is available.</div>}</Panel>
      <Panel title="Monthly energy profile" eyebrow="Seasonality / month"><SeriesChart data={monthly.data?.series} kind="bar" unit={monthly.data?.units} height={250} /></Panel>
      <Panel title="Typical demand by hour" eyebrow="Intraday / 24-hour cycle"><SeriesChart data={hourly.data?.series} unit={hourly.data?.units} height={250} /></Panel>
      <Panel title="Day-to-day pattern" eyebrow="Grouped analysis" className="xl:col-span-2"><div className="grid gap-5 md:grid-cols-2"><div><div className="mb-3 text-xs font-semibold">Daily consumption</div><SeriesChart data={analysis.data?.daily} kind="bar" unit={analysis.data?.units} height={220} /></div><div><div className="mb-3 text-xs font-semibold">Weekday and weekend</div><SeriesChart data={analysis.data?.weekday_weekend} kind="bar" unit={analysis.data?.units} height={220} /></div></div></Panel>
      <Panel title="Weekly rhythm" eyebrow="Week over week"><SeriesChart data={analysis.data?.weekly} kind="bar" unit={analysis.data?.units} height={230} /></Panel>
      <Panel title="Seasonal profile" eyebrow="Seasonal grouping"><SeriesChart data={analysis.data?.seasonal} kind="bar" unit={analysis.data?.units} height={230} /></Panel>
      <Panel title="Consumption distribution" eyebrow="Value bands"><SeriesChart data={analysis.data?.distribution} kind="bar" unit={analysis.data?.units} height={230} /></Panel>
      <Panel title="Correlation signals" eyebrow="Relationship scan"><div className="space-y-3">{analysis.data?.correlation && Object.keys(analysis.data.correlation).length ? Object.entries(analysis.data.correlation).sort((a,b)=>Math.abs(b[1])-Math.abs(a[1])).map(([name,value])=><div key={name}><div className="mb-1.5 flex justify-between text-[11px]"><span>{name}</span><span className="mono">{value.toFixed(3)}</span></div><div className="h-1.5 overflow-hidden rounded-full bg-[hsl(var(--muted))]"><div className={`h-full rounded-full ${value<0?'bg-[hsl(var(--accent))]':'bg-[hsl(var(--primary))]'}`} style={{width:`${Math.min(100,Math.abs(value)*100)}%`}} /></div></div>) : <div className="py-6 text-center text-xs text-[hsl(var(--muted-foreground))]">Correlation values appear when analysis data is available.</div>}</div></Panel>
    </div>
    <div className="mt-5 flex items-center gap-2 text-[10px] text-[hsl(var(--muted-foreground))]"><Database size={13} /> All figures reflect the currently profiled dataset. No illustrative values are shown.</div>
  </div>;
}
