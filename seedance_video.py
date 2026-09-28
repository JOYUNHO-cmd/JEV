"""fal.ai를 통해 ByteDance Seedance 2.5로 영상을 생성하는 클라이언트.

주의:
  - 이건 실제 과금되는 유료 API다 (fal.ai 기준 1000토큰당 $0.0214,
    720p 기준 요금은 fal.ai/seedance-2.5 페이지에서 직접 확인할 것).
  - 이 코드는 fal.ai의 표준 큐 API 패턴(제출 -> 폴링 -> 결과 조회)으로 짰다.
    seedance-2.5의 정확한 입력 파라미터(prompt 외 duration/resolution/
    aspect_ratio 등 옵션명)는 fal.ai/models/bytedance/seedance-2.5 플레이
    그라운드에서 먼저 1건 테스트해 스키마를 맞춰본 뒤 배치로 돌릴 것.

사용법:
  export FAL_API_KEY=...
  python seedance_video.py "강남구 입주청소 홍보 영상, 밝고 깨끗한 톤"          # 1건 테스트
  python seedance_video.py posts_example.csv --batch --confirm-cost           # 여러 건
"""
from __future__ import annotations

import argparse
import csv
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

MODEL_PATH = "bytedance/seedance-2.5/text-to-video"
QUEUE_SUBMIT_URL = f"https://queue.fal.run/{MODEL_PATH}"
POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = 600

OUTPUT_DIR = Path(__file__).parent / "output_videos"


class SeedanceError(RuntimeError):
    pass


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}


def submit(prompt: str, api_key: str, **extra_params) -> dict:
    resp = requests.post(QUEUE_SUBMIT_URL, headers=_headers(api_key), json={"prompt": prompt, **extra_params}, timeout=30)
    if not resp.ok:
        raise SeedanceError(f"제출 실패 {resp.status_code}: {resp.text}")
    return resp.json()  # {"request_id", "status_url", "response_url", ...}


def poll_until_done(status_url: str, api_key: str) -> None:
    start = time.time()
    while time.time() - start < POLL_TIMEOUT_SEC:
        resp = requests.get(status_url, headers=_headers(api_key), timeout=30)
        resp.raise_for_status()
        status = resp.json().get("status")
        if status == "COMPLETED":
            return
        if status in {"ERROR", "FAILED"}:
            raise SeedanceError(f"생성 실패: {resp.text}")
        time.sleep(POLL_INTERVAL_SEC)
    raise SeedanceError(f"{POLL_TIMEOUT_SEC}초 안에 끝나지 않음: {status_url}")


def fetch_result(response_url: str, api_key: str) -> dict:
    resp = requests.get(response_url, headers=_headers(api_key), timeout=30)
    resp.raise_for_status()
    return resp.json()


def generate_video(prompt: str, api_key: str | None = None, **extra_params) -> str:
    """prompt로 영상을 생성하고 결과 mp4 URL을 반환한다."""
    api_key = api_key or os.environ.get("FAL_API_KEY")
    if not api_key:
        raise SeedanceError("FAL_API_KEY가 설정돼 있지 않습니다 (.env 확인)")

    submitted = submit(prompt, api_key, **extra_params)
    poll_until_done(submitted["status_url"], api_key)
    result = fetch_result(submitted["response_url"], api_key)

    video = result.get("video") or {}
    video_url = video.get("url")
    if not video_url:
        raise SeedanceError(f"응답에서 영상 URL을 찾지 못함: {result}")
    return video_url


def download(url: str, out_path: Path) -> None:
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    out_path.write_bytes(resp.content)


def build_prompt(region: str, service: str, notes: str) -> str:
    base = f"{region} {service} 청소 서비스를 소개하는 밝고 깨끗한 홍보 영상. 신뢰감 있는 톤."
    return f"{base} {notes}" if notes else base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="프롬프트 문자열(1건) 또는 CSV 경로(--batch일 때)")
    parser.add_argument("--batch", action="store_true", help="input을 posts CSV(지역,서비스,요구사항)로 취급해 여러 건 생성")
    parser.add_argument("--confirm-cost", action="store_true", help="배치는 과금이 발생함을 인지했다는 명시적 확인")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)

    if not args.batch:
        url = generate_video(args.input)
        out_path = OUTPUT_DIR / "test.mp4"
        download(url, out_path)
        print(f"완료: {out_path}")
        return

    if not args.confirm_cost:
        raise SystemExit("배치 생성은 실제 과금이 발생합니다. --confirm-cost를 붙여서 다시 실행하세요.")

    rows = list(csv.DictReader(Path(args.input).read_text(encoding="utf-8").splitlines()))
    print(f"{len(rows)}건 생성 시작 (건당 과금 발생)")

    for row in rows:
        region, service = row["지역"].strip(), row["서비스"].strip()
        notes = (row.get("요구사항") or "").strip()
        prompt = build_prompt(region, service, notes)

        try:
            url = generate_video(prompt)
            out_path = OUTPUT_DIR / f"{region}_{service}.mp4"
            download(url, out_path)
            print(f"{region} {service} -> {out_path}")
        except SeedanceError as e:
            print(f"{region} {service} 실패: {e}")


if __name__ == "__main__":
    main()
