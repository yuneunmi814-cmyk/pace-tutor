# 선수개념 역추적 + 수준진단 — 구현 청사진 (reference)

> 목표: 학습자가 **어디서 막혔는지** 개념별로 진단(mastery estimation)하고,
> 부족한 **선수개념(prerequisite)을 거슬러 올라가** "세상의 진도"가 아니라
> "이 학생은 아주 기본부터 다시" 시작하는 학습 경로를 자동으로 만든다.
>
> 이 문서는 **청사진**이다. 구현은 아직 하지 않는다.

---

## 0. 한 줄 결론

이 앱의 진짜 어려운 부분은 **딥러닝/LLM이 아니라 두 개의 검증된 알고리즘**으로 풀린다:

1. **개념별 숙달도 추정** = **Bayesian Knowledge Tracing (BKT)** — `pyBKT`의 `Roster` API
2. **선수개념 역추적 / "기본부터" 추천** = **ALOSI adaptive-engine의 Readiness 수식 (substrategy P)** — 단 6줄의 numpy

LLM(Ollama)은 진단을 하지 않는다. LLM은 **(a) 자막을 개념 단위로 쪼개고 (b) 진단 결과를 사람이 읽는 학습가이드 문장으로 풀어주는** 역할만 한다. 진단의 신뢰성은 BKT가 책임진다.

---

## 1. 레퍼런스 선정 (왜 이걸 골랐나)

| 후보 | 별점/상태 | 라이선스 | 채택? | 이유 |
|---|---|---|---|---|
| **CAHLR/pyBKT** | ⭐260, 2026-03 업데이트(v1.4.2), 활발 | **MIT** | ✅ **진단 엔진** | BKT의 사실상 표준 구현. `Roster` API가 "학생별·개념별 실시간 숙달확률"을 정확히 제공. 과거 이력 저장 없이 latent state만 들고 감 → 데스크톱 앱에 딱. |
| **harvard-vpal/alosi + adaptive-engine** | Harvard/Microsoft/edX 공동, 검증된 프레임워크 | (repo 라이선스 확인 필요, 코드 참고용) | ✅ **역추적 수식만 발췌** | 선수개념 행렬(prereqs)을 이용한 추천 수식이 핵심. 단, 통째로 쓰기엔 Django 결합이 무거움 → **순수 numpy 함수 4개만 복붙**. |
| oseducation/knowledge-graph | 콘텐츠 큐레이션 앱 | - | ❌ | 알고리즘이 아니라 "정리된 지식 콘텐츠" 프로젝트. 우리에게 필요한 역추적 로직이 없음. |
| ALOSI 전체 스택(bridge-adaptivity 등) | 웹/LTI/edX 통합용 | - | ❌ 불필요 | MOOC·LTI·다중사용자 웹 인프라. 우리는 1인 데스크톱이라 전부 군더더기. |

**결정적 판단**: ALOSI 엔진을 **서버 앱으로 쓰지 않는다**. 그 안의 `alosi/engine.py` **순수 함수들**(`recommendation_score`, `recommendation_score_P/R/D/C`, `calculate_mastery_update`, `odds`)만 가져온다. 이건 numpy만 의존하므로 데스크톱 사이드카에 그대로 박을 수 있다.

---

## 2. 매핑표 — 레퍼런스 ↔ 우리 앱

| 레퍼런스 개념 (ALOSI/pyBKT) | 우리 도메인 용어 | 우리 앱에서의 대응 |
|---|---|---|
| Knowledge Component (KC / LO) | **개념 노드** (예: "분수의 덧셈") | 자막에서 추출 + 교육과정 사전에서 매핑 |
| Activity / Item | **문항 / 학습조각** (퀴즈, 영상 구간) | 영상 타임스탬프 구간 또는 진단 퀴즈 1문항 |
| `prereqs` (KxK 행렬) | **선수개념 그래프 (DAG)** | "분수 덧셈" ← "약분" ← "최대공약수" … 의 의존 행렬 |
| `Mastery` / `L` (mastery log-odds) | **개념별 숙달확률** | pyBKT `Roster.get_mastery_prob()` 결과 |
| `guess` / `slip` / `transit` | BKT 문항 파라미터 | 처음엔 합리적 기본값(아래 §6), 데이터 쌓이면 재추정 |
| `L_star` (숙달 임계 log-odds) | **"이 개념은 안다" 기준선** | 기본 2.2 (≈ 확률 0.9). §6 참고 |
| `r_star` (선수개념 관용 임계) | **"선수개념 조금 부족해도 봐주는" 정도** | 기본 0.0 (엄격). 어린 학습자엔 0으로 시작 권장 |
| `recommendation_score_P` (Readiness) | **🔑 선수개념 역추적의 핵심** | 선수개념이 안 잡힌 활동에 음수 점수 → 추천 안 됨 |
| `recommendation_score_R` (Remediation) | **약점 보충 수요** | 아직 모르는 개념일수록 높은 점수 |
| `recommend()` → `argmax(scores)` | **다음에 뭘 학습할지** | "지금 이 학생에게 맞는 단 하나의 다음 단계" |

---

## 3. 🔑 핵심 — 선수개념 역추적 수식 (그대로 복붙)

레퍼런스 실제 파일: `alosi/alosi/engine.py` 의 `recommendation_score_P`.

```python
# 출처: harvard-vpal/alosi  alosi/engine.py:413  (substrategy P = Readiness)
def recommendation_score_P(relevance, L, prereqs, r_star, L_star):
    m_w = prereqs                                   # KxK 선수개념 행렬
    fillna(m_w)
    m_r = np.dot(np.minimum(L - L_star, 0), m_w)    # ① 각 개념의 "선수개념 부족분" 누적
    P = np.dot(relevance, np.minimum((m_r + r_star), 0))  # ② 준비 안 된 활동에 음수 페널티
    return P
```

### 이 6줄이 "기본부터"를 만드는 원리 (반드시 이해할 것)

- `L` = 학습자의 개념별 숙달 **log-odds** 벡터. `L_star` = 숙달 기준선.
- `np.minimum(L - L_star, 0)` → **이미 통달한 개념은 0**, **아직 부족한 개념만 음수**(부족할수록 큰 음수). 즉 "결손 벡터".
- `np.dot(결손벡터, prereqs)` → 각 개념 j에 대해, **그 개념의 선수개념들이 얼마나 부족한지**를 합산(`m_r`).
- `np.minimum(m_r + r_star, 0)` → 선수개념이 관용 임계(`r_star`)를 넘게 부족하면 **음수**. → 이 활동은 "아직 준비 안 됨".
- 최종 `recommendation_score`에서 P에 큰 양의 가중치 `W_p`를 곱해 더함 → **선수개념이 안 잡힌 어려운 활동은 점수가 깎여 추천에서 밀려난다.**

동시에 **substrategy R**(`recommendation_score_R`)은 *아직 모르는 개념*에 높은 점수를 준다:

```python
# alosi/engine.py:434  (substrategy R = Remediation/demand)
def recommendation_score_R(relevance, L, L_star):
    return np.dot(relevance, np.maximum((L_star - L), 0))  # 모를수록 ↑
```

> **두 힘의 합성 결과 = "이 학생은 아주 기본부터"**
> R은 "모르는 걸 가르쳐라"라고 당기고, P는 "선수개념 안 된 건 아직 하지 마라"라고 막는다.
> 두 힘이 만나는 지점 = **선수개념은 이미 갖춰졌으면서 + 본인은 아직 모르는, 가장 깊은 기초 개념**.
> 중3 학생의 막힌 단원이 아니라, 그 학생이 *지금 당장 배울 수 있는* 초등 개념이 1순위로 떠오른다. 정확히 사용자가 원한 동작.

### 최종 점수 합성 (그대로 복붙)

```python
# alosi/engine.py:359  recommendation_score()
P = recommendation_score_P(relevance, L, prereqs, r_star, L_star)
R = recommendation_score_R(relevance, L, L_star)
C = recommendation_score_C(relevance, last_attempted_relevance)  # 직전 학습과의 연속성
D = recommendation_score_D(relevance, L, difficulty)             # 난이도 적정성
subscores = np.array([P, R, C, D])
weights   = np.array([W_p, W_r, W_d, W_c])
scores    = np.dot(weights, subscores)   # 활동별 종합점수
# 다음 학습 = np.argmax(scores)
```

ALOSI 운영 기본 가중치(adaptive-engine `engines.py:64`): **`W_p=2.0`(readiness)**, 나머지(W_r/W_d/W_c)는 우리 목적에 맞게 §6에서 조정.

---

## 4. 숙달도 추정 — pyBKT Roster (그대로 복붙)

레퍼런스 실제 파일: `pyBKT/README.md:239` (Roster 섹션).

```python
from pyBKT.models import Model, Roster
from pyBKT.models.Roster import StateType
import numpy as np

# 1) 모델 준비 (데이터 있으면 fit, 없으면 합리적 기본 파라미터로 시작 — §6)
model = Model(seed=42)
# model.fit(data_path='responses.csv')   # 데이터가 쌓이면

# 2) 학습자 + 개념(skill)별 상태 추적
roster = Roster(students=['학생A'], skills='분수의 덧셈', model=model)

# 3) 진단 퀴즈 응답을 넣을 때마다 상태 업데이트 (1=정답, 0=오답)
roster.update_state('분수의 덧셈', '학생A', np.array([1, 0, 1, 1]))

# 4) 현재 숙달확률 조회
p = roster.get_mastery_prob('분수의 덧셈', '학생A')   # → 0.0~1.0

# 5) 통달 여부 판정
if roster.get_state_type('분수의 덧셈', '학생A') == StateType.MASTERED:
    ...
```

**우리 앱에서의 흐름**: 진단 퀴즈 응답 → `roster.update_state(...)` → 개념별 `get_mastery_prob` 벡터 확보 → 이 벡터를 `L = np.log(odds(mastery))`로 변환해 §3의 `recommendation_score`에 투입.

확률 → log-odds 변환은 alosi의 `odds()`를 그대로 사용:

```python
# alosi/engine.py:484
EPSILON = 1e-10
def odds(p, epsilon=EPSILON):
    p = np.minimum(np.maximum(p, epsilon), 1 - epsilon)
    return p / (1.0 - p)

L = np.log(odds(mastery_vector))   # recommendation_score에 넣을 형태
```

---

## 5. 결정적 차이 — 우리는 ALOSI보다 **훨씬 단순**해진다

| 항목 | ALOSI (레퍼런스) | 우리 앱 | 그래서 |
|---|---|---|---|
| 사용자 수 | 다중 학습자 웹/LTI | **1인(또는 소수) 데스크톱** | 인증·DB·서버 전부 **삭제** |
| 저장소 | PostgreSQL + Django ORM | **SQLite 파일 1개** (또는 JSON) | 마이그레이션·모델 클래스 불필요 |
| 행렬 차원 | 수백~수천 KC | **수십~수백 개념** | 전부 메모리 numpy로 충분, 최적화 불필요 |
| 통신 | REST API + LTI 연동 | **로컬 함수 호출 / 사이드카 IPC** | 네트워크 계층 **삭제** |
| 파라미터 재추정 | 대규모 로그로 `train()` | 초기엔 **기본 파라미터 고정**, 나중에 pyBKT `fit()` | 콜드스타트 가능 (§6) |
| 콘텐츠 | 외부 활동 라이브러리 | **영상 자막에서 LLM이 개념·문항 생성** | 우리만의 추가 부분 |

**우리가 ALOSI에 *추가*해야 하는 유일한 무거운 부분** = "영상 → 개념·선수관계·진단문항"을 만드는 파이프라인. ALOSI는 콘텐츠가 이미 있다고 가정한다. 우리는 그걸 LLM으로 만든다 (§7).

---

## 6. 함정(gotcha) — 레퍼런스 소스에서 직접 확인한 것들

1. **`prereqs` 행렬 방향성**: 예제(`example_engine.py:65`)에서 `[[0,1],[0,0]]` = "개념0이 개념1의 선수개념". 즉 **행=선수개념, 열=후속개념**. `np.dot(결손, prereqs)`가 열(후속개념) 기준으로 누적되도록 방향을 맞춰야 한다. 뒤집으면 역추적이 거꾸로 동작한다. **DAG여야 함**(순환 금지) — 순환이면 "기본부터" 경로가 무한루프.

2. **콜드스타트**: 데이터 0건이면 `model.fit()` 불가. pyBKT는 `coef_`로 파라미터를 직접 주입 가능. 초기 기본값(문헌 통용):
   - `guess ≈ 0.1~0.3`, `slip ≈ 0.05~0.1`, `transit(prior_learn) ≈ 0.1`, `prior(mastery) ≈ 0.1`
   - `L_star = 2.2` (≈ 숙달확률 0.9), `r_star = 0.0`(어린 학습자엔 선수개념 엄격하게).
   데이터가 쌓이면 `fit()`/`estimate()`로 교체.

3. **degeneracy 제거**: `estimate()`(engine.py:701)는 `guess≥0.5` 또는 `guess+slip≥1`을 NaN 처리한다. 직접 파라미터를 줄 때도 이 범위를 넘기지 말 것 — BKT가 "틀려야 아는 것" 같은 역설적 동작을 한다.

4. **log-odds vs 확률 혼동**: `recommendation_score`는 `learner_mastery`를 **확률**로 받아 내부에서 `L=np.log(odds(...))`로 변환한다(engine.py:390). 그런데 `recommendation_score_P`에 직접 넣을 땐 이미 `L`(log-odds). **어느 함수가 무엇을 받는지 시그니처를 반드시 확인**하고 이중변환하지 말 것. pyBKT는 **확률**을 주므로, 최상위 `recommendation_score()`에 그대로 넣는 게 안전.

5. **`recommendation_score_C`(연속성)**: 직전 학습 활동이 없으면 0 벡터 반환(engine.py:461). 첫 학습 세션에선 C가 0이라 자연히 무시됨 — 정상.

6. **pyBKT 빌드 의존성**: C/C++ 확장이 있어 일부 환경에서 설치가 무겁다. 데스크톱 번들 시 사이드카(아래 §8) PyInstaller 빌드에서 네이티브 의존성 누락 주의. (가벼운 대안이 필요하면 BKT 업데이트 식 `calculate_mastery_update`(engine.py:338)만 직접 구현해도 동일 — pyBKT 없이도 가능.)

---

## 7. 우리가 새로 만드는 부분 — 영상 → 개념·선수관계·진단문항

ALOSI에 없는, **LLM이 담당**하는 콘텐츠 생성 파이프라인. 진단(BKT)이 아니라 콘텐츠 준비만 한다.

```
영상파일
  └─(Whisper STT)→ 자막+타임스탬프
       └─(LLM: Ollama)→ ① 개념 노드 추출 ("이 강의가 다루는 개념 N개")
                         ② 각 개념의 선수개념 매핑 → prereqs 행렬 (DAG)
                         ③ 개념별 진단 문항 2~3개 생성
```

- **선수개념 그래프의 신뢰성**: LLM 단독 생성은 환각 위험. 권장 = **교육과정 표준 사전을 백본으로** 두고(예: 한국 수학과 교육과정 성취기준 코드, 또는 Khan Academy 개념맵) LLM은 "자막 개념 ↔ 표준개념 매핑"만 하게 한다. 0→1은 LLM, 검증은 사전.
- **STT**: 사용자는 이미 Meetily(Whisper 계열)·로컬 AI 세팅 경험 보유 → 동일 로컬 Whisper 재사용 가능.
- 이 부분은 **별도 refbuild 청사진**으로 깊게 파는 걸 권장(이 문서는 진단/역추적에 집중).

---

## 8. 스택 추천 (요청하신 부분)

**추천: Tauri (React/TS UI) + Python 사이드카 (진단 엔진 + STT + Ollama 호출)**

이유:
- 진단의 핵심 라이브러리(pyBKT, numpy, Whisper)가 전부 **Python**이다 → Python을 빼면 핵심을 못 만든다.
- UI는 가볍게, 로컬 파일/Ollama 친화 → **Tauri**가 Electron보다 가볍고, 사용자가 이미 쓰는 **Meetily가 Tauri 계열**이라 학습비용↓.
- 라이트모드 선호 → Tauri+React에서 테마 제어 쉬움.

```
┌─────────────────────────────┐
│ Tauri Shell (Rust)          │
│  └ React + TS UI (라이트테마)│  ← 진단결과·학습가이드·진도 시각화
└──────────────┬──────────────┘
               │ IPC (stdin/stdout JSON 또는 localhost)
┌──────────────▼──────────────┐
│ Python 사이드카 (PyInstaller)│
│  • pyBKT Roster (숙달도)     │
│  • alosi engine 함수 4개     │  ← §3,§4 복붙
│  • Whisper STT               │
│  • Ollama 호출 (가이드 생성) │
│  • SQLite (학습자 상태 저장) │
└─────────────────────────────┘
```

- **차선책**: Electron + Python 사이드카 (영상/미디어 라이브러리 생태계가 더 크지만 무겁다).
- ⚠️ **Tauri Python 사이드카 번들링은 그 자체로 함정이 많다** → 구현 착수 시 `/refbuild Tauri Python sidecar` 로 별도 청사진을 먼저 뽑는 것을 강력 권장.

---

## 9. 실행 순서 체크리스트

- [ ] **스택 확정**: Tauri + Python 사이드카로 갈지 결정 (§8)
- [ ] Python 사이드카 뼈대: `pip install pyBKT numpy`, FastAPI 또는 stdin/stdout JSON IPC
- [ ] `alosi/engine.py`에서 **순수 함수만** 복사: `odds`, `fillna`, `calculate_relevance`, `calculate_mastery_update`, `recommendation_score`, `recommendation_score_P/R/C/D` (Django 의존 코드는 절대 가져오지 않음)
- [ ] 개념 도메인 모델 정의: `Concept(id, name, 표준코드)`, `prereqs` KxK numpy 행렬 (DAG 검증 포함 — 순환 탐지)
- [ ] pyBKT `Roster`로 개념별 숙달확률 추적 + SQLite 영속화 (§4)
- [ ] 콜드스타트 기본 파라미터 주입 (§6-2), `L_star=2.2`, `r_star=0.0`
- [ ] `recommend()` 연결: mastery 벡터 → `recommendation_score` → `argmax` → "다음 학습 1개" 반환
- [ ] **검증 시나리오**: 중3 학생이 "이차방정식" 막힘 → 진단 → 추천이 "분수/약분/등식" 같은 *기초*로 내려가는지 직접 확인 (이게 통과 못 하면 prereqs 방향(§6-1) 또는 W_p 가중치 의심)
- [ ] (별도) 영상→개념·문항 생성 파이프라인은 `/refbuild` 추가 청사진으로 분리 (§7)
- [ ] (별도) Tauri Python 사이드카 번들링은 `/refbuild` 추가 청사진으로 분리 (§8)

---

## 10. 참고한 레퍼런스 실제 파일

- `harvard-vpal/alosi` → `alosi/engine.py`
  - `recommendation_score` (L359), `recommendation_score_P` (L413, **역추적 핵심**), `_R`(L434), `_C`(L448), `_D`(L467)
  - `calculate_mastery_update` (L338), `odds` (L484), `calculate_relevance` (L509), `estimate` (L579)
  - `examples/example_engine.py` (prereqs 행렬 형식·사용 예, L65)
- `harvard-vpal/adaptive-engine` → `app/engine/engines.py`
  - 운영 가중치 `W_p=2.0` (L64), `get_prereqs`/`get_recommend_params` 실제 배선 (L190, L316)
- `CAHLR/pyBKT` → `README.md` Roster 섹션(L239~), `Model`/`Roster`/`StateType` API (MIT, v1.4.2 / 2026-03)
