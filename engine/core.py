"""순수 수학 코어 — harvard-vpal/alosi  alosi/engine.py 에서 발췌.

Django/DB 의존 없이 numpy만 사용한다. 이 파일의 함수들은 ALOSI 원문을
그대로 옮긴 것이며(가독성 위해 주석 보강), 우리 앱의 진단/추천 수식의 토대다.

선수개념 역추적의 핵심: recommendation_score_P (substrategy P = Readiness).
"""

import numpy as np

# 정규화 컷오프 — 숙달 확률의 최소값 (odds 계산 시 발산 방지)
EPSILON = 1e-10


def fillna(x, value=0.0, inplace=False):
    """NaN/Inf 원소를 scalar 또는 같은 모양의 배열 값으로 치환."""
    output = x.copy() if inplace else x
    ind_to_replace = np.where(np.isnan(output) | np.isinf(output))
    if np.isscalar(value):
        output[ind_to_replace] = value
    else:
        output[ind_to_replace] = value[ind_to_replace]
    return output if not inplace else None


def odds(p, epsilon=EPSILON):
    """확률 → odds. epsilon으로 정규화해 0/1 근처 발산을 막는다."""
    p = np.minimum(np.maximum(p, epsilon), 1 - epsilon)
    return p / (1.0 - p)


def calculate_relevance(guess, slip):
    """문항-개념 관련도(relevance)를 원소별로 계산. NaN은 0으로.

    guess/slip이 NaN(=그 문항이 그 개념을 다루지 않음)이면 relevance 0 → 무관.
    """
    r = -np.log(odds(guess)) - np.log(odds(slip))
    return fillna(r, 0.0)


def _x0_mult(guess, slip):
    return slip * (1.0 + guess) / (1.0 + slip)


def _x1_0_mult(guess, slip):
    return ((1.0 + guess) / (guess * (1.0 + slip))) / _x0_mult(guess, slip)


def calculate_mastery_update(mastery, score, guess, slip, transit, epsilon=EPSILON):
    """새 점수 정보로 학습자 숙달 odds를 베이지안 업데이트.

    :param mastery: 현재 숙달 odds 벡터 (1xK)
    :param score: 0.0~1.0 사이 점수
    :param guess/slip/transit: 해당 문항의 파라미터 벡터 (1xK)
    :return: 새 숙달 odds 벡터 (1xK)
    """
    x = _x0_mult(guess, slip) * np.power(_x1_0_mult(guess, slip), score)
    new_mastery_odds = transit + (transit + 1) * (mastery * x)
    new_mastery_odds[np.where(np.isposinf(new_mastery_odds))] = odds(1.0)
    new_mastery_odds[np.where(new_mastery_odds == 0.0)] = odds(0.0)
    return new_mastery_odds


# ---------------------------------------------------------------------------
# 추천 점수 — 4개 substrategy 의 가중 평균
#   P: Readiness (선수개념 준비도)  ← 역추적의 핵심
#   R: Remediation (약점 보충 수요)
#   C: Continuity (직전 학습과의 연속성)
#   D: Difficulty (난이도 적정성)
# ---------------------------------------------------------------------------

def recommendation_score(*, guess, slip, learner_mastery, prereqs, r_star, L_star,
                         difficulty, W_p, W_r, W_d, W_c,
                         last_attempted_guess=None, last_attempted_slip=None):
    """활동별 추천 점수 벡터(Q,)를 계산. learner_mastery는 **확률**로 받는다."""
    relevance = calculate_relevance(guess, slip)
    if last_attempted_guess is None and last_attempted_slip is None:
        last_attempted_relevance = None
    else:
        last_attempted_relevance = calculate_relevance(last_attempted_guess, last_attempted_slip)
    L = np.log(odds(learner_mastery))
    difficulty = fillna(np.asarray(difficulty, dtype=float), value=0.5)

    P = recommendation_score_P(relevance, L, prereqs, r_star, L_star)
    R = recommendation_score_R(relevance, L, L_star)
    C = recommendation_score_C(relevance, last_attempted_relevance)
    D = recommendation_score_D(relevance, L, difficulty)

    subscores = np.array([P, R, C, D])
    weights = np.array([W_p, W_r, W_d, W_c])
    return np.dot(weights, subscores)


def recommendation_score_P(relevance, L, prereqs, r_star, L_star):
    """🔑 Substrategy P (Readiness) — 선수개념 역추적의 심장.

    선수개념이 충분히 안 잡힌 활동에 음수 페널티를 줘서 추천에서 밀어낸다.
    - np.minimum(L - L_star, 0): 통달한 개념은 0, 부족한 개념만 음수(결손 벡터)
    - dot(결손, prereqs): 각 개념의 선수개념 부족분 누적 (prereqs[행=선수, 열=후속])
    - minimum(m_r + r_star, 0): 관용 임계 r_star 넘게 부족하면 음수 = "아직 준비 안 됨"
    """
    m_w = prereqs
    fillna(m_w)
    m_r = np.dot(np.minimum(L - L_star, 0), m_w)
    P = np.dot(relevance, np.minimum((m_r + r_star), 0))
    return P


def recommendation_score_R(relevance, L, L_star):
    """Substrategy R (Remediation) — 아직 모르는 개념일수록 높은 점수."""
    return np.dot(relevance, np.maximum((L_star - L), 0))


def recommendation_score_C(relevance, last_attempted_relevance=None):
    """Substrategy C (Continuity) — 직전 학습과 관련된 활동에 가점. 첫 세션이면 0."""
    Q = relevance.shape[0]
    if last_attempted_relevance is None:
        return np.repeat(0.0, Q)
    return np.sqrt(np.dot(relevance, last_attempted_relevance))


def recommendation_score_D(relevance, L, difficulty):
    """Substrategy D (Difficulty) — 학습자 수준에 난이도가 맞을수록 높은 점수."""
    K = len(L)
    Q = len(difficulty)
    d_temp = np.tile(difficulty, (K, 1))
    L_temp = np.tile(L, (Q, 1)).T
    return -np.diag(np.dot(relevance, np.abs(L_temp - np.log(odds(d_temp)))))
