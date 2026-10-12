import os
import io
from PIL import Image, ImageDraw, ImageOps, ImageEnhance

class PlannerImageProcessor:
    def __init__(self, base_dir="AI-study"):
        # base_dir 경로 자동 탐색 (현재 디렉토리 또는 상위 디렉토리 기준)
        if os.path.isabs(base_dir) and os.path.exists(base_dir):
            self.base_dir = base_dir
        else:
            parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            if os.path.exists(os.path.join(parent_dir, "sample1.jpg")):
                self.base_dir = parent_dir
            elif os.path.exists(os.path.join(os.path.dirname(__file__), base_dir)):
                self.base_dir = os.path.join(os.path.dirname(__file__), base_dir)
            else:
                self.base_dir = parent_dir

    def _resolve_image(self, path_or_color: str, default_color=(255, 255, 255, 255), size=(300, 300)) -> Image.Image:
        """파일 경로 또는 색상 코드를 PIL Image로 로드"""
        if not path_or_color:
            return Image.new('RGBA', size, default_color)

        # 헥스 컬러 코드 지원 (예: #ff6b6b)
        if path_or_color.startswith('#'):
            hex_val = path_or_color.lstrip('#')
            if len(hex_val) == 6:
                r, g, b = tuple(int(hex_val[i:i+2], 16) for i in (0, 2, 4))
                return Image.new('RGBA', size, (r, g, b, 255))

        # 파일명 처리 (.jpg 확장자 보정)
        filename = path_or_color if '.' in path_or_color else f"{path_or_color}.jpg"
        full_path = os.path.join(self.base_dir, filename)

        if os.path.exists(full_path):
            return Image.open(full_path)

        # 파일이 없을 경우 단색 대체 이미지 생성
        return Image.new('RGBA', size, default_color)

    def apply_circular_mask(self, image: Image.Image) -> Image.Image:
        """[배경] 원형 마스킹 처리"""
        size = min(image.size)
        mask = Image.new('L', (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        
        # 중앙 크롭 후 원형 마스킹 적용
        left = (image.width - size) / 2
        top = (image.height - size) / 2
        cropped = image.crop((left, top, left + size, top + size))
        
        result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        result.paste(cropped, (0, 0), mask=mask)
        return result

    def extract_frame_nukki(self, image: Image.Image, color_type: str = "white_black") -> Image.Image:
        """[프레임] 중앙 및 외곽 투명 누끼 처리 (흰색/검정색/체크 패턴 제거)"""
        rgba_img = image.convert("RGBA")
        datas = rgba_img.getdata()
        
        new_data = []
        for item in datas:
            r, g, b, a = item
            # 흰색 배경 및 중앙 임계값 처리
            if color_type == "white" and r > 240 and g > 240 and b > 240:
                new_data.append((255, 255, 255, 0))
            # 검정색 중앙 및 외곽 임계값 처리
            elif color_type == "black" and r < 15 and g < 15 and b < 15:
                new_data.append((0, 0, 0, 0))
            # 체크무늬/흰색+검정색 복합 제거
            elif color_type == "white_black" and ((r > 235 and g > 235 and b > 235) or (r < 20 and g < 20 and b < 20)):
                new_data.append((0, 0, 0, 0))
            else:
                new_data.append(item)
                
        rgba_img.putdata(new_data)
        return rgba_img

    def extract_character_nukki(self, image: Image.Image) -> Image.Image:
        """[캐릭터] 외곽 흰색 여백 자동 누끼 처리 (내부 흰색 보존 BFS)"""
        from collections import deque
        rgba_img = image.convert("RGBA")
        w, h = rgba_img.size
        pixels = list(rgba_img.getdata())
        out = [list(p) for p in pixels]

        # 모서리 색상 표본 추출
        c0 = pixels[0][:3]
        if c0[0] >= 245 and c0[1] >= 245 and c0[2] >= 245:
            ref_r, ref_g, ref_b = c0
        else:
            ref_r, ref_g, ref_b = (255, 255, 255)

        visited = bytearray(w * h)
        q = deque()

        def is_bg(idx):
            r, g, b, _ = pixels[idx]
            return (abs(r - ref_r) <= 4 and abs(g - ref_g) <= 4 and abs(b - ref_b) <= 4 and
                    r >= 250 and g >= 250 and b >= 250)

        for x in range(w):
            for y in (0, h - 1):
                idx = y * w + x
                if not visited[idx] and is_bg(idx):
                    visited[idx] = 1
                    out[idx][3] = 0
                    q.append((x, y))
        for y in range(h):
            for x in (0, w - 1):
                idx = y * w + x
                if not visited[idx] and is_bg(idx):
                    visited[idx] = 1
                    out[idx][3] = 0
                    q.append((x, y))

        # 헤드셋 등 상단 폐곡선 내부 갇힌 흰색 공간 보조 탐색
        for check_y in range(int(h * 0.15), int(h * 0.35), 5):
            mid_x = w // 2
            idx = check_y * w + mid_x
            if not visited[idx] and is_bg(idx):
                visited[idx] = 1
                out[idx][3] = 0
                q.append((mid_x, check_y))
                break

        while q:
            cx, cy = q.popleft()
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < w and 0 <= ny < h:
                    nidx = ny * w + nx
                    if not visited[nidx]:
                        visited[nidx] = 1
                        if is_bg(nidx):
                            out[nidx][3] = 0
                            q.append((nx, ny))

        res_img = Image.new('RGBA', (w, h))
        res_img.putdata([tuple(p) for p in out])
        return res_img

    def render_profile(self, bg_path: str, char_path: str, frame_path: str, output_size=(300, 300)) -> Image.Image:
        """[합성] 레이어 합성: 1층(배경) -> 2층(캐릭터) -> 3층(프레임)"""
        # 1. 배경 로드 및 원형 마스킹
        bg_img = self._resolve_image(bg_path, default_color=(255, 215, 0, 255), size=output_size)
        bg_processed = self.apply_circular_mask(bg_img).resize(output_size, Image.Resampling.LANCZOS)
        
        # 2. 캐릭터 로드 및 누끼 추출
        char_img = self._resolve_image(char_path, default_color=(255, 255, 255, 0), size=output_size)
        char_processed = self.extract_character_nukki(char_img).resize(output_size, Image.Resampling.LANCZOS)
        
        # 3. 프레임 로드 및 누끼 추출
        frame_img = self._resolve_image(frame_path, default_color=(255, 255, 255, 0), size=output_size)
        frame_processed = self.extract_frame_nukki(frame_img).resize(output_size, Image.Resampling.LANCZOS)
        
        # 4. 순서대로 레이어 캔버스 합성 (Bottom to Top)
        canvas = Image.new('RGBA', output_size, (0, 0, 0, 0))
        canvas.alpha_composite(bg_processed)      # 1층: 원형 배경
        canvas.alpha_composite(char_processed)    # 2층: 누끼 캐릭터
        canvas.alpha_composite(frame_processed)   # 3층: 누끼 프레임
        
        return canvas

    def render_profile_bytes(self, bg_path: str, char_path: str, frame_path: str, output_size=(300, 300)) -> bytes:
        """합성된 프로필 이미지를 PNG 바이트 버퍼로 반환"""
        canvas = self.render_profile(bg_path, char_path, frame_path, output_size)
        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()
