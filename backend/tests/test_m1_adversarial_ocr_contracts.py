"""
Milestone 1 Adversarial Stress & Contract Verification Suite
============================================================
Challenger 2 Empirical Verification Suite for:
1. Batch size alignment (`batch_size = 8`, `CHUNK_SIZE = 8`) and memory behavior
   on multi-crop panels in `backend/ocr/paddle_engine.py`.
2. Fallback condition elimination (`len(words1) == 0`) and pass early-exit logic
   (`len(words1) >= 6`, front prominence, statutory indicators) against simulated edge cases
   (empty image, sparse 4-word image, dense 40-word image).
3. OCRResult schema and interface contracts conformance.
"""

import os
import re
import pytest
import numpy as np
from unittest.mock import patch, MagicMock, call

from models.schemas import OCRResult, OCRWord
from ocr.paddle_engine import (
    PaddleOCREngine,
    _sync_paddle_extract,
    _sync_paddle_extract_multiscale,
    _identify_statutory_candidate_regions,
    _OCR_RESULT_CACHE,
    _OCR_CACHE_LOCK,
)


# ═════════════════════════════════════════════════════════════════════════════
# 1. BATCH SIZE ALIGNMENT & MEMORY CONTAINMENT ON MULTI-CROP PANELS
# ═════════════════════════════════════════════════════════════════════════════

class TestBatchAlignmentAndMemoryContainment:
    """Empirical verification of SVTR batch_size = 8 and CHUNK_SIZE = 8 alignment."""

    def test_direct_pipeline_crop_chunking_divisible_by_8(self, tmp_path):
        """Verify that 40 detected crops are chunked into exactly 5 batches of 8 with batch_size=8."""
        dummy_img_path = str(tmp_path / "test_40_crops.png")
        import cv2
        fake_img = np.zeros((800, 800, 3), dtype=np.uint8)
        cv2.imwrite(dummy_img_path, fake_img)

        # Generate 40 distinct non-overlapping horizontal boxes
        polys = []
        for i in range(40):
            y1 = i * 18 + 5
            y2 = y1 + 14
            polys.append([[10, y1], [150, y1], [150, y2], [10, y2]])

        mock_det_res = [{"dt_polys": polys}]
        mock_rec_model = MagicMock()
        mock_rec_model.batch_sampler = MagicMock()
        mock_rec_model.batch_sampler.batch_size = 4  # Initial value before alignment

        # SVTR recognition returns a record per crop
        def fake_rec(crops_batch):
            return [{"rec_text": f"Word_{i}", "rec_score": 0.95} for i in range(len(crops_batch))]

        mock_rec_model.side_effect = fake_rec

        mock_inner_pipe = MagicMock()
        mock_inner_pipe.text_det_model.predict.return_value = mock_det_res
        mock_inner_pipe.text_rec_model = mock_rec_model

        mock_ocr_inst = MagicMock()
        mock_ocr_inst.paddlex_pipeline._pipeline = mock_inner_pipe

        with patch("ocr.paddle_engine._init_paddle_ocr", return_value=mock_ocr_inst):
            lines, words, confs = _sync_paddle_extract(dummy_img_path)

            # 1. Verify batch_sampler.batch_size was updated to 8
            assert mock_rec_model.batch_sampler.batch_size == 8, (
                f"Expected batch_size == 8, got {mock_rec_model.batch_sampler.batch_size}"
            )

            # 2. Verify text_rec_model was called exactly 5 times (40 / 8)
            assert mock_rec_model.call_count == 5, (
                f"Expected exactly 5 batches for 40 crops, got {mock_rec_model.call_count}"
            )

            # 3. Verify each call passed exactly 8 crops (chunk size 8)
            for call_args in mock_rec_model.call_args_list:
                batch_passed = call_args[0][0]
                assert len(batch_passed) == 8, f"Expected chunk of 8 crops, got {len(batch_passed)}"

            # 4. Verify all crops were recognized and mapped to words
            assert len(words) == 40
            assert len(lines) == 40
            assert len(confs) == 40

    def test_direct_pipeline_crop_chunking_non_divisible_by_8(self, tmp_path):
        """Verify that 43 detected crops are chunked into 6 batches [8, 8, 8, 8, 8, 3]."""
        dummy_img_path = str(tmp_path / "test_43_crops.png")
        import cv2
        fake_img = np.zeros((1000, 800, 3), dtype=np.uint8)
        cv2.imwrite(dummy_img_path, fake_img)

        polys = []
        for i in range(43):
            y1 = i * 20 + 5
            y2 = y1 + 15
            polys.append([[10, y1], [120, y1], [120, y2], [10, y2]])

        mock_det_res = [{"dt_polys": polys}]
        mock_rec_model = MagicMock()
        mock_rec_model.batch_sampler = MagicMock()

        def fake_rec(crops_batch):
            return [{"rec_text": f"Item_{i}", "rec_score": 0.90} for i in range(len(crops_batch))]

        mock_rec_model.side_effect = fake_rec

        mock_inner_pipe = MagicMock()
        mock_inner_pipe.text_det_model.predict.return_value = mock_det_res
        mock_inner_pipe.text_rec_model = mock_rec_model

        mock_ocr_inst = MagicMock()
        mock_ocr_inst.paddlex_pipeline._pipeline = mock_inner_pipe

        with patch("ocr.paddle_engine._init_paddle_ocr", return_value=mock_ocr_inst):
            lines, words, confs = _sync_paddle_extract(dummy_img_path)

            assert mock_rec_model.call_count == 6
            chunk_sizes = [len(call_args[0][0]) for call_args in mock_rec_model.call_args_list]
            assert chunk_sizes == [8, 8, 8, 8, 8, 3], f"Unexpected chunk sizes: {chunk_sizes}"
            assert len(words) == 43

    def test_hasattr_guard_when_batch_sampler_missing(self, tmp_path):
        """Verify hasattr defensive guard prevents crashes when predictor lacks batch_sampler."""
        dummy_img_path = str(tmp_path / "test_no_sampler.png")
        import cv2
        cv2.imwrite(dummy_img_path, np.zeros((200, 200, 3), dtype=np.uint8))

        polys = [[[10, 10], [50, 10], [50, 30], [10, 30]]]
        mock_det_res = [{"dt_polys": polys}]

        # Create a spec without batch_sampler
        class BarePredictor:
            def __call__(self, crops):
                return [{"rec_text": "Sample", "rec_score": 0.99} for _ in crops]

        mock_rec_model = BarePredictor()
        assert not hasattr(mock_rec_model, "batch_sampler")

        mock_inner_pipe = MagicMock()
        mock_inner_pipe.text_det_model.predict.return_value = mock_det_res
        mock_inner_pipe.text_rec_model = mock_rec_model

        mock_ocr_inst = MagicMock()
        mock_ocr_inst.paddlex_pipeline._pipeline = mock_inner_pipe

        with patch("ocr.paddle_engine._init_paddle_ocr", return_value=mock_ocr_inst):
            lines, words, confs = _sync_paddle_extract(dummy_img_path)
            assert len(words) == 1
            assert words[0].text == "Sample"

    def test_memory_containment_under_high_crop_load(self, tmp_path):
        """Verify memory safety: chunk size never exceeds 8 even with 120 crops (cloud 512MB RAM invariant)."""
        dummy_img_path = str(tmp_path / "test_120_crops.png")
        import cv2
        cv2.imwrite(dummy_img_path, np.zeros((3000, 800, 3), dtype=np.uint8))

        polys = [[[10, i * 22], [100, i * 22], [100, i * 22 + 16], [10, i * 22 + 16]] for i in range(120)]
        mock_det_res = [{"dt_polys": polys}]

        observed_batch_sizes = []

        def fake_rec(crops_batch):
            observed_batch_sizes.append(len(crops_batch))
            return [{"rec_text": f"Line_{i}", "rec_score": 0.9} for i in range(len(crops_batch))]

        mock_rec_model = MagicMock(side_effect=fake_rec)
        mock_rec_model.batch_sampler = MagicMock()

        mock_inner_pipe = MagicMock()
        mock_inner_pipe.text_det_model.predict.return_value = mock_det_res
        mock_inner_pipe.text_rec_model = mock_rec_model

        mock_ocr_inst = MagicMock()
        mock_ocr_inst.paddlex_pipeline._pipeline = mock_inner_pipe

        with patch("ocr.paddle_engine._init_paddle_ocr", return_value=mock_ocr_inst):
            lines, words, confs = _sync_paddle_extract(dummy_img_path)

            assert max(observed_batch_sizes) <= 8, f"Batch size exceeded 8: {max(observed_batch_sizes)}"
            assert sum(observed_batch_sizes) == 120


# ═════════════════════════════════════════════════════════════════════════════
# 2. FALLBACK CONDITION AND PASS EARLY-EXIT LOGIC
# ═════════════════════════════════════════════════════════════════════════════

class TestFallbackAndEarlyExitLogic:
    """Stress tests for fallback trigger (len == 0) and early-exit conditions."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        with _OCR_CACHE_LOCK:
            _OCR_RESULT_CACHE.clear()
        yield
        with _OCR_CACHE_LOCK:
            _OCR_RESULT_CACHE.clear()

    def test_edge_case_empty_image_triggers_fallback(self, tmp_path):
        """Empty image (0 words) with w*h > 10000 invokes controlled fallback (2 passes)."""
        img_path = str(tmp_path / "blank_500x500.png")
        import cv2
        cv2.imwrite(img_path, np.zeros((500, 500, 3), dtype=np.uint8))

        # Pass 1 returns 0 words
        pass1_return = ([], [], [])
        # Pass 2 (fallback) also returns 0 words
        pass2_return = ([], [], [])

        with patch("ocr.paddle_engine._sync_paddle_extract", side_effect=[pass1_return, pass2_return]) as mock_extract:
            lines, words, confs, passes = _sync_paddle_extract_multiscale(img_path)

            # Controlled fallback triggers because len(words1) == 0 and 500*500 > 10000
            assert passes == 2, f"Expected 2 passes for empty image fallback, got {passes}"
            assert mock_extract.call_count == 2
            assert words == []

    def test_edge_case_small_empty_image_no_fallback(self, tmp_path):
        """Small empty image (w*h <= 10000) does not invoke fallback (1 pass)."""
        img_path = str(tmp_path / "tiny_80x80.png")
        import cv2
        cv2.imwrite(img_path, np.zeros((80, 80, 3), dtype=np.uint8))

        with patch("ocr.paddle_engine._sync_paddle_extract", return_value=([], [], [])) as mock_extract:
            lines, words, confs, passes = _sync_paddle_extract_multiscale(img_path)

            # Fallback condition (w*h > 10000) is False, no candidate regions -> 1 pass
            assert passes == 1
            assert mock_extract.call_count == 1
            assert words == []

    def test_edge_case_sparse_4_word_front_panel_early_exit(self, tmp_path):
        """Sparse front panel packaging image (4 words like 'FAMILY PACK TakaTak CHATPATA') exits in 1 pass."""
        img_path = str(tmp_path / "takatak_front_sparse.png")
        import cv2
        cv2.imwrite(img_path, np.zeros((600, 600, 3), dtype=np.uint8))

        # 4 prominent front panel words (height >= 20px, no back panel indicators)
        pass1_words = [
            OCRWord(text="FAMILY", confidence=98.0, bbox=[50, 40, 200, 90]),
            OCRWord(text="PACK", confidence=97.0, bbox=[220, 40, 350, 90]),
            OCRWord(text="TakaTak", confidence=99.0, bbox=[50, 120, 450, 240]),
            OCRWord(text="CHATPATA", confidence=96.0, bbox=[50, 260, 320, 330]),
        ]
        pass1_lines = ["FAMILY PACK", "TakaTak", "CHATPATA"]
        pass1_confs = [98.0, 97.0, 99.0, 96.0]

        with patch("ocr.paddle_engine._sync_paddle_extract", return_value=(pass1_lines, pass1_words, pass1_confs)) as mock_extract:
            lines, words, confs, passes = _sync_paddle_extract_multiscale(img_path)

            # Must exit in 1 pass via has_front_prominence
            assert passes == 1, f"Expected 1 pass for sparse front panel, got {passes}"
            assert mock_extract.call_count == 1
            assert len(words) == 4
            # Verify no fallback occurred
            assert "TakaTak" in [w.text for w in words]

    def test_elimination_of_premature_less_than_8_fallback(self, tmp_path):
        """Images with 1 to 7 words NEVER trigger full-image fallback (verifies elimination of len < 8 bug)."""
        img_path = str(tmp_path / "test_sparse_counts.png")
        import cv2
        cv2.imwrite(img_path, np.zeros((400, 400, 3), dtype=np.uint8))

        for word_count in range(1, 8):
            # Clear result cache between iterations
            with _OCR_CACHE_LOCK:
                _OCR_RESULT_CACHE.clear()

            words = [
                OCRWord(text=f"Word{i}", confidence=90.0, bbox=[10, i * 30, 80, i * 30 + 15])
                for i in range(word_count)
            ]
            lines = [f"Word{i}" for i in range(word_count)]
            confs = [90.0] * word_count

            with patch("ocr.paddle_engine._sync_paddle_extract", return_value=(lines, words, confs)) as mock_extract:
                res_lines, res_words, res_confs, passes = _sync_paddle_extract_multiscale(img_path)

                # Fallback condition is strictly len(words1) == 0.
                # Since word_count >= 1, full fallback (which calls extract on tmp_path) MUST NOT run.
                # If secondary pass runs, mock_extract would be called on a tmp file;
                # but if no statutory keywords exist, it exits in 1 pass.
                for call_args in mock_extract.call_args_list:
                    passed_path = call_args[0][0]
                    assert "_fallback" not in passed_path, (
                        f"Bug: Full-image fallback triggered for word_count={word_count}!"
                    )

    def test_edge_case_dense_40_word_image_early_exit(self, tmp_path):
        """Dense packaging label (40 words) exits immediately in 1 pass (len >= 6)."""
        img_path = str(tmp_path / "dense_back_panel.png")
        import cv2
        cv2.imwrite(img_path, np.zeros((1000, 800, 3), dtype=np.uint8))

        words = [
            OCRWord(text=f"Token_{i}", confidence=95.0, bbox=[20, i * 20, 150, i * 20 + 16])
            for i in range(40)
        ]
        lines = [f"Token_{i}" for i in range(40)]
        confs = [95.0] * 40

        with patch("ocr.paddle_engine._sync_paddle_extract", return_value=(lines, words, confs)) as mock_extract:
            res_lines, res_words, res_confs, passes = _sync_paddle_extract_multiscale(img_path)

            assert passes == 1, f"Expected 1 pass for dense 40-word image, got {passes}"
            assert mock_extract.call_count == 1
            assert len(res_words) == 40

    def test_statutory_indicators_bypass_secondary_pass_even_with_low_word_count(self, tmp_path):
        """Image with 4 words containing both Ingredients and MRP indicators exits in 1 pass."""
        img_path = str(tmp_path / "statutory_sparse.png")
        import cv2
        cv2.imwrite(img_path, np.zeros((400, 400, 3), dtype=np.uint8))

        words = [
            OCRWord(text="INGREDIENTS:", confidence=92.0, bbox=[10, 10, 120, 25]),
            OCRWord(text="Potato, Oil", confidence=91.0, bbox=[130, 10, 250, 25]),
            OCRWord(text="MRP", confidence=95.0, bbox=[10, 40, 50, 55]),
            OCRWord(text="Rs. 20.00", confidence=96.0, bbox=[60, 40, 140, 55]),
        ]
        lines = ["INGREDIENTS: Potato, Oil", "MRP Rs. 20.00"]
        confs = [92.0, 91.0, 95.0, 96.0]

        with patch("ocr.paddle_engine._sync_paddle_extract", return_value=(lines, words, confs)) as mock_extract:
            res_lines, res_words, res_confs, passes = _sync_paddle_extract_multiscale(img_path)

            # has_ingr and has_mrp both True -> early exit in 1 pass
            assert passes == 1
            assert mock_extract.call_count == 1
            assert len(res_words) == 4


# ═════════════════════════════════════════════════════════════════════════════
# 3. END-TO-END OCR ENGINE ASYNC CONTRACTS
# ═════════════════════════════════════════════════════════════════════════════

class TestPaddleOCREngineContracts:
    """Verify PaddleOCREngine.extract() public interface contracts and error resilience."""

    @pytest.mark.asyncio
    async def test_engine_extract_contract_structure(self, tmp_path):
        """Verify OCRResult fields, passes count, and statutory string cleanup."""
        img_path = str(tmp_path / "contract_test.png")
        import cv2
        cv2.imwrite(img_path, np.zeros((300, 300, 3), dtype=np.uint8))

        engine = PaddleOCREngine(lang="en")

        sample_lines = ["Net Weight: 400 9", "Lic No: FSSA1 10014051000910", "Chatpata Masala"]
        sample_words = [
            OCRWord(text="Net", confidence=95.0, bbox=[10, 10, 40, 25]),
            OCRWord(text="Weight:", confidence=95.0, bbox=[50, 10, 100, 25]),
            OCRWord(text="400", confidence=96.0, bbox=[110, 10, 140, 25]),
            OCRWord(text="g", confidence=94.0, bbox=[150, 10, 160, 25]),
            OCRWord(text="Lic", confidence=90.0, bbox=[10, 40, 35, 55]),
            OCRWord(text="No:", confidence=90.0, bbox=[40, 40, 65, 55]),
            OCRWord(text="FSSAI", confidence=98.0, bbox=[70, 40, 120, 55]),
            OCRWord(text="10014051000910", confidence=99.0, bbox=[130, 40, 260, 55]),
        ]
        sample_confs = [95.0, 95.0, 96.0, 94.0, 90.0, 90.0, 98.0, 99.0]

        with patch("ocr.paddle_engine._is_paddle_available", return_value=True), \
             patch("ocr.paddle_engine._sync_paddle_extract_multiscale", return_value=(sample_lines, sample_words, sample_confs, 1)):

            result = await engine.extract(img_path)

            assert isinstance(result, OCRResult)
            assert result.ocr_passes == 1
            assert result.word_count == 8
            assert "400 g" in result.full_text
            assert "FSSAI" in result.full_text
            assert result.average_confidence > 90.0
            assert result.engine == "PaddleOCR (PP-OCRv4)"

    @pytest.mark.asyncio
    async def test_engine_graceful_handling_on_unavailable(self):
        """Engine returns safe fallback OCRResult when paddle is unavailable."""
        engine = PaddleOCREngine()

        with patch("ocr.paddle_engine._is_paddle_available", return_value=False):
            result = await engine.extract("non_existent.jpg")
            assert isinstance(result, OCRResult)
            assert result.ocr_passes == 0
            assert result.word_count == 0
            assert result.average_confidence == 0.0
            assert "Unavailable" in result.engine
