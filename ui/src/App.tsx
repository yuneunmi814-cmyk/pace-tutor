import { useEffect, useMemo, useState } from "react";
import {
  connect, getBands, ingestTranscript, ingestConcepts, recommend, getPath,
  type Concept, type Band, type RecResult,
} from "./api";
import { STR, SAMPLES, type Locale } from "./i18n";
import "./App.css";

export default function App() {
  const [loc, setLoc] = useState<Locale>("en");
  const t = STR[loc];

  const [online, setOnline] = useState<boolean | null>(null);
  const [bands, setBands] = useState<Band[]>([]);
  const [band, setBand] = useState<string>("secondary");

  const [transcript, setTranscript] = useState<string>(SAMPLES.en.transcript);
  const [graphId, setGraphId] = useState<string | null>(null);
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [known, setKnown] = useState<Set<string>>(new Set());
  const [target, setTarget] = useState<string | null>(null);

  const [rec, setRec] = useState<RecResult | null>(null);
  const [path, setPath] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // 번들된 사이드카는 첫 실행 시 부팅에 몇 초 걸린다 → 연결될 때까지 폴링/재시도
  // (청사진 §5-7: 사이드카 ready 대기). null=시작중, true=연결, false=실패.
  async function waitForBackend(tries = 30) {
    setOnline(null);
    for (let i = 0; i < tries; i++) {
      if (await connect()) {
        setOnline(true);
        getBands().then(setBands).catch(() => {});
        return;
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
    setOnline(false);
  }

  useEffect(() => { waitForBackend(); }, []);

  // 로케일 전환 시, 손대지 않은 기본 샘플이면 해당 언어 샘플로 교체
  function switchLocale(next: Locale) {
    setTranscript((cur) =>
      cur.trim() === SAMPLES.en.transcript.trim() || cur.trim() === SAMPLES.ko.transcript.trim()
        ? SAMPLES[next].transcript : cur,
    );
    setLoc(next);
  }

  const byId = useMemo(() => Object.fromEntries(concepts.map((c) => [c.id, c])), [concepts]);
  const sorted = useMemo(() => [...concepts].sort((a, b) => a.difficulty - b.difficulty), [concepts]);

  async function doIngest(kind: "transcript" | "sample") {
    setBusy(true); setErr(null); setRec(null); setPath([]); setKnown(new Set()); setTarget(null);
    try {
      const res = kind === "transcript"
        ? await ingestTranscript(transcript)
        : await ingestConcepts([...SAMPLES[loc].concepts], SAMPLES[loc].edges.map((e) => [...e] as [string, string]));
      setGraphId(res.graph_id);
      setConcepts(res.concepts);
      const hardest = [...res.concepts].sort((a, b) => b.difficulty - a.difficulty)[0];
      setTarget(hardest?.id ?? null);
    } catch (e: any) {
      setErr(e.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  function buildResponses(): Record<string, number[]> {
    const r: Record<string, number[]> = {};
    known.forEach((id) => { r[id] = [1, 1, 1, 1]; });
    if (target) r[target] = [0, 0, 0];
    return r;
  }

  async function makePlan() {
    if (!graphId || !target) return;
    setBusy(true); setErr(null);
    try {
      const responses = buildResponses();
      const [rc, pa] = await Promise.all([
        recommend(graphId, responses, band),
        getPath(graphId, target, responses, band),
      ]);
      setRec(rc); setPath(pa.path);
    } catch (e: any) {
      setErr(e.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  function toggleKnown(id: string) {
    setKnown((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  }

  return (
    <div className="app">
      <header>
        <div className="topbar">
          <h1>pace-tutor</h1>
          <div className="lang">
            <button className={loc === "en" ? "on" : ""} onClick={() => switchLocale("en")}>EN</button>
            <button className={loc === "ko" ? "on" : ""} onClick={() => switchLocale("ko")}>한국어</button>
          </div>
        </div>
        <p className="tag">{t.tagline}</p>
        <span className={`status ${online === true ? "ok" : online === false ? "down" : "wait"}`}>
          {online === null ? t.connecting : online ? t.connected : t.down}
          {online === false && (
            <button className="retry" onClick={() => waitForBackend()}>{t.retry}</button>
          )}
        </span>
      </header>

      {err && <div className="err">{err}</div>}

      <section className="card">
        <h2>{t.s1}</h2>
        <textarea value={transcript} onChange={(e) => setTranscript(e.target.value)} rows={6} />
        <div className="row">
          <button disabled={busy} onClick={() => doIngest("transcript")}>{t.ingestLLM}</button>
          <button className="ghost" disabled={busy} onClick={() => doIngest("sample")}>{t.ingestSample}</button>
        </div>
      </section>

      {concepts.length > 0 && (
        <section className="card">
          <h2>{t.s2}</h2>
          <div className="row">
            <label>{t.level}&nbsp;</label>
            <select value={band} onChange={(e) => setBand(e.target.value)}>
              {bands.map((b) => <option key={b.key} value={b.key}>{t.bands[b.key] ?? b.label}</option>)}
            </select>
          </div>
          <p className="hint">{t.s2hint}</p>
          <div className="chips">
            {sorted.map((c) => {
              const isTarget = target === c.id;
              const isKnown = known.has(c.id);
              return (
                <span
                  key={c.id}
                  className={`chip ${isTarget ? "target" : ""} ${isKnown ? "known" : ""}`}
                  onClick={() => toggleKnown(c.id)}
                >
                  {isKnown ? "✓ " : ""}{c.name}
                  <button className="tbtn" onClick={(e) => { e.stopPropagation(); setTarget(c.id); }}>{t.stuck}</button>
                </span>
              );
            })}
          </div>
          <button disabled={busy || !target} onClick={makePlan}>{t.makePlan}</button>
        </section>
      )}

      {rec && (
        <section className="card result">
          <h2>{t.s3}</h2>
          <div className="next">
            <span className="nlabel">{t.startHere}</span>
            <span className="nname">{rec.next.name}</span>
          </div>
          <div className="stepper">
            {path.map((name, i) => (
              <span key={i} className="step">
                <span className="snum">{i + 1}</span>{name}
                {i < path.length - 1 && <span className="arrow">→</span>}
              </span>
            ))}
          </div>
          <p className="hint">{t.pathHint(target ? byId[target]?.name ?? "" : "")}</p>
        </section>
      )}
    </div>
  );
}
