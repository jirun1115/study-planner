import os
import time
from PIL import Image

cache_dir = r"C:\AI-study\study-planner\static\cache_transparent"
canvas_size = 600

def normalize_character(fname):
    if not fname.endswith(".png"):
        return
    fpath = os.path.join(cache_dir, fname)
    try:
        im = Image.open(fpath).convert("RGBA")
    except Exception as e:
        print(f"[ERR] Failed to open {fname}: {e}")
        return

    # Find tight bounding box of opaque content
    bbox = im.getbbox()
    if not bbox:
        print(f"[WARN] Empty bounding box for {fname}")
        return

    # Crop tightly to character silhouette
    cropped = im.crop(bbox)
    cw, ch = cropped.size
    aspect = cw / ch

    # Optical Scaling & Eye-Level Target:
    # 1. Round/square characters (aspect >= 0.82): target max dimension 460px
    # 2. Slender/tall full-body characters (aspect < 0.82): scale height up to 525px so visual volume matches round characters
    if aspect < 0.70:
        # Very slender characters (e.g. Disney princesses, Cinderella, slender animals)
        target_h = 525
        scale = target_h / ch
        new_w = max(1, int(round(cw * scale)))
        new_h = target_h
        # Keep inside canvas width
        if new_w > 520:
            scale = 520 / cw
            new_w = 520
            new_h = max(1, int(round(ch * scale)))
    elif aspect < 0.82:
        # Moderately tall characters
        target_h = 505
        scale = target_h / ch
        new_w = max(1, int(round(cw * scale)))
        new_h = target_h
        if new_w > 500:
            scale = 500 / cw
            new_w = 500
            new_h = max(1, int(round(ch * scale)))
    else:
        # Round/wide characters (Chiikawa, Panda, Cinnamoroll, Kirby, Duck, etc.)
        target_max = 460
        scale = target_max / max(cw, ch)
        new_w = max(1, int(round(cw * scale)))
        new_h = max(1, int(round(ch * scale)))

    # High quality Lanczos resize
    resized_char = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Calculate center placement
    offset_x = (canvas_size - new_w) // 2
    
    # Vertical positioning:
    # For tall slender characters, give a tiny 10px breathing room from the top so head nicely aligns with circle upper curve
    if aspect < 0.80 and new_h >= 500:
        offset_y = max(38, (canvas_size - new_h) // 2 + 10)
    else:
        offset_y = (canvas_size - new_h) // 2

    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    canvas.paste(resized_char, (offset_x, offset_y), resized_char)

    # Save normalized PNG
    canvas.save(fpath, format="PNG")
    print(f"[OK] {fname:15s} aspect={aspect:.2f} -> size=({new_w}x{new_h}) at ({offset_x}, {offset_y})")

def main():
    t0 = time.time()
    files = sorted([f for f in os.listdir(cache_dir) if f.endswith(".png")])
    print(f"Starting Optical Scaling & Eye-Level Normalization for {len(files)} files...")
    for f in files:
        normalize_character(f)
    print(f"\nCompleted in {time.time() - t0:.2f}s!")

if __name__ == "__main__":
    main()
