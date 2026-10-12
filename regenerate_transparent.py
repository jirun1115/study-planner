import os
import time
from PIL import Image
from collections import deque

ai_study_dir = r"C:\AI-study"
out_dir = r"C:\AI-study\study-planner\static\cache_transparent"
os.makedirs(out_dir, exist_ok=True)

char_ids = [
    'simple1', 'simple4', 'simple5', 'simple7', 'simple8', 'simple10', 'simple11', 'simple13', 'simple14',
    'simple15', 'simple17', 'simple20', 'simple22', 'simple23', 'simple24', 'simple27', 'simple28', 'simple29',
    'sample26', 'sample25', 'sample21', 'sample19', 'sample18', 'sample20',
    'sample7', 'sample10', 'sample5', 'sample3', 'sample8', 'sample9', 'sample2', 'sample4', 'sample6',
    'sample22', 'sample23', 'sample24',
    'sample12', 'sample11', 'sample13', 'sample15', 'sample16', 'sample17', 'sample14',
    'ss1', 'ss2', 'ss3'
]

def process_image(char_id):
    src_file = None
    for ext in ['.png', '.jpg', '.jpeg']:
        p = os.path.join(ai_study_dir, char_id + ext)
        if os.path.exists(p):
            src_file = p
            break
    if not src_file:
        print(f"[SKIP] File not found: {char_id}")
        return

    im = Image.open(src_file).convert('RGBA')
    w, h = im.size

    # Resize if excessively large to keep responsive load times (max 800px)
    max_dim = 800
    if w > max_dim or h > max_dim:
        if w >= h:
            new_w = max_dim
            new_h = max(1, int(h * max_dim / w))
        else:
            new_h = max_dim
            new_w = max(1, int(w * max_dim / h))
        im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
        w, h = im.size

    pixels = list(im.getdata())
    out = [list(p) for p in pixels]

    # Sample corners to determine background color
    corners = [
        pixels[0][:3],
        pixels[w - 1][:3],
        pixels[(h - 1) * w][:3],
        pixels[(h - 1) * w + w - 1][:3]
    ]

    # If top corners are white, use top corner white reference
    top_c0 = corners[0]
    top_c1 = corners[1]
    if top_c0[0] >= 245 and top_c0[1] >= 245 and top_c0[2] >= 245:
        ref_r, ref_g, ref_b = top_c0
    elif top_c1[0] >= 245 and top_c1[1] >= 245 and top_c1[2] >= 245:
        ref_r, ref_g, ref_b = top_c1
    else:
        # Non-white background (e.g. sample26)
        ref_r = sorted([c[0] for c in corners])[1]
        ref_g = sorted([c[1] for c in corners])[1]
        ref_b = sorted([c[2] for c in corners])[1]

    is_white_bg = (ref_r >= 245 and ref_g >= 245 and ref_b >= 245)

    visited = bytearray(w * h)
    q = deque()

    def is_bg(idx):
        r, g, b, _ = pixels[idx]
        if is_white_bg:
            # Strict tolerance: only pure/near-pure canvas background
            # NEVER allow blue or darker colors, strictly r,g,b >= 250
            return (abs(r - ref_r) <= 4 and abs(g - ref_g) <= 4 and abs(b - ref_b) <= 4 and
                    r >= 250 and g >= 250 and b >= 250)
        else:
            # For non-white background, match sampled corner color closely
            return (abs(r - ref_r) <= 8 and abs(g - ref_g) <= 8 and abs(b - ref_b) <= 8)

    # Seed strictly from outer canvas border (top, bottom, left, right)
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

    # 폐곡선 소품(헤드셋 등) 내부 갇힌 흰색 배경을 위한 보조 시드 추가
    enclosed_seeds = {
        'simple14': [(w // 2, int(h * 0.275))],  # 울보사자 헤드셋 안쪽
        'simple28': [(w // 2, int(h * 0.23))]    # 헤드셋오리 헤드셋 안쪽
    }
    if char_id in enclosed_seeds:
        for sx, sy in enclosed_seeds[char_id]:
            if 0 <= sx < w and 0 <= sy < h:
                s_idx = sy * w + sx
                if not visited[s_idx] and is_bg(s_idx):
                    visited[s_idx] = 1
                    out[s_idx][3] = 0
                    q.append((sx, sy))

    # BFS flood fill only into contiguous background pixels
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

    out_path = os.path.join(out_dir, f"{char_id}.png")
    res_img.save(out_path, format="PNG")

    trans_pct = sum(visited) / (w * h) * 100
    print(f"[OK] {char_id:10s} -> size=({w}x{h}), bg_transparent={trans_pct:.1f}%")

if __name__ == "__main__":
    t0 = time.time()
    for cid in char_ids:
        process_image(cid)
    print(f"\nSuccessfully regenerated all {len(char_ids)} character images in {time.time() - t0:.2f}s!")
