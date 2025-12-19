"""Analysis state enum and helpers for strategy analysis UI buttons."""
from enum import Enum


class AnalysisState(Enum):
    IDLE = "idle"
    LOADING = "loading"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


def state_label(state: AnalysisState) -> str:
    return {
        AnalysisState.IDLE: "전략 분석",
        # LOADING: 백엔드에 전략 분석 요청을 보내고
        # 히스토리컬 데이터를 수집하는 단계 - "다운로드 중..."
        AnalysisState.LOADING: "다운로드 중...",
        # RUNNING: 수집된 데이터를 기반으로 전략 시뮬레이션을
        # 수행하는 단계 - "분석중..."
        AnalysisState.RUNNING: "분석중...",
        AnalysisState.COMPLETED: "완료",
        AnalysisState.ERROR: "오류",
    }.get(state, "전략 분석")


def state_style(state: AnalysisState) -> str:
    # Lightweight styles for each state; caller may override with additional rules
    mapping = {
        AnalysisState.IDLE: """
            QPushButton { background-color: #4CAF50; color: white; font-weight: bold; font-size: 9px; border: none; border-radius: 3px; padding: 4px 8px; min-width: 60px; }
            QPushButton:hover { background-color: #66BB6A; }
            QPushButton:pressed { background-color: #388E3C; }
        """,
        AnalysisState.LOADING: """
            QPushButton { background-color: #f0ad4e; color: white; font-weight: bold; font-size: 9px; border: none; border-radius: 3px; padding: 4px 8px; }
        """,
        AnalysisState.RUNNING: """
            QPushButton { background-color: #2196F3; color: white; font-weight: bold; font-size: 9px; border: none; border-radius: 3px; padding: 4px 8px; }
        """,
        AnalysisState.COMPLETED: """
            QPushButton { background-color: #6c757d; color: white; font-weight: bold; font-size: 9px; border: none; border-radius: 3px; padding: 4px 8px; }
        """,
        AnalysisState.ERROR: """
            QPushButton { background-color: #e16476; color: white; font-weight: bold; font-size: 9px; border: none; border-radius: 3px; padding: 4px 8px; }
        """,
    }
    return mapping.get(state, "")
