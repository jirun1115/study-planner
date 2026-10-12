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

def process_character_perfect(char_id):
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

    # Downscale overly gigantic images (>1200px) for fast high-precision processing
    max_src = 1200
    if w > max_src or h > max_src:
        if w >= h:
            nw = max_src
            nh = max(1, int(round(h * max_src / w)))
        else:
            nh = max_src
            nw = max(1, int(round(w * max_src / h)))
        im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        w, h = im.size

    pixels = list(im.getdata())
    out = [list(p) for p in pixels]

    # Sample top corner background
    c0 = pixels[0][:3]
    c1 = pixels[w - 1][:3]
    if c0[0] >= 245 and c0[1] >= 245 and c0[2] >= 245:
        ref_r, ref_g, ref_b = c0
    elif c1[0] >= 245 and c1[1] >= 245 and c1[2] >= 245:
        ref_r, ref_g, ref_b = c1
    else:
        corners = [pixels[0][:3], pixels[w - 1][:3], pixels[(h - 1) * w][:3], pixels[(h - 1) * w + w - 1][:3]]
        ref_r = sorted([c[0] for c in corners])[1]
        ref_g = sorted([c[1] for c in corners])[1]
        ref_b = sorted([c[2] for c in corners])[1]

    is_white_bg = (ref_r >= 245 and ref_g >= 245 and ref_b >= 245)

    visited = bytearray(w * h)
    q = deque()

    def is_bg(idx):
        r, g, b, _ = pixels[idx]
        if is_white_bg:
            return (abs(r - ref_r) <= 4 and abs(g - ref_g) <= 4 and abs(b - ref_b) <= 4 and
                    r >= 250 and g >= 250 and b >= 250)
        else:
            return (abs(r - ref_r) <= 8 and abs(g - ref_g) <= 8 and abs(b - ref_b) <= 8)

    # 1. Outer boundary seeds
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

    # 2. Enclosed headset seeds (for simple14 and simple28)
    enclosed_seeds = {
        'simple14': [(w // 2, int(h * 0.275))],
        'simple28': [(w // 2, int(h * 0.23))]
    }
    if char_id in enclosed_seeds:
        for sx, sy in enclosed_seeds[char_id]:
            if 0 <= sx < w and 0 <= sy < h:
                sidx = sy * w + sx
                if not visited[sidx] and is_bg(sidx):
                    visited[sidx] = 1
                    out[sidx][3] = 0
                    q.append((sx, sy))

    # 3. BFS flood fill
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

    clean_img = Image.new('RGBA', (w, h))
    clean_img.putdata([tuple(p) for p in out])

    # 4. Tight bounding box of character (100% FULL BODY, NO CROPPING/AMPUTATION)
    bbox = clean_img.getbbox()
    if not bbox:
        print(f"[WARN] Empty bbox for {char_id}")
        return

    # Extract 100% full intact character
    full_char = clean_img.crop(bbox)
    cw, ch = full_char.size

    # 5. Scale to standard dimension (480px) preserving exact aspect ratio
    canvas_size = 600
    target_dim = 480
    scale = target_dim / max(cw, ch)
    new_w = max(1, int(round(cw * scale)))
    new_h = max(1, int(round(ch * scale)))
    resized = full_char.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # 6. Perfect geometric center placement
    canvas = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))
    offset_x = (canvas_size - new_w) // 2
    offset_y = (canvas_size - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y), resized)

    out_file = os.path.join(out_dir, f"{char_id}.png")
    canvas.save(out_file, format="PNG")
    print(f"[OK] {char_id:10s} raw=({cw}x{ch}) -> full_scaled=({new_w}x{new_h}) centered at ({offset_x}, {offset_y})")

def main():
    t0 = time.time()
    print(f"Generating 100% Full-Body Uncut Centered Avatars for {len(char_ids)} characters...")
    for cid in char_ids:
        process_character_perfect(cid)
    print(f"\nAll {len(char_ids)} characters generated perfectly in {time.time() - t0:.2f}s!")

if __name__ == "__main__":
    main()
