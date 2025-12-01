"""
NewStrategy API compatibility test
- Tries the new engine-style endpoints first (both with and without `/api/v1`),
- then falls back to the deprecated `/strategy/new/*` endpoints if necessary.

The tests are resilient: they accept either the new `/engine/...` shape or the
legacy `/strategy/new/...` forwarding behavior (which currently forwards to
the `alpha` engine).
"""
import asyncio
import httpx
import json
import os
from typing import Dict, Any, List, Tuple, Optional

# Allow tests to target a non-default base URL via environment variable.
# Default to the backend's actual listen address used by `backend/app_main.py`.
BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8200")
# Defaults to title-case engine name expected by the backend handlers.
ENGINE_NAME = os.getenv("API_ENGINE_NAME", "Alpha")


async def try_post_variants(client: httpx.AsyncClient, variants: List[Tuple[str, dict]]) -> Tuple[Optional[httpx.Response], Optional[str]]:
    """Try POSTing to a list of (url, json) variants and return the first non-404 response.

    Returns (response, url_used) or (None, None) if all attempts fail to connect.
    """
    for url, payload in variants:
        try:
            resp = await client.post(url, json=payload)
        except httpx.RequestError:
            continue
        if resp.status_code != 404:
            return resp, url
    return None, None


async def try_get_variants(client: httpx.AsyncClient, variants: List[str]) -> Tuple[Optional[httpx.Response], Optional[str]]:
    for url in variants:
        try:
            resp = await client.get(url)
        except httpx.RequestError:
            continue
        if resp.status_code != 404:
            return resp, url
    return None, None


async def test_api_endpoints():
    """API 엔드포인트 통합 테스트 (호환성 레이어 포함)"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("=" * 60)
        print("NewStrategy API 호환성 테스트")
        print("=" * 60)

        # 1. 초기 상태 확인 (try engine-style then fallback to legacy)
        status_variants = [
            f"{BASE_URL}/api/v1/engine/{ENGINE_NAME}/status",
            f"{BASE_URL}/engine/{ENGINE_NAME}/status",
            f"{BASE_URL}/api/v1/engine/status/{ENGINE_NAME}",
            f"{BASE_URL}/engine/status/{ENGINE_NAME}",
            f"{BASE_URL}/strategy/new/status",
        ]

        print("\n[1/6] 초기 상태 확인")
        resp, used = await try_get_variants(client, status_variants)
        if not resp:
            print("❌ 상태 확인에 실패했습니다: 모든 엔드포인트 응답 불가")
        else:
            print(f"응답 URL: {used}  Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(json.dumps(data, indent=2, ensure_ascii=False))
                if not data.get("data", {}).get("is_running", True):
                    print("✅ 초기 상태: 실행 중 아님")

        # 2. 전략 시작 (try multiple shapes)
        print("\n[2/6] 전략 시작 시도")
        start_payload_base = {"symbol": "BTCUSDT", "leverage": 10, "quantity": None}

        start_variants = [
            (f"{BASE_URL}/api/v1/engine/{ENGINE_NAME}/start", start_payload_base),
            (f"{BASE_URL}/engine/{ENGINE_NAME}/start", start_payload_base),
            (f"{BASE_URL}/api/v1/engine/start", {**start_payload_base, "engine": ENGINE_NAME}),
            (f"{BASE_URL}/engine/start", {**start_payload_base, "engine": ENGINE_NAME}),
            (f"{BASE_URL}/strategy/new/start", start_payload_base),
        ]

        resp, used = await try_post_variants(client, start_variants)
        if not resp:
            print("❌ 시작 실패: 모든 엔드포인트에 연결할 수 없음")
            return
        print(f"응답 URL: {used}  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
            if data.get("status") == "success":
                print("✅ 전략 시작 성공")
        else:
            print(f"⚠️ 시작 응답 상태: {resp.status_code}  텍스트: {resp.text}")

        # 3. 3초 대기
        print("\n[3/6] 3초 대기 (전략 실행 중...)")
        await asyncio.sleep(3)

        # 4. 실행 중 상태 확인
        print("\n[4/6] 실행 중 상태 확인")
        resp, used = await try_get_variants(client, status_variants)
        if resp and resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
            status_data = data.get("data", {})
            if status_data.get("is_running"):
                print("✅ 전략 실행 중 확인")
                print(f"   - Symbol: {status_data.get('symbol')}")
                print(f"   - Leverage: {status_data.get('leverage')}")
                print(f"   - Orchestrator Running: {status_data.get('orchestrator_running')}")

        # 5. 전략 중지
        print("\n[5/6] 전략 중지 시도")
        stop_payload = {"force": True}
        stop_variants = [
            (f"{BASE_URL}/api/v1/engine/{ENGINE_NAME}/stop", stop_payload),
            (f"{BASE_URL}/engine/{ENGINE_NAME}/stop", stop_payload),
            (f"{BASE_URL}/api/v1/engine/stop", {**stop_payload, "engine": ENGINE_NAME}),
            (f"{BASE_URL}/engine/stop", {**stop_payload, "engine": ENGINE_NAME}),
            (f"{BASE_URL}/strategy/new/stop", stop_payload),
        ]

        resp, used = await try_post_variants(client, stop_variants)
        if resp:
            print(f"응답 URL: {used}  Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(json.dumps(data, indent=2, ensure_ascii=False))
                if data.get("status") == "success":
                    print("✅ 전략 중지 성공")
                    if data.get("had_position"):
                        print("⚠️  포지션 보유 중이었음 (강제 종료)")
        else:
            print("❌ 중지 실패: 모든 엔드포인트 응답 불가")

        # 6. 최종 상태 확인
        print("\n[6/6] 최종 상태 확인")
        resp, used = await try_get_variants(client, status_variants)
        if resp and resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
            if not data.get("data", {}).get("is_running", True):
                print("✅ 최종 상태: 정상 종료됨")

        print("\n" + "=" * 60)
        print("테스트 완료")
        print("=" * 60)


async def test_duplicate_start():
    """중복 시작 방지 테스트 (엔드포인트 호환성 포함)"""
    print("\n" + "=" * 60)
    print("중복 시작 방지 테스트")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        start_payload = {"symbol": "ETHUSDT", "leverage": 10}

        start_variants = [
            (f"{BASE_URL}/api/v1/engine/{ENGINE_NAME}/start", start_payload),
            (f"{BASE_URL}/engine/{ENGINE_NAME}/start", start_payload),
            (f"{BASE_URL}/api/v1/engine/start", {**start_payload, "engine": ENGINE_NAME}),
            (f"{BASE_URL}/engine/start", {**start_payload, "engine": ENGINE_NAME}),
            (f"{BASE_URL}/strategy/new/start", start_payload),
        ]

        # 첫 번째 시작
        print("\n[1/3] 첫 번째 시작")
        resp, used = await try_post_variants(client, start_variants)
        if resp and resp.status_code == 200:
            print(f"✅ 첫 번째 시작 성공 (URL: {used})")
        else:
            print("❌ 첫 번째 시작 실패")

        # 두 번째 시작 (실패해야 함)
        print("\n[2/3] 두 번째 시작 (중복, 실패 예상)")
        resp2, used2 = await try_post_variants(client, start_variants)
        if resp2 and resp2.status_code == 400:
            print(f"✅ 중복 시작 방지됨: {resp2.json().get('detail')}")
        else:
            print(f"⚠️ 중복 시작 응답 상태: {None if not resp2 else resp2.status_code}  텍스트: {None if not resp2 else resp2.text}")

        # 정리
        print("\n[3/3] 정리 (중지)")
        stop_variants = [
            (f"{BASE_URL}/api/v1/engine/{ENGINE_NAME}/stop", {"force": True}),
            (f"{BASE_URL}/engine/{ENGINE_NAME}/stop", {"force": True}),
            (f"{BASE_URL}/api/v1/engine/stop", {"force": True, "engine": ENGINE_NAME}),
            (f"{BASE_URL}/engine/stop", {"force": True, "engine": ENGINE_NAME}),
            (f"{BASE_URL}/strategy/new/stop", {"force": True}),
        ]

        resp3, used3 = await try_post_variants(client, stop_variants)
        if resp3 and resp3.status_code == 200:
            print("✅ 정리 완료")


if __name__ == "__main__":
    print("⚠️  Backend 서버가 http://localhost:8000 에서 실행 중이어야 합니다.")
    print("   실행 명령: python backend/app_main.py\n")

    try:
        asyncio.run(test_api_endpoints())
        # asyncio.run(test_duplicate_start())
    except httpx.ConnectError:
        print("\n❌ Backend 서버에 연결할 수 없습니다.")
        print("   1. backend/app_main.py 실행 확인")
        print("   2. 포트 8000이 사용 중인지 확인")
    except KeyboardInterrupt:
        print("\n\n⚠️  테스트 중단됨 (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
