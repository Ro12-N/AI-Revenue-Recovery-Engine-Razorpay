import pytest
from sqlmodel import create_engine, Session, SQLModel
from app.models import BatchRun, RecoveryAction
from app.pipeline.pipeline import RevenueRecoveryPipeline
from app.llm.client import LLMClient

class TestPipelineIntegration:

    @pytest.fixture
    def test_session(self):
        # In-memory SQLite for testing
        engine = create_engine("sqlite:///:memory:", echo=False)
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            yield session

    def test_full_pipeline_run_shape_and_invariants(self, test_session):
        """
        Runs full 5-stage pipeline with mocked/heuristic LLM client.
        Asserts output shape, database persistence, and invariant: net_recovered <= gross_recovered.
        """
        # Initialize pipeline without live API key requirement
        mock_llm = LLMClient(api_key=None)
        pipeline = RevenueRecoveryPipeline(llm_client=mock_llm)

        seed = 999
        event_count = 50
        response = pipeline.run_batch(session=test_session, seed=seed, event_count=event_count)

        # 1. Assert Batch Summary Shape
        assert response.batch is not None
        assert response.batch.seed == seed
        assert response.batch.event_count == event_count
        assert response.batch.at_risk_count > 0
        assert len(response.actions) == response.batch.at_risk_count

        # 2. Invariant: net_recovered <= gross_recovered across batch and actions
        assert response.batch.total_recovered_net <= response.batch.total_recovered_gross
        assert response.batch.agent_off_total_lost == response.batch.total_at_risk

        # 3. Assert all 5 stages populated for every action
        for action in response.actions:
            # Stage 1: Detection
            assert action.trigger_event_id is not None
            assert action.trigger_type in ("payment_event", "checkout_session")
            
            # Stage 2: Diagnosis
            assert action.diagnosed_cause is not None
            assert 0.0 <= action.diagnosis_confidence <= 1.0
            assert action.diagnosis_source in ("rules", "llm", "llm-fallback")
            assert len(action.diagnosis_reasoning) > 0

            # Stage 3: Decision Engine
            assert action.chosen_intervention is not None
            assert action.intervention_bounds is not None
            assert len(action.decision_reasoning) > 0

            # Stage 4: Executor + Guardrails
            assert action.guardrail_ok in (True, False)
            if action.chosen_intervention not in ("no_action", "escalate_review"):
                assert action.drafted_message is not None
                assert action.sent_message is not None

            # Stage 5: Outcomes
            assert action.outcome in (
                "recovered", "promise_to_pay", "no_response",
                "escalated", "no_action", "stopped", "rejected"
            )
            assert action.net_recovered <= action.amount_recovered

        # 4. Assert Adversarial Self-Test Present and Passed
        assert response.self_test is not None
        assert response.self_test["guardrail_ok"] is False  # Correctly flagged adversarial violation
        assert "PASSED" in response.self_test["status"]

        # 5. Assert Non-technical Summary Present
        assert response.summary_text is not None
        assert "₹" in response.summary_text
