// pace-tutor 사이드카(:8008) HTTP 클라이언트.
// Tauri 로 감쌀 때도 동일 — UI 는 사이드카 API 만 호출한다.

const BASE = "http://127.0.0.1:8008";

export interface Concept {
  id: string;
  name: string;
  prereqs: string[];
  difficulty: number;
  grade: string;
}

export interface Band {
  key: string;
  label: string;
}

export async function connect(): Promise<boolean> {
  try {
    const r = await fetch(`${BASE}/v1/connect`);
    return r.ok;
  } catch {
    return false;
  }
}

export async function getBands(): Promise<Band[]> {
  const r = await fetch(`${BASE}/v1/bands`);
  return (await r.json()).bands;
}

export async function ingestTranscript(transcript: string): Promise<{ graph_id: string; concepts: Concept[] }> {
  const r = await fetch(`${BASE}/v1/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transcript }),
  });
  if (!r.ok) throw new Error(`ingest 실패: ${r.status} ${await r.text()}`);
  return r.json();
}

export async function ingestConcepts(
  concepts: string[],
  edges: [string, string][],
): Promise<{ graph_id: string; concepts: Concept[] }> {
  const r = await fetch(`${BASE}/v1/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ concepts, edges }),
  });
  if (!r.ok) throw new Error(`ingest 실패: ${r.status} ${await r.text()}`);
  return r.json();
}

export interface RecResult {
  next: { id: string; name: string; mastery: number };
  ranking: { id: string; name: string; score: number; mastery: number; readiness: number; remediation: number }[];
}

export async function recommend(
  graph_id: string,
  responses: Record<string, number[]>,
  band: string | null,
): Promise<RecResult> {
  const r = await fetch(`${BASE}/v1/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ graph_id, responses, band, top_k: 5 }),
  });
  if (!r.ok) throw new Error(`recommend 실패: ${r.status}`);
  return r.json();
}

export async function getPath(
  graph_id: string,
  target: string,
  responses: Record<string, number[]>,
  band: string | null,
): Promise<{ target: string; path: string[] }> {
  const r = await fetch(`${BASE}/v1/path`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ graph_id, target, responses, band }),
  });
  if (!r.ok) throw new Error(`path 실패: ${r.status}`);
  return r.json();
}
