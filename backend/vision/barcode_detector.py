import cv2
import numpy as np
from typing import Optional, List, Tuple
from vision.schemas import BarcodeDetectionResult
from vision.utils import normalize_bbox
from vision.config import vision_config

class BarcodeDetector:
    """
    Localizes 1D Barcodes on packaging using morphological gradient analysis.
    Finds parallel high-frequency vertical bar clusters.
    """

    @classmethod
    def detect(cls, img_bgr: np.ndarray) -> BarcodeDetectionResult:
        if img_bgr is None or img_bgr.size == 0:
            return BarcodeDetectionResult()

        h, w = img_bgr.shape[:2]

        # 1. First attempt direct barcode decoding via OpenCV's BarcodeDetector
        try:
            detector = cv2.barcode.BarcodeDetector()
            ret, decoded_info, decoded_types, points = detector.detectAndDecodeWithType(img_bgr)
            if ret and decoded_info and len(decoded_info) > 0 and decoded_info[0]:
                decoded_val = decoded_info[0].strip()
                decoded_type = decoded_types[0] if (decoded_types and len(decoded_types) > 0) else "1D_BARCODE"
                if points is not None and len(points) > 0:
                    pts = points[0].astype(int)
                    bx = int(np.min(pts[:, 0]))
                    by = int(np.min(pts[:, 1]))
                    bw = int(np.max(pts[:, 0]) - bx)
                    bh = int(np.max(pts[:, 1]) - by)
                    best_box = [max(0, bx), max(0, by), min(w, bx + bw), min(h, by + bh)]
                    norm_box = normalize_bbox(best_box, w, h)
                    return BarcodeDetectionResult(
                        detected=True,
                        barcode_type=decoded_type or "1D_BARCODE",
                        decoded_value=decoded_val,
                        bbox=best_box,
                        normalized_bbox=norm_box,
                        orientation="HORIZONTAL",
                        confidence=0.96,
                        confidence_tier=vision_config.get_confidence_tier(0.96),
                        detection_method="OPENCV_BARCODE_DETECTOR"
                    )
        except Exception:
            pass

        # 2. Fallback to morphological gradient analysis to localize barcode region
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # Compute Scharr/Sobel gradient magnitude representation in X and Y
        grad_x = cv2.Sobel(gray, ddepth=cv2.CV_32F, dx=1, dy=0, ksize=-1)
        grad_y = cv2.Sobel(gray, ddepth=cv2.CV_32F, dx=0, dy=1, ksize=-1)

        # Subtract Y-gradient from X-gradient to isolate vertical stripes
        gradient = cv2.subtract(grad_x, grad_y)
        gradient = cv2.convertScaleAbs(gradient)

        # Blur and threshold
        blurred = cv2.GaussianBlur(gradient, (9, 9), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Morphological close to bridge gaps between parallel bars
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        # Remove small speckles with erode and dilate
        closed = cv2.erode(closed, None, iterations=2)
        closed = cv2.dilate(closed, None, iterations=2)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return BarcodeDetectionResult()

        candidates = []
        for c in contours:
            bx, by, bw, bh = cv2.boundingRect(c)
            aspect = bw / float(max(1, bh))
            area = bw * bh

            # Barcodes typically have aspect ratio 1.0 to 6.0 and minimum area
            if area > 800 and 0.8 <= aspect <= 6.0 and bw < w * 0.95 and bh < h * 0.80:
                score = area * (1.0 if 1.2 <= aspect <= 4.0 else 0.7)
                candidates.append((score, [bx, by, bx + bw, by + bh]))

        if not candidates:
            return BarcodeDetectionResult()

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_box = candidates[0][1]
        norm_box = normalize_bbox(best_box, w, h)
        conf = 0.88

        return BarcodeDetectionResult(
            detected=True,
            barcode_type="1D_BARCODE",
            bbox=best_box,
            normalized_bbox=norm_box,
            orientation="HORIZONTAL",
            confidence=conf,
            confidence_tier=vision_config.get_confidence_tier(conf),
            detection_method="MORPHOLOGICAL_GRADIENT_BARS"
        )

barcode_detector = BarcodeDetector()
