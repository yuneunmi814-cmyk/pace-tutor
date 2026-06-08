// 영문 우선(English-first) i18n — 전 세계 사용자 대상. 한국어는 토글.
export type Locale = "en" | "ko";

export const STR = {
  en: {
    tagline: "Learn at your own pace, not the world's — start from the basics.",
    connecting: "Starting backend… (first launch may take ~15s)",
    connected: "● Backend connected",
    down: "● Backend not responding",
    retry: "Retry",
    s1: "1. Add lecture content",
    ingestLLM: "Build concept graph (LLM)",
    ingestSample: "Try a sample instantly (no LLM)",
    s2: "2. Your level & what you know",
    level: "Level",
    goal: "Goal",
    s2hint: "Tap each concept to set how well you know it (Know it / Unsure / No idea).",
    r_confident: "Know it",
    r_unsure: "Unsure",
    r_none: "No idea",
    quiz: "Quiz",
    quizTitle: (n: string) => `Quick check — ${n}`,
    quizSubmit: "Grade me",
    quizResult: (c: number, t: number) => `${c} / ${t} correct`,
    quizClose: "Close",
    makePlan: "Build my learning path →",
    s3: "3. Your learning path",
    startHere: "Start here now",
    pathHint: (x: string) =>
      `To reach "${x}", start from the deepest basics you're ready for and build up.`,
    bands: { elementary: "Elementary", secondary: "Middle/High school", tertiary_adult: "College/Adult" } as Record<string, string>,
  },
  ko: {
    tagline: "세상의 진도 말고, 자기 속도로 — 기본부터 다시.",
    connecting: "백엔드 시작 중… (첫 실행은 ~15초 걸릴 수 있어요)",
    connected: "● 백엔드 연결됨",
    down: "● 백엔드가 응답하지 않습니다",
    retry: "다시 시도",
    s1: "1. 강의 내용 넣기",
    ingestLLM: "개념 그래프 생성 (LLM)",
    ingestSample: "샘플로 즉시 체험 (LLM 불필요)",
    s2: "2. 수준과 아는 정도",
    level: "학습 수준",
    goal: "목표",
    s2hint: "각 개념을 눌러 얼마나 아는지 표시하세요 (알아요 / 가물가물 / 몰라요).",
    r_confident: "알아요",
    r_unsure: "가물가물",
    r_none: "몰라요",
    quiz: "퀴즈",
    quizTitle: (n: string) => `간단 진단 — ${n}`,
    quizSubmit: "채점하기",
    quizResult: (c: number, t: number) => `${t}문제 중 ${c}개 정답`,
    quizClose: "닫기",
    makePlan: "내 학습경로 만들기 →",
    s3: "3. 당신을 위한 학습경로",
    startHere: "지금 바로 시작할 것",
    pathHint: (x: string) => `「${x}」에 도달하기 위해, 준비된 가장 깊은 기초부터 차근차근 올라갑니다.`,
    bands: { elementary: "초등학생", secondary: "중·고등학생", tertiary_adult: "대학생·성인" } as Record<string, string>,
  },
} as const;

// 입력 샘플(로케일별)
export const SAMPLES = {
  en: {
    transcript: `Today we'll learn about the water cycle. Water exists in three states: solid, liquid, and gas.
When the sun heats water in oceans and rivers, liquid water turns into water vapor, a gas — this is called evaporation.
As the vapor rises and cools, it turns back into tiny droplets; this process is called condensation,
and the droplets gather to form clouds. When the droplets grow heavy, they fall as rain or snow,
which is called precipitation. So to understand the water cycle, you first need to understand the changes in states of matter.`,
    concepts: ["Greatest Common Divisor", "Reducing Fractions", "Common Denominator", "Adding Fractions", "Linear Equations", "Factoring", "Quadratic Equations"],
    edges: [
      ["Greatest Common Divisor", "Reducing Fractions"], ["Greatest Common Divisor", "Common Denominator"],
      ["Reducing Fractions", "Adding Fractions"], ["Common Denominator", "Adding Fractions"],
      ["Adding Fractions", "Linear Equations"], ["Linear Equations", "Quadratic Equations"],
      ["Factoring", "Quadratic Equations"],
    ] as [string, string][],
  },
  ko: {
    transcript: `오늘은 물의 순환에 대해 배워보겠습니다. 물은 고체, 액체, 기체 세 가지 상태로 존재합니다.
태양이 바다나 강의 물을 데우면 액체인 물이 기체인 수증기로 변하는데 이것을 증발이라고 합니다.
수증기가 하늘 높이 올라가 차가워지면 다시 작은 물방울로 변합니다. 이 과정을 응결이라고 하고,
응결된 물방울이 모여 구름이 됩니다. 구름 속 물방울이 무거워지면 비나 눈이 되어 땅으로 떨어지는데,
이것을 강수라고 합니다. 따라서 물의 순환을 이해하려면 먼저 물의 상태 변화를 알아야 합니다.`,
    concepts: ["최대공약수", "약분", "통분", "분수의 덧셈", "일차방정식", "인수분해", "이차방정식"],
    edges: [
      ["최대공약수", "약분"], ["최대공약수", "통분"], ["약분", "분수의 덧셈"],
      ["통분", "분수의 덧셈"], ["분수의 덧셈", "일차방정식"],
      ["일차방정식", "이차방정식"], ["인수분해", "이차방정식"],
    ] as [string, string][],
  },
} as const;
