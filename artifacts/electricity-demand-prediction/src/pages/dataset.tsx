import { useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { AlertCircle, Check, FileSpreadsheet, RefreshCw, UploadCloud } from 'lucide-react';
import { getGetElectricityDatasetInfoQueryKey, getGetElectricityDatasetPreviewQueryKey, useGetElectricityDatasetInfo, useGetElectricityDatasetPreview, useUploadElectricityDataset } from '@workspace/api-client-react';
import { Heading, LoadingBlock, QueryMessage } from '@/components/workbench';
import { Panel } from '@/components/charts';

export default function Dataset() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState('');
  const queryClient = useQueryClient();
  const info = useGetElectricityDatasetInfo();
  const preview = useGetElectricityDatasetPreview({ limit: 10 }, { query: { queryKey: getGetElectricityDatasetPreviewQueryKey({ limit: 10 }) } });
  const upload = useUploadElectricityDataset({ mutation: { onSuccess: async () => { await queryClient.invalidateQueries(); setFile(null); if (inputRef.current) inputRef.current.value = ''; } } });
  const sendFile = async () => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.csv')) { setUploadError('Choose a CSV file to continue.'); return; }
    setUploadError('');
    try { const csv_text = await file.text(); upload.mutate({ data: { filename: file.name, csv_text } }); }
    catch { setUploadError('This file could not be read. Choose another CSV and retry.'); }
  };
  const missing = Object.entries(info.data?.missing_values ?? {});
  const summary = Object.entries(info.data?.summary ?? {});
  return <div className="page-enter">
    <Heading kicker="Data foundation / 02" title="Dataset lab" description="Inspect data quality, understand the schema and upload a CSV to re-profile the analysis." />
    {(info.isError || preview.isError) && <QueryMessage error retry={() => { void info.refetch(); void preview.refetch(); }} />}
    <div className="mb-5 grid gap-5 lg:grid-cols-[.86fr_1.14fr]">
      <Panel title="Bring your own dataset" eyebrow="CSV ingestion">
        <button className="group flex min-h-[170px] w-full flex-col items-center justify-center rounded-xl border border-dashed border-[hsl(var(--input))] bg-[hsl(var(--muted)/.45)] px-5 text-center transition hover:border-[hsl(var(--primary))]" onClick={() => inputRef.current?.click()} data-testid="button-choose-csv"><span className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-[hsl(var(--primary)/.12)] text-[hsl(var(--primary))]"><UploadCloud size={21} /></span><span className="text-sm font-semibold">{file?.name || 'Select a CSV file'}</span><span className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">CSV format · file is profiled by the analysis service</span></button>
        <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} data-testid="input-dataset-file" />
        {uploadError && <div className="mt-3 flex items-center gap-2 text-xs text-[hsl(var(--destructive))]" role="alert"><AlertCircle size={14} />{uploadError}</div>}
        {upload.isError && <div className="mt-3 text-xs text-[hsl(var(--destructive))]" role="alert">{(upload.error as Error)?.message || 'Upload failed. Check the file and retry.'}</div>}
        <div className="mt-4 flex items-center justify-between gap-3"><span className="text-[10px] text-[hsl(var(--muted-foreground))]">Your current profile updates after a successful upload.</span><button disabled={!file || upload.isPending} onClick={sendFile} className="btn-primary flex items-center gap-2 rounded-lg px-4 py-2.5 text-xs font-semibold" data-testid="button-upload-csv">{upload.isPending ? <RefreshCw size={14} className="animate-spin" /> : <UploadCloud size={14} />}{upload.isPending ? 'Profiling…' : 'Upload & profile'}</button></div>
        {upload.isSuccess && <div className="mt-3 flex items-center gap-2 text-xs text-[hsl(var(--primary))]"><Check size={14} />Dataset profile refreshed successfully.</div>}
      </Panel>
      <Panel title="Current profile" eyebrow="Dataset overview" action={info.data && <span className="flex items-center gap-1.5 rounded-full bg-[hsl(var(--primary)/.1)] px-2.5 py-1 text-[10px] font-semibold text-[hsl(var(--primary))]"><span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--primary))]" />Profile available</span>}>
        {info.isLoading ? <LoadingBlock rows={4} /> : info.data ? <><div className="mb-5 flex items-center gap-3 border-b border-[hsl(var(--border))] pb-4"><span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[hsl(var(--muted))]"><FileSpreadsheet size={19} /></span><div className="min-w-0"><div className="truncate text-sm font-semibold">{info.data.filename}</div><div className="mt-1 text-[10px] text-[hsl(var(--muted-foreground))]">Source: {info.data.source}</div></div></div><div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{[['Rows',info.data.rows],['Columns',info.data.column_count],['Duplicates',info.data.duplicate_rows],['Units',info.data.units]].map(([k,v])=><div className="rounded-lg bg-[hsl(var(--muted)/.55)] p-3" key={String(k)}><div className="eyebrow">{k}</div><div className="mt-2 truncate text-sm font-semibold">{typeof v==='number'?v.toLocaleString():v}</div></div>)}</div><div className="mt-4 grid gap-2 text-xs sm:grid-cols-2"><div><span className="text-[hsl(var(--muted-foreground))]">Target column</span><div className="mt-1 font-medium">{info.data.target_column || 'Not identified'}</div></div><div><span className="text-[hsl(var(--muted-foreground))]">Datetime column</span><div className="mt-1 font-medium">{info.data.datetime_column || 'Not identified'}</div></div></div></> : <div className="flex h-48 flex-col items-center justify-center text-center"><FileSpreadsheet size={24} className="text-[hsl(var(--muted-foreground))]" /><div className="mt-3 text-sm font-semibold">No dataset profile yet</div><p className="mt-1 max-w-xs text-xs text-[hsl(var(--muted-foreground))]">Upload a CSV to inspect its schema, quality and consumption summary.</p></div>}
      </Panel>
    </div>
    <div className="mb-5 grid gap-5 lg:grid-cols-[1fr_1fr]">
      <Panel title="Column types" eyebrow="Schema"><div className="max-h-[250px] overflow-auto">{info.data?.columns?.length ? info.data.columns.map((col,i)=><div className="flex items-center justify-between border-b border-[hsl(var(--border))] py-2.5 text-xs last:border-0" key={`${col}-${i}`}><span className="font-medium">{col}</span><span className="mono text-[10px] text-[hsl(var(--muted-foreground))]">{info.data.data_types[col] || 'unknown'}</span></div>) : <p className="py-5 text-xs text-[hsl(var(--muted-foreground))]">Column types appear after dataset profiling.</p>}</div></Panel>
      <Panel title="Missing values & summary" eyebrow="Quality checks"><div className="mb-4"><div className="mb-2 flex items-center justify-between text-xs"><span className="font-medium">Missing values by field</span><span className="text-[10px] text-[hsl(var(--muted-foreground))]">{missing.reduce((total,[,value])=>total+value,0).toLocaleString()} total</span></div>{missing.length ? <div className="max-h-[110px] overflow-auto">{missing.map(([name,value])=><div key={name} className="flex justify-between border-t border-[hsl(var(--border))] py-2 text-[11px]"><span>{name}</span><span className="mono">{value}</span></div>)}</div> : <div className="text-xs text-[hsl(var(--muted-foreground))]">No missing-value profile available.</div>}</div><div className="border-t border-[hsl(var(--border))] pt-3"><div className="mb-2 text-xs font-medium">Numeric summary</div>{summary.length ? <div className="grid grid-cols-2 gap-2">{summary.map(([name,value])=><div key={name} className="flex justify-between gap-2 rounded-md bg-[hsl(var(--muted)/.55)] px-2.5 py-2 text-[10px]"><span className="truncate">{name}</span><span className="mono">{Number(value).toLocaleString(undefined,{maximumFractionDigits:2})}</span></div>)}</div> : <div className="text-xs text-[hsl(var(--muted-foreground))]">Numeric summary appears when available.</div>}</div></Panel>
    </div>
    <Panel title="Record preview" eyebrow={`First ${preview.data?.rows?.length ?? 0} rows`} action={<span className="mono text-[10px] text-[hsl(var(--muted-foreground))]">{preview.data?.total_rows?.toLocaleString() ?? '—'} total records</span>}>
      {preview.isLoading ? <LoadingBlock rows={4} /> : preview.data?.columns?.length ? <div className="overflow-x-auto"><table className="w-full min-w-[560px] border-collapse text-left text-xs"><thead><tr>{preview.data.columns.map((col,i)=><th key={`${col}-${i}`} className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted)/.45)] px-3 py-2.5 font-semibold">{col}</th>)}</tr></thead><tbody>{preview.data.rows.map((row,i)=><tr key={i} className="hover:bg-[hsl(var(--muted)/.35)]">{preview.data!.columns.map((col,j)=><td key={`${i}-${j}`} className="max-w-[230px] truncate border-b border-[hsl(var(--border))] px-3 py-2.5 mono text-[10px]">{row[col] ?? '—'}</td>)}</tr>)}</tbody></table></div> : <div className="py-8 text-center text-xs text-[hsl(var(--muted-foreground))]">No preview available. Upload a dataset to inspect its records.</div>}
    </Panel>
  </div>;
}
