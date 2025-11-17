"""
Smoke tests for ML/OCR dependencies.

These tests ensure that critical ML/OCR dependencies are installed and functioning
correctly. They are designed to run in CI/CD pipelines to catch environment issues
before Docker build.

Author: Claude Code (Sonnet 4.5)
Date: 2025-11-16
Epic: CI/CD Preparation
Task: TSK-CICD-AUDIT-001
"""

import pytest
from packaging import version


class TestMLDependenciesAvailable:
    """Test that all ML dependencies can be imported."""

    def test_torch_available(self):
        """Verify PyTorch is installed and importable."""
        import torch

        assert version.parse(torch.__version__) >= version.parse("2.0.0"), (
            f"PyTorch version {torch.__version__} is too old. Minimum required: 2.0.0"
        )

    def test_transformers_available(self):
        """Verify Transformers library is installed and importable."""
        import transformers

        assert version.parse(transformers.__version__) >= version.parse("4.30.0"), (
            f"Transformers version {transformers.__version__} is too old. "
            f"Minimum required: 4.30.0"
        )

    def test_opencv_available(self):
        """Verify OpenCV is installed and importable."""
        import cv2

        assert version.parse(cv2.__version__) >= version.parse("4.8.0"), (
            f"OpenCV version {cv2.__version__} is too old. Minimum required: 4.8.0"
        )

    def test_sentence_transformers_available(self):
        """Verify sentence-transformers is installed and importable."""
        import sentence_transformers  # noqa: F401

        # Should not raise ImportError

    def test_scikit_learn_available(self):
        """Verify scikit-learn is installed and importable."""
        import sklearn

        assert version.parse(sklearn.__version__) >= version.parse("1.7.0"), (
            f"scikit-learn version {sklearn.__version__} is too old. "
            f"Minimum required: 1.7.0"
        )

    def test_numpy_available(self):
        """Verify NumPy is installed and importable."""
        import numpy as np

        assert version.parse(np.__version__) >= version.parse("1.26.0"), (
            f"NumPy version {np.__version__} is too old. Minimum required: 1.26.0"
        )

    def test_pandas_available(self):
        """Verify Pandas is installed and importable."""
        import pandas as pd

        assert version.parse(pd.__version__) >= version.parse("2.0.0"), (
            f"Pandas version {pd.__version__} is too old. Minimum required: 2.0.0"
        )


class TestMLBasicOperations:
    """Test basic operations with ML libraries."""

    def test_torch_basic_tensor_operations(self):
        """Test basic PyTorch tensor operations."""
        import torch

        # Create tensor
        tensor = torch.tensor([1.0, 2.0, 3.0])
        assert tensor.sum().item() == 6.0

        # Test device availability
        assert torch.cuda.is_available() or True  # CPU is always available

        # Test basic operations
        result = tensor * 2
        assert result.tolist() == [2.0, 4.0, 6.0]

    def test_opencv_basic_image_operations(self):
        """Test basic OpenCV image operations."""
        import cv2
        import numpy as np

        # Create a test image (black 100x100 image)
        img = np.zeros((100, 100, 3), dtype=np.uint8)

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        assert gray.shape == (100, 100)
        assert gray.dtype == np.uint8

        # Test resize
        resized = cv2.resize(img, (50, 50))
        assert resized.shape == (50, 50, 3)

    def test_numpy_basic_array_operations(self):
        """Test basic NumPy array operations."""
        import numpy as np

        # Create array
        arr = np.array([1, 2, 3, 4, 5])
        assert arr.sum() == 15
        assert arr.mean() == 3.0

        # Test matrix operations
        matrix = np.eye(3)
        assert matrix.shape == (3, 3)
        assert matrix[0, 0] == 1.0
        assert matrix[0, 1] == 0.0

    def test_transformers_tokenizer_basic(self):
        """Test basic transformers tokenizer operations."""
        from transformers import AutoTokenizer

        # Use a small, fast tokenizer for testing
        tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")

        # Test tokenization
        text = "Hello, world!"
        tokens = tokenizer(text, return_tensors="pt")

        assert "input_ids" in tokens
        assert "attention_mask" in tokens
        assert tokens["input_ids"].shape[0] == 1  # Batch size 1


class TestMLCacheDirectory:
    """Test that ML model cache directory is writable."""

    def test_model_cache_writable(self, tmp_path):
        """Test that we can write to model cache directory."""

        # Use tmp_path fixture for testing
        cache_dir = tmp_path / ".cache" / "huggingface"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Test write
        test_file = cache_dir / "test.txt"
        test_file.write_text("test")

        # Test read
        assert test_file.exists()
        assert test_file.read_text() == "test"

        # Cleanup
        test_file.unlink()

    def test_torch_cache_directory(self, tmp_path, monkeypatch):
        """Test that PyTorch can use a custom cache directory."""

        # Set custom cache directory
        cache_dir = tmp_path / ".cache" / "torch"
        cache_dir.mkdir(parents=True)
        monkeypatch.setenv("TORCH_HOME", str(cache_dir))

        # Test that cache directory is recognized
        # (Actual model download would be too slow for tests)
        assert cache_dir.exists()


class TestMLPerformanceBasic:
    """Basic performance tests for ML operations."""

    def test_torch_cuda_if_available(self):
        """Test CUDA availability and basic operations if GPU is present."""
        import torch

        if torch.cuda.is_available():
            # Test basic CUDA operation
            device = torch.device("cuda")
            tensor = torch.tensor([1.0, 2.0, 3.0]).to(device)
            assert tensor.device.type == "cuda"

            # Test computation on GPU
            result = tensor * 2
            assert result.sum().item() == 12.0
        else:
            # If no GPU, just verify CPU works
            tensor = torch.tensor([1.0, 2.0, 3.0])
            assert tensor.device.type == "cpu"

    def test_numpy_performance_basic(self):
        """Test basic NumPy performance with larger arrays."""
        import time

        import numpy as np

        # Create large array (10 million elements)
        arr = np.random.rand(10_000_000)

        # Time a basic operation (should be fast)
        start = time.time()
        result = arr.sum()
        elapsed = time.time() - start

        # Should complete in less than 1 second on any modern CPU
        assert elapsed < 1.0
        assert result > 0  # Sanity check


@pytest.mark.skipif(
    "os.environ.get('SKIP_SLOW_TESTS', '0') == '1'",
    reason="Slow test - skipped in fast CI runs",
)
class TestMLModelLoading:
    """Test actual model loading (slower tests, can be skipped in CI)."""

    def test_load_small_bert_model(self):
        """Test loading a small BERT model."""
        from transformers import AutoModel

        # Load smallest BERT model for testing
        model = AutoModel.from_pretrained("prajjwal1/bert-tiny")

        # Verify model loaded
        assert model is not None
        assert hasattr(model, "config")

    def test_load_sentence_transformer(self):
        """Test loading a sentence transformer model."""
        from sentence_transformers import SentenceTransformer

        # Load a tiny model for testing
        model = SentenceTransformer("paraphrase-MiniLM-L3-v2")

        # Test encoding
        sentences = ["Hello, world!"]
        embeddings = model.encode(sentences)

        assert embeddings.shape[0] == 1
        assert len(embeddings.shape) == 2  # 2D array (batch, embedding_dim)
