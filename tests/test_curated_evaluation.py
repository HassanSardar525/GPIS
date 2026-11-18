from scripts.run_curated_evaluation import factual_checks, values_match


def test_literacy_numbers_are_bound_to_the_correct_district_and_rounded():
    expected = [["Multan", "61.41"], ["Lahore", "79.62"]]
    assert values_match("Multan: 61.410495%. Lahore: 79.619010%.", expected)
    assert not values_match("Multan: 79.62%. Lahore: 61.41%.", expected)
    assert not values_match("Lahore: 79.62%.", expected)


def test_invented_marker_fails_despite_correct_number():
    response = {"answer": "Multan: 61.41% [unknown]", "citations": [], "abstained": False}
    ref = {"abstain": False, "values": [["Multan", "61.41"]], "terms": []}
    assert factual_checks(response, ref)["score"] == 0
