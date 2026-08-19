import json
import unittest
from pathlib import Path

from app.retrieval import EvidenceRetriever, generate_grounded_answer
from app.scoring import rankings, score_districts


ROOT = Path(__file__).resolve().parents[1]


class PrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "data/curated/districts.json").read_text(encoding="utf-8"))
        cls.districts = score_districts(cls.data["districts"])

    def test_all_scores_are_in_range(self):
        for district in self.districts:
            for score in district["derived"]["scores"].values():
                self.assertGreaterEqual(score, 0)
                self.assertLessEqual(score, 100)

    def test_rankings_have_unique_positions(self):
        for category in ("overall", "education", "health", "accountability"):
            result = rankings(self.districts, category)
            self.assertEqual([item["rank"] for item in result], [1, 2, 3, 4, 5])

    def test_retrieval_stays_on_selected_district(self):
        retriever = EvidenceRetriever(self.districts, self.data["sources"])
        result = retriever.search("literacy and education", district_slug="multan")
        self.assertTrue(result)
        self.assertTrue(all(item["slug"] == "multan" for item in result))
        self.assertEqual(result[0]["category"], "education")

    def test_unknown_question_can_abstain(self):
        answer = generate_grounded_answer("weather forecast", [])
        self.assertEqual(answer["mode"], "abstained")
        self.assertEqual(answer["citations"], [])


if __name__ == "__main__":
    unittest.main()
