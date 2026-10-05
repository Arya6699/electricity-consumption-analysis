import { useState } from 'react';
import { usePredictElectricityDemand } from '@workspace/api-client-react';
import type { DemandPredictionInput } from '@workspace/api-client-react';
import { ArrowRight, CalendarClock, CloudSun, Gauge, LineChart, Zap } from 'lucide-react';
import { Heading, StatCard } from '@/components/workbench';
import { Panel } from '@/components/charts';

export default function Prediction() {
  const [timestamp, setTimestamp] = useState('');
  const [temperature, setTemperature] = useState('');
  const [recent, setRecent] = useState('');
  const prediction = usePredictElectricityDemand();
  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!timestamp) return;
    const input: DemandPredictionInput = { timestamp: new Date(timestamp).toISOString(), temperature: temperature === '' ? null : Number(temperature), recent_consumption: recent === '' ? null : Number(recent) };
    prediction.mutate({ data: input });
  };
  return <div className="page-enter">
    <Heading kicker="Forecast studio / 03" title="Put a number on what comes next." description="Set a future interval and optional context. The prediction comes from the trained demand model." />
    <div className="grid gap-5 xl:grid-cols-[.88fr_1.12fr]">
      <Panel title="Forecast inputs" eyebrow="Prediction request">
        <form onSubmit={submit} className="space-y-4">
          <label className="block text-xs font-semibold">Forecast date and hour<span className="mt-2 flex items-center gap-2"><CalendarClock size={15} className="text-[hsl(var(--muted-foreground))]" /><input required type="datetime-local" className="field h-11 min-w-0 flex-1 px-3 text-sm font-normal" value={timestamp} onChange={(e)=>setTimestamp(e.target.value)} data-testid="input-prediction-timestamp" /></span></label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-xs font-semibold">Temperature <span className="font-normal text-[hsl(var(--muted-foreground))]">(optional)</span><span className="mt-2 flex items-center gap-2"><CloudSun size={15} className="text-[hsl(var(--muted-foreground))]" /><input type="number" step="any" className="field h-10 w-full px-3 text-sm font-normal" placeholder="°C" value={temperature} onChange={(e)=>setTemperature(e.target.value)} data-testid="input-prediction-temperature" /></span></label>
            <label className="block text-xs font-semibold">Recent consumption <span className="font-normal text-[hsl(var(--muted-foreground))]">(optional)</span><span className="mt-2 flex items-center gap-2"><Zap size={15} className="text-[hsl(var(--muted-foreground))]" /><input type="number" min="0" step="any" className="field h-10 w-full px-3 text-sm font-normal" placeholder="Latest reading" value={recent} onChange={(e)=>setRecent(e.target.value)} data-testid="input-prediction-recent-consumption" /></span></label>
          </div>
          {prediction.isError && <div className="rounded-lg border border-[hsl(var(--destructive)/.25)] bg-[hsl(var(--destructive)/.06)] p-3 text-xs text-[hsl(var(--destructive))]" role="alert">{(prediction.error as Error)?.message || 'Forecast could not be generated. Train a model and retry.'}</div>}
          <button type="submit" disabled={!timestamp || prediction.isPending} className="btn-primary flex w-full items-center justify-center gap-2 rounded-lg px-4 py-3 text-xs font-semibold" data-testid="button-generate-prediction">{prediction.isPending ? 'Calculating forecast…' : 'Generate demand forecast'}{!prediction.isPending && <ArrowRight size={15} />}</button>
          <p className="text-[10px] leading-relaxed text-[hsl(var(--muted-foreground))]">Optional signals are passed only when supplied. Units follow the active dataset profile.</p>
        </form>
      </Panel>
      <div className="space-y-5">
        {prediction.data ? <><div className="overflow-hidden rounded-[15px] bg-[hsl(var(--sidebar))] p-6 text-[hsl(var(--sidebar-foreground))] sm:p-8" data-testid="card-prediction-result"><div className="eyebrow text-white/55">FORECAST RESULT / {new Date(prediction.data.timestamp).toLocaleDateString()}</div><div className="mt-9 flex items-end justify-between gap-3"><div><div className="text-[11px] text-white/60">Predicted demand</div><div className="mt-1 font-[var(--app-font-serif)] text-5xl font-bold tracking-[-.05em] sm:text-6xl">{prediction.data.predicted_demand.toLocaleString(undefined,{maximumFractionDigits:2})}<span className="ml-2 text-base font-medium text-white/55">{prediction.data.units}</span></div></div><div className="mb-1 rounded-full border border-white/15 px-3 py-1.5 text-[10px] text-white/65">{prediction.data.model}</div></div><div className="mt-8 border-t border-white/15 pt-4 text-xs text-white/60">Forecast interval <span className="float-right text-white">{new Date(prediction.data.timestamp).toLocaleString()}</span></div></div><StatCard label="Predicted interval demand" value={prediction.data.predicted_demand} unit={prediction.data.units} icon={Gauge} accent note={`Produced by ${prediction.data.model}`} /></> :
          <div className="panel flex min-h-[330px] flex-col justify-between overflow-hidden p-6 sm:p-8"><div><div className="eyebrow">Forecast preview</div><h2 className="mt-3 max-w-sm font-[var(--app-font-serif)] text-3xl font-bold leading-tight tracking-[-.045em]">Demand becomes easier to reason about.</h2><p className="mt-3 max-w-md text-sm leading-relaxed text-[hsl(var(--muted-foreground))]">Choose a date and an hour to request a forecast. The result will include its timestamp, model and measurement unit.</p></div><div className="mt-8 flex items-center gap-3 rounded-lg border border-dashed border-[hsl(var(--border))] p-4"><LineChart size={18} className="text-[hsl(var(--primary))]" /><span className="text-xs text-[hsl(var(--muted-foreground))]">Submit a forecast request to reveal the model result.</span></div></div>}
      </div>
    </div>
  </div>;
}
