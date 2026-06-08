"""영상 → 자막 (faster-whisper).

faster-whisper(CTranslate2)는 ffmpeg로 오디오를 읽으므로 mp4/mkv 등 직접 입력 가능.
Apple Silicon 데스크톱 기본: model="base"/"small" + compute_type="int8" (가벼움).
타임스탬프는 나중에 "이 개념은 영상 12:30 구간" 링크에 사용.

이 모듈은 faster-whisper 가 설치된 경우에만 import 된다 (지연 import).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Segment:
    start: float
    end: float
    text: str


def transcribe(video_path: str, model_size: str = "base",
               compute_type: str = "int8",
               language: str | None = None,
               initial_prompt: str | None = None) -> tuple[str, list[Segment]]:
    """영상/오디오 파일 → (전체 자막 텍스트, 타임스탬프 세그먼트 목록).

    :param language: 강제 언어 코드(예: "ko"). None이면 자동 감지.
    :param initial_prompt: 도메인 용어 힌트(예: "물의 순환, 증발, 응결, 강수").
        한국어 정확도가 낮을 때 어휘를 유도해 오인식을 줄인다(청사진 §5-4 품질 레버).
        정확도가 더 필요하면 model_size="medium" 도 고려.
    """
    from faster_whisper import WhisperModel  # 지연 import (무거운 의존성)

    model = WhisperModel(model_size, device="cpu", compute_type=compute_type)
    segments, _info = model.transcribe(
        video_path, word_timestamps=True,
        language=language, initial_prompt=initial_prompt,
    )
    segs = [Segment(start=s.start, end=s.end, text=s.text.strip()) for s in segments]
    full_text = " ".join(s.text for s in segs)
    return full_text, segs
