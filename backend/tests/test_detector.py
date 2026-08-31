import pytest
from app.synthetic_data import generate_synthetic_batch
from app.pipeline.detector import Detector

class TestDetector:

    def test_seeded_reproducibility(self):
        """
        Proves that identical seeds produce identical event sets and at-risk detections.
        """
        seed = 12345
        custs1, pays1, checks1 = generate_synthetic_batch(seed=seed, event_count=70)
        custs2, pays2, checks2 = generate_synthetic_batch(seed=seed, event_count=70)

        assert len(custs1) == len(custs2)
        assert [p.id for p in pays1] == [p.id for p in pays2]
        assert [p.amount for p in pays1] == [p.amount for p in pays2]
        assert [c.id for c in checks1] == [c.id for c in checks2]

        at_risk1 = Detector.detect_at_risk(custs1, pays1, checks1)
        at_risk2 = Detector.detect_at_risk(custs2, pays2, checks2)

        assert len(at_risk1) == len(at_risk2)
        assert [e.event_id for e in at_risk1] == [e.event_id for e in at_risk2]
        assert [e.amount for e in at_risk1] == [e.amount for e in at_risk2]

    def test_event_mix_and_at_risk_filtering(self):
        """
        Proves event counts match target proportions and only at-risk events pass detector.
        """
        custs, pays, checks = generate_synthetic_batch(seed=42, event_count=100)
        
        # Proportions: ~60 payments, ~40 checkouts
        assert len(pays) == 60
        assert len(checks) == 40

        at_risk = Detector.detect_at_risk(custs, pays, checks)
        assert len(at_risk) > 0

        for item in at_risk:
            if item.event_type == "payment_event":
                assert item.raw_status in ("failed", "degraded")
            elif item.event_type == "checkout_session":
                assert item.raw_status != "completed"
