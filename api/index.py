import sys
import os

# Vercel Serverless 실행 환경을 위해 프로젝트 루트 경로를 sys.path에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app
