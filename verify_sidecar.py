"""사이드카 서버 검증 (Tauri 불필요).

1부 (결정적, in-process TestClient): connect/ingest(직접개념)/recommend/path/수준대
2부 (실프로세스): uvicorn 기동 → HTTP 호출 → stdin "sidecar shutdown" 종료 확인

실행: .venv/bin/python verify_sidecar.py
"""

import subprocess
import sys
import time


def part1_testclient():
    from fastapi.testclient import TestClient
    from sidecar.server import app

    c = TestClient(app)
    print("=" * 74)
    print("[1부] in-process API 검증 (LLM 불필요)")
    print("=" * 74)
    assert c.get("/v1/connect").json()["status"] == "ok"

    ing = c.post("/v1/ingest", json={
        "concepts": ["최대공약수", "약분", "분수의 덧셈", "일차방정식", "이차방정식"],
        "edges": [["최대공약수", "약분"], ["약분", "분수의 덧셈"],
                  ["분수의 덧셈", "일차방정식"], ["일차방정식", "이차방정식"],
                  ["이차방정식", "최대공약수"]],  # 순환! 자동 제거돼야
    }).json()
    gid = ing["graph_id"]
    print(f"  ingest: graph_id={gid}, 개념 {len(ing['concepts'])}개 (순환 입력 → DAG 생성 성공)")

    rec = c.post("/v1/recommend",
                 json={"graph_id": gid, "responses": {"이차방정식": [0, 0, 0]}}).json()
    print(f"  recommend(이차방정식 막힘): 다음 = {rec['next']['name']}")
    assert rec["next"]["name"] == "최대공약수"

    p = c.post("/v1/path", json={"graph_id": gid, "target": "이차방정식"}).json()
    print(f"  path: {' → '.join(p['path'])}")
    assert p["path"][0] == "최대공약수" and p["path"][-1] == "이차방정식"

    pe = c.post("/v1/path", json={"graph_id": gid, "target": "이차방정식",
                                  "band": "elementary"}).json()["path"]
    pt = c.post("/v1/path", json={"graph_id": gid, "target": "이차방정식",
                                  "band": "tertiary_adult"}).json()["path"]
    print(f"  수준대 초등:      {' → '.join(pe)}")
    print(f"  수준대 대학·성인: {' → '.join(pt)}")
    assert len(pt) < len(pe)  # 성인은 기초를 건너뛰어 더 짧아야
    print("  ✅ 1부 통과")


def part2_live_process():
    print("\n" + "=" * 74)
    print("[2부] 실프로세스 — uvicorn 기동 → HTTP → stdin 종료")
    print("=" * 74)
    import httpx

    proc = subprocess.Popen([sys.executable, "-m", "sidecar.server"],
                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    try:
        # ready 폴링 (사이드카는 spawn 직후 바로 안 뜸 — reference §5-7)
        for _ in range(20):
            time.sleep(0.5)
            try:
                if httpx.get("http://127.0.0.1:8008/v1/connect", timeout=1).status_code == 200:
                    break
            except Exception:
                pass
        else:
            raise RuntimeError("서버가 기동되지 않음")
        print("  HTTP 기동 확인 (connect 200)")

        # Tauri ExitRequested 와 동일한 종료 신호
        proc.stdin.write(b"sidecar shutdown\n")
        proc.stdin.flush()
        code = proc.wait(timeout=8)
        print(f"  stdin 'sidecar shutdown' → 종료 (exit {code}, SIGINT) — 좀비 없음")
        print("  ✅ 2부 통과")
    finally:
        if proc.poll() is None:
            proc.kill()


if __name__ == "__main__":
    part1_testclient()
    part2_live_process()
    print("\n" + "=" * 74)
    print("완료 — 사이드카 API가 곧 Tauri UI 가 호출할 계약(contract)이다.")
    print("=" * 74)
