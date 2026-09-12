from job_agent.candidate import CandidateFactStore, CandidateProfile


def test_missing_facts_do_not_default_silently() -> None:
    store = CandidateFactStore(CandidateProfile())

    assert store.get("identity.email") is None
    assert store.get("education.0.institution") is None
    assert store.all() == []


def test_known_false_boolean_is_still_a_known_fact() -> None:
    profile = CandidateProfile.model_validate(
        {"work_authorization": {"canada": {"authorized": False}}}
    )

    fact = CandidateFactStore(profile).get("work_authorization.canada.authorized")

    assert fact is not None
    assert fact.value is False
    assert fact.source_id == "fact.work_authorization.canada.authorized"


def test_fact_ids_are_stable() -> None:
    profile = CandidateProfile.model_validate(
        {"education": [{"institution": "Example University"}]}
    )
    store = CandidateFactStore(profile)

    first = store.get("education.0.institution")
    second = CandidateFactStore(profile).get("education.0.institution")

    assert first is not None and second is not None
    assert first.source_id == second.source_id == "fact.education.0.institution"
