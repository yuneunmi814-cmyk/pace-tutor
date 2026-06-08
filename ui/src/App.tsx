import { useEffect, useMemo, useState } from "react";
import {
  connect, getBands, ingestTranscript, ingestConcepts, recommend, getPath, getQuestions,
  type Concept, type Band, type RecResult, type Question,
} from "./api";
import { STR, SAMPLES, type Locale } from "./i18n";
import "./App.css";

// 등급형 자기평가 — 답이 틀리기 쉬운 로컬LLM 자동퀴즈 대신 신뢰할 수 있는 진단.
// 각 등급이 BKT 엔진에 줄 응답(정답1/오답0 시퀀스)으로 매핑된다.
type Rating = "confident" | "unsure" | "none";
const CYCLE: (Rating | "untested")[] = ["untested", "none", "unsure", "confident"];
const RESP: Record<Rating, number[]> = {
  confident: [1, 1, 1, 1],
  unsure: [1, 0],
  none: [0, 0, 0],
};
const MARK: Record<Rating | "untested", string> = {
  untested: "", none: "✗ ", unsure: "~ ", confident: "✓ ",
};

export default function App() {
  const [loc, setLoc] = useState<Locale>("en");
  const t = STR[loc];

  const [online, setOnline] = useState<boolean | null>(null);
  const [bands, setBands] = useState<Band[]>([]);
  const [band, setBand] = useState<string>("secondary");

  const [transcript, setTranscript] = useState<string>(SAMPLES.en.transcript);
  const [graphId, setGraphId] = useState<string | null>(null);
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [rating, setRating] = useState<Record<string, Rating>>({});
  const [goal, setGoal] = useState<string | null>(null);

  // 자동채점 퀴즈(큐레이션 문항). quizzes: 개념별 문항. activeQuiz: 모달 대상.
  const [quizzes, setQuizzes] = useState<Record<string, Question[]>>({});
  const [activeQuiz, setActiveQuiz] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});

  const [rec, setRec] = useState<RecResult | null>(null);
  const [path, setPath] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // 번들된 사이드카는 첫 실행 시 부팅에 몇 초 걸린다 → 연결될 때까지 폴링/재시도.
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
    setBusy(true); setErr(null); setRec(null); setPath([]); setRating({}); setGoal(null); setQuizzes({});
    try {
      const res = kind === "transcript"
        ? await ingestTranscript(transcript)
        : await ingestConcepts([...SAMPLES[loc].concepts], SAMPLES[loc].edges.map((e) => [...e] as [string, string]));
      setGraphId(res.graph_id);
      setConcepts(res.concepts);
      const hardest = [...res.concepts].sort((a, b) => b.difficulty - a.difficulty)[0];
      setGoal(hardest?.id ?? null);   // 기본 목표 = 가장 상위(어려운) 개념
      // 큐레이션 문항 프리페치(LLM 아님 — 즉시): 문항 있는 개념만 퀴즈 버튼 노출
      const qmap: Record<string, Question[]> = {};
      await Promise.all(res.concepts.map(async (c) => {
        const qs = await getQuestions(c.name);
        if (qs.length) qmap[c.id] = qs;
      }));
      setQuizzes(qmap);
    } catch (e: any) {
      setErr(e.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  function cycleRating(id: string) {
    setRating((prev) => {
      const cur = prev[id] ?? "untested";
      const next = CYCLE[(CYCLE.indexOf(cur) + 1) % CYCLE.length];
      const n = { ...prev };
      if (next === "untested") delete n[id]; else n[id] = next;
      return n;
    });
  }

  function openQuiz(id: string) { setActiveQuiz(id); setAnswers({}); }

  function gradeQuiz() {
    if (!activeQuiz) return;
    const qs = quizzes[activeQuiz] ?? [];
    const correct = qs.reduce((n, q, i) => n + (answers[i] === q.answer_index ? 1 : 0), 0);
    const rt: Rating = correct === qs.length ? "confident" : correct === 0 ? "none" : "unsure";
    setRating((prev) => ({ ...prev, [activeQuiz]: rt }));   // 객관 채점 → 등급
    setActiveQuiz(null);
  }

  function buildResponses(): Record<string, number[]> {
    const r: Record<string, number[]> = {};
    for (const [id, rt] of Object.entries(rating)) r[id] = RESP[rt];
    return r;
  }

  async function makePlan() {
    if (!graphId || !goal) return;
    setBusy(true); setErr(null);
    try {
      const responses = buildResponses();
      const [rc, pa] = await Promise.all([
        recommend(graphId, responses, band),
        getPath(graphId, goal, responses, band),
      ]);
      setRec(rc); setPath(pa.path);
    } catch (e: any) {
      setErr(e.message ?? String(e));
    } finally {
      setBusy(false);
    }
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
            <label>&nbsp;&nbsp;{t.goal}&nbsp;</label>
            <select value={goal ?? ""} onChange={(e) => setGoal(e.target.value)}>
              {sorted.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <p className="hint">{t.s2hint}</p>
          <div className="legend">
            <span className="chip confident">✓ {t.r_confident}</span>
            <span className="chip unsure">~ {t.r_unsure}</span>
            <span className="chip none">✗ {t.r_none}</span>
          </div>
          <div className="chips">
            {sorted.map((c) => {
              const rt = rating[c.id] ?? "untested";
              return (
                <span
                  key={c.id}
                  className={`chip ${rt}`}
                  onClick={() => cycleRating(c.id)}
                  title={t.s2hint}
                >
                  {MARK[rt]}{c.name}
                  {goal === c.id && <span className="goalflag">🎯</span>}
                  {quizzes[c.id] && (
                    <button className="tbtn" onClick={(e) => { e.stopPropagation(); openQuiz(c.id); }}>
                      📝 {t.quiz}
                    </button>
                  )}
                </span>
              );
            })}
          </div>
          <button disabled={busy || !goal} onClick={makePlan}>{t.makePlan}</button>
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
          <p className="hint">{t.pathHint(goal ? byId[goal]?.name ?? "" : "")}</p>
        </section>
      )}

      {activeQuiz && (
        <div className="overlay" onClick={() => setActiveQuiz(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>{t.quizTitle(byId[activeQuiz]?.name ?? "")}</h3>
            {(quizzes[activeQuiz] ?? []).map((q, qi) => (
              <div key={qi} className="qitem">
                <p className="qstem">{qi + 1}. {q.stem}</p>
                <div className="qchoices">
                  {q.choices.map((ch, ci) => (
                    <label key={ci} className={`qchoice ${answers[qi] === ci ? "sel" : ""}`}>
                      <input type="radio" name={`q${qi}`} checked={answers[qi] === ci}
                        onChange={() => setAnswers((p) => ({ ...p, [qi]: ci }))} />
                      {ch}
                    </label>
                  ))}
                </div>
              </div>
            ))}
            <div className="row">
              <button onClick={gradeQuiz}>{t.quizSubmit}</button>
              <button className="ghost" onClick={() => setActiveQuiz(null)}>{t.quizClose}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
