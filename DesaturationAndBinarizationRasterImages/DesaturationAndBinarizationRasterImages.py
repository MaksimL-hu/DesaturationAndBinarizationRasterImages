from pathlib import Path
from io import BytesIO
import requests
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# -----------------------------
# НАСТРОЙКИ
# -----------------------------
ORIGIN = "https://www.slavcorpora.ru"
SAMPLE_ID = "b008ae91-32cf-4d7d-84e4-996144e4edb7"

# Параметр метода Сингха.
# Можно менять для разных изображений
SINGH_K = 0.05

# Размер окна по заданию
WINDOW_SIZE = 3

# Лимит для скачивания (None - нет лимита)
LIMIT = 3

# Папки
ROOT = Path("lab2_output")
INPUT_DIR = ROOT / "input_png"
GRAY_DIR = ROOT / "grayscale_bmp"
BIN_DIR = ROOT / "binary_bmp"

for folder in [ROOT, INPUT_DIR, GRAY_DIR, BIN_DIR]:
    folder.mkdir(parents=True, exist_ok=True)


# -----------------------------
# ЗАГРУЗКА ИСХОДНЫХ ИЗОБРАЖЕНИЙ
# -----------------------------
def fetch_sample_image_urls(origin: str, sample_id: str, limit: int | None = None) -> list[str]:
    url = f"{origin}/api/samples/{sample_id}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    sample_data = response.json()

    image_urls = [f"{origin}/images/{page['filename']}" for page in sample_data["pages"]]

    if limit is not None:
        image_urls = image_urls[:limit]

    return image_urls


def download_images_as_png(image_urls: list[str], out_dir: Path) -> list[Path]:
    """
    Скачать изображения и сохранить их в PNG
    """
    saved_paths = []

    for idx, url in enumerate(image_urls, start=1):
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        img = Image.open(BytesIO(response.content)).convert("RGB")
        out_path = out_dir / f"img_{idx:03d}.png"
        img.save(out_path, format="PNG")
        saved_paths.append(out_path)

        print(f"[OK] Скачано и сохранено: {out_path}")

    return saved_paths


# -----------------------------
# 1. RGB -> ПОЛУТОН
# -----------------------------
def rgb_to_grayscale_manual(rgb: np.ndarray) -> np.ndarray:
    """
    перевод RGB -> grayscale.
    Формула взвешенного усреднения:
        Y = 0.299 R + 0.587 G + 0.114 B
    """
    rgb_f = rgb.astype(np.float32)

    r = rgb_f[:, :, 0]
    g = rgb_f[:, :, 1]
    b = rgb_f[:, :, 2]

    gray = 0.299 * r + 0.587 * g + 0.114 * b
    gray = np.clip(gray, 0, 255).astype(np.uint8)
    return gray


def save_grayscale_bmp(gray: np.ndarray, out_path: Path) -> None:
    """
    Сохранение полутонового изображения в BMP (1 канал яркости).
    """
    img = Image.fromarray(gray, mode="L")
    img.save(out_path, format="BMP")


# -----------------------------
# 2. БИНАРИЗАЦИЯ СИНГХА 3x3
# -----------------------------
def mean_filter_3x3(gray_norm: np.ndarray) -> np.ndarray:
    """
    расчёт локального среднего по окну 3x3
    """
    p = np.pad(gray_norm, 1, mode="edge")

    s = (
        p[:-2, :-2] + p[:-2, 1:-1] + p[:-2, 2:] +
        p[1:-1, :-2] + p[1:-1, 1:-1] + p[1:-1, 2:] +
        p[2:, :-2] + p[2:, 1:-1] + p[2:, 2:]
    )

    return s / 9.0


def mean_filter_manual(gray_norm: np.ndarray, window_size: int = 3) -> np.ndarray:
    if window_size % 2 == 0 or window_size < 1:
        raise ValueError("window_size должен быть нечётным положительным числом")

    pad = window_size // 2
    padded = np.pad(gray_norm, pad, mode="edge")

    h, w = gray_norm.shape
    result = np.zeros((h, w), dtype=np.float32)

    for dy in range(window_size):
        for dx in range(window_size):
            result += padded[dy:dy + h, dx:dx + w]

    result /= (window_size * window_size)
    return result


def singh_binarization(gray: np.ndarray, k: float = 0.25, window_size: int = 3) -> np.ndarray:
    gray_norm = gray.astype(np.float32) / 255.0
    m = mean_filter_manual(gray_norm, window_size)
    d = gray_norm - m

    eps = 1e-6
    denominator = 1.0 - d
    denominator = np.where(np.abs(denominator) < eps, eps, denominator)

    t = m * (1.0 + k * ((d / denominator) - 1.0))
    t = np.clip(t, 0.0, 1.0)

    binary = gray_norm > t
    return binary


def save_binary_bmp(binary: np.ndarray, out_path: Path) -> None:
    """
    Сохранение бинарного изображения как 1-битного BMP.
    """
    img = Image.fromarray(binary)   # bool -> mode '1'
    img.save(out_path, format="BMP")


# -----------------------------
# ОБРАБОТКА ИЗОБРАЖЕНИЯ
# -----------------------------
def process_one_image(img_path: Path, k: float = 0.25) -> None:
    stem = img_path.stem

    img = Image.open(img_path).convert("RGB")
    rgb = np.array(img, dtype=np.uint8)

    # 1. Полутон
    gray = rgb_to_grayscale_manual(rgb)
    gray_path = GRAY_DIR / f"{stem}_gray.bmp"
    save_grayscale_bmp(gray, gray_path)

    # 2. Бинаризация Сингха
    binary = singh_binarization(gray, k=SINGH_K, window_size=WINDOW_SIZE)
    bin_path = BIN_DIR / f"{stem}_binary_singh_3x3.bmp"
    save_binary_bmp(binary, bin_path)

    print(f"[OK] Обработано: {img_path.name}")
    print(f"     Полутон:   {gray_path}")
    print(f"     Бинарное:  {bin_path}")


# -----------------------------
# MAIN
# -----------------------------
def main():
    print("=== Лабораторная работа №2 ===")
    print("Загрузка изображений из API...")

    image_urls = fetch_sample_image_urls(ORIGIN, SAMPLE_ID, LIMIT)
    print(f"Найдено изображений: {len(image_urls)}")

    input_paths = download_images_as_png(image_urls, INPUT_DIR)

    print("\nЗапуск обработки...")
    for path in input_paths:
        process_one_image(path, k=SINGH_K)

    print("\nГотово.")
    print(f"Все результаты находятся в папке: {ROOT.resolve()}")


if __name__ == "__main__":
    main()