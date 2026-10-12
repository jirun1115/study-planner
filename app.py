import os
import sys
import logging
from datetime import datetime
import io
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from dotenv import load_dotenv
import requests
import google.generativeai as genai
from image_processor import PlannerImageProcessor

# 로깅 설정 (요청, 응답, 검색결과, 오류 출력)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# .env 환경변수 로드
load_dotenv()

app = Flask(__name__)

# API 키 및 설정 읽기
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "").strip()
PORT = int(os.getenv("FLASK_PORT", 5000))
DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")

# Gemini API 클라이언트 초기화
if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Gemini API가 성공적으로 설정되었습니다.")
else:
    logger.warning("경고: GEMINI_API_KEY가 올바르게 설정되지 않았습니다. .env 파일을 확인하세요.")

def search_serper(query: str) -> str:
    """
    Serper API를 호출하여 최신 시험 정보나 학습 리소스를 웹 검색합니다.
    """
    if not SERPER_API_KEY or SERPER_API_KEY == "your_serper_api_key_here":
        logger.info("Serper API Key가 제공되지 않아 실시간 웹 검색을 건너뜁니다.")
        return ""

    logger.info(f"Serper API 웹 검색 시작: '{query}'")
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "gl": "kr",
        "hl": "ko",
        "num": 4
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=8)
        if response.status_code == 200:
            data = response.json()
            snippets = []
            
            # 검색 결과 파싱 (organic 결과 추출)
            organic_results = data.get("organic", [])
            for item in organic_results[:3]:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                if snippet:
                    snippets.append(f"- 제목: {title}\n  내용: {snippet}\n  출처: {link}")

            result_text = "\n\n".join(snippets)
            logger.info(f"Serper API 검색 성공: {len(snippets)}건의 최신 정보를 수집했습니다.")
            return result_text
        else:
            logger.warning(f"Serper API 응답 오류 (상태 코드: {response.status_code}): {response.text}")
            return ""
    except Exception as e:
        logger.error(f"Serper API 호출 중 오류 발생: {str(e)}")
        return ""

def call_gemini(system_prompt: str, user_prompt: str) -> str:
    """
    Gemini 3.5 Flash Lite API (또는 호환 모델)를 호출하여 학습 플래너를 생성합니다.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        raise ValueError(".env 파일에 올바른 GEMINI_API_KEY를 입력해주세요.")

    # 모델 후보군: 요구사항에 명시된 Gemini 3.5 Flash Lite를 1순위로 시도
    model_candidates = [
        os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        "gemini-3.5-flash",
        "gemini-flash-lite-latest",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite"
    ]

    last_error = None
    for model_name in model_candidates:
        try:
            logger.info(f"Gemini 모델 호출 시도: {model_name}")
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_prompt
            )
            response = model.generate_content(
                user_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=4096
                )
            )
            if response and response.text:
                logger.info(f"Gemini 응답 생성 완료 (모델: {model_name})")
                return response.text
        except Exception as e:
            logger.warning(f"모델 '{model_name}' 호출 실패: {str(e)}")
            last_error = e

    if last_error:
        raise last_error
    raise RuntimeError("Gemini 모델로부터 응답을 받지 못했습니다.")

@app.route("/")
def index():
    """메인 화면 렌더링"""
    logger.info("메인 페이지('/') 접근")
    return render_template("index.html")

image_processor = PlannerImageProcessor()

@app.route("/style.css")
def serve_css():
    """정적 CSS 파일 제공"""
    return send_from_directory("static/css", "style.css")

@app.route("/app.js")
def serve_js():
    """정적 JS 파일 제공"""
    return send_from_directory("static/js", "app.js")

@app.route("/AI-study/transparent/<path:filename>")
def serve_transparent_ai_study(filename):
    """외곽 배경만 투명화된 고화질 캐릭터 PNG 서빙"""
    cache_dir = os.path.join(os.path.dirname(__file__), "static", "cache_transparent")
    base, _ = os.path.splitext(filename)
    cached_file = os.path.join(cache_dir, f"{base}.png")
    if os.path.exists(cached_file):
        return send_from_directory(cache_dir, f"{base}.png")
    return serve_ai_study(filename)

@app.route("/AI-study/<path:filename>")
def serve_ai_study(filename):
    """C:/AI-study 디렉토리의 샘플 이미지 에셋 제공 (외곽 투명 캐시 우선 서빙)"""
    cache_dir = os.path.join(os.path.dirname(__file__), "static", "cache_transparent")
    base, _ = os.path.splitext(filename)
    cached_file = os.path.join(cache_dir, f"{base}.png")
    if os.path.exists(cached_file):
        return send_from_directory(cache_dir, f"{base}.png")

    ai_study_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    file_path = os.path.join(ai_study_dir, filename)
    if not os.path.exists(file_path):
        for alt_ext in [".jpg", ".png", ".jpeg"]:
            alt_path = os.path.join(ai_study_dir, base + alt_ext)
            if os.path.exists(alt_path):
                return send_from_directory(ai_study_dir, base + alt_ext)
    return send_from_directory(ai_study_dir, filename)

@app.route("/avatar/composite")
def get_composite_avatar():
    """배경, 캐릭터, 프레임 레이어 3층 합성 아바타 PNG 제공"""
    char = request.args.get("char", "sample1")
    bg = request.args.get("bg", "sample24")
    frame = request.args.get("frame", "sample39")
    try:
        png_bytes = image_processor.render_profile_bytes(bg, char, frame)
        return send_file(io.BytesIO(png_bytes), mimetype="image/png")
    except Exception as e:
        logger.error(f"아바타 합성 오류: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/generate", methods=["POST"])
def generate():
    """
    학습플래너 생성 API 엔드포인트
    6가지 입력값을 검증하고, Serper 검색 및 Gemini 생성을 수행합니다.
    """
    logger.info("플래너 생성 요청('/generate') 수신")
    
    # 1. 요청 데이터 추출 (JSON 또는 Form 데이터 지원)
    if request.is_json:
        data = request.get_json() or {}
    else:
        data = request.form.to_dict()

    goal = data.get("goal", "").strip()
    exam_date = data.get("exam_date", "").strip()
    level = data.get("level", "").strip()
    daily_time = data.get("daily_time", "").strip()
    weakness = data.get("weakness", "").strip()
    study_style = data.get("study_style", "").strip()

    # 2. 백엔드 필수 입력 검증 (6가지 항목 모두 필수)
    missing_fields = []
    if not goal: missing_fields.append("학습목표")
    if not exam_date: missing_fields.append("시험일")
    if not level: missing_fields.append("현재 수준")
    if not daily_time: missing_fields.append("하루 가능시간")
    if not weakness: missing_fields.append("취약영역")
    if not study_style: missing_fields.append("선호 학습방식")

    if missing_fields:
        error_msg = f"다음 필수 입력 항목이 누락되었습니다: {', '.join(missing_fields)}"
        logger.warning(f"입력 검증 실패: {error_msg}")
        return jsonify({
            "success": False,
            "error": error_msg
        }), 400

    # 시험일 날짜 포맷 검증
    try:
        target_date = datetime.strptime(exam_date, "%Y-%m-%d").date()
        today = datetime.now().date()
        d_day = (target_date - today).days
        logger.info(f"시험일: {exam_date} (D-Day: {d_day}일 남음)")
    except ValueError:
        return jsonify({
            "success": False,
            "error": "시험일은 올바른 날짜 형식(YYYY-MM-DD)이어야 합니다."
        }), 400

    try:
        # 3. Serper API 최신 정보 웹 검색
        search_query = f"{goal} 시험 최신 일정 및 핵심 공부법"
        search_results = search_serper(search_query)

        # 4. 프롬프트 엔지니어링: 시스템 프롬프트 및 사용자 프롬프트 구성
        system_prompt = (
            "당신은 대한민국 최고의 수험 전략가이자 1:1 학습 멘토인 'AI 맞춤형 학습 플래너 코치'입니다.\n"
            "사용자의 목표, 일정, 취약점, 선호 학습 방식을 종합적으로 고려하여 극도로 구체적이고 실천 가능한 학습 계획을 수립합니다.\n\n"
            "## 작성 규칙:\n"
            "1. 반드시 아래 6가지 섹션 제목을 그대로 사용하여 체계적으로 작성하세요:\n"
            "   # 1. 주간계획\n"
            "   # 2. 일일계획\n"
            "   # 3. 복습주기\n"
            "   # 4. 점검문항\n"
            "   # 5. 진도체크\n"
            "   # 6. 학습회고\n"
            "2. [매우 중요] '1. 주간계획'과 '2. 일일계획' 섹션은 반드시 마크다운 체크박스 기호(`- [ ]`)를 사용하여 사용자가 하나씩 완료 체크(To-Do List)할 수 있는 목록 형식으로 작성해야 합니다.\n"
            "   예시:\n"
            "   - [ ] 1주차 월요일: 기본 개념서 1~3장 핵심 요약 및 공식 암기\n"
            "   - [ ] 1주차 화요일: 취약 단원 기출문제 20문항 풀이 및 오답노트 정리\n"
            "3. 친절하고 동기부여가 되는 어조로 작성하되, 수험생의 취약점을 집중 보완할 수 있는 현실적인 플랜을 제시하세요.\n"
            "4. 불필요한 서두나 잡담은 지양하고 플래너 본문 내용에 집중하세요."
        )

        user_prompt = f"""
[수험생 맞춤형 학습 정보]
- 학습목표: {goal}
- 목표 시험일: {exam_date} (D-Day: {d_day}일)
- 현재 수준: {level}
- 하루 학습 가능시간: {daily_time}
- 집중 보완 취약영역: {weakness}
- 선호 학습방식: {study_style}

[웹 실시간 검색 참고자료]
{search_results if search_results else "참고할 외부 검색 결과 없음. 자체 최적화 지식 적용"}

위 학생을 위한 맞춤형 학습 플래너를 6가지 섹션 규격에 맞추어 상세히 작성해 주세요. 
특히 '1. 주간계획'과 '2. 일일계획'은 반드시 `- [ ]` 체크박스 목록으로 작성해 주세요.
"""

        # 5. Gemini API 호출
        planner_content = call_gemini(system_prompt, user_prompt)
        logger.info("학습플래너 생성 완료 및 클라이언트 반환")

        return jsonify({
            "success": True,
            "planner": planner_content,
            "d_day": d_day,
            "exam_date": exam_date,
            "search_used": bool(search_results)
        })

    except Exception as e:
        error_message = str(e)
        logger.error(f"서버 처리 중 오류 발생: {error_message}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"학습플래너 생성 중 오류가 발생했습니다: {error_message}"
        }), 500

if __name__ == "__main__":
    logger.info(f"Flask 서버 시작 - http://127.0.0.1:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
