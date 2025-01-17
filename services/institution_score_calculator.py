from decimal import Decimal
import polars as pl
import logging

from services.api_client_service import api_client
from services.score_calculator import score_calc_service
from services.dict_keys import json_keys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InstitutionScoreCalculator:
    def __init__(self, api_client, score_calculator):
        self.api_client = api_client
        self.score_calculator = score_calculator

    @staticmethod
    def sum_dict_values(data: dict) -> Decimal:
        total = Decimal(0)

        for value in data.values():
            if isinstance(value, (int, float, Decimal)):
                total += Decimal(value)
            else:
                raise ValueError(f"Unsupported value type: {type(value)}")

        return total

    @staticmethod
    def get_filtered_dict(input_dict: dict, remove_keys: list):
        filtered_dict = {}
        for key, value in input_dict.items():
            if key not in remove_keys:
                filtered_dict[key] = value
        return filtered_dict

    def calculate_institution_score(self, institution: str, df: pl.DataFrame) -> dict:
        logger.info(f"Calculating score for institution: {institution}")

        filtered_series = df.filter(pl.col('affiliation') == institution)
        filtered_series = filtered_series.unique(subset=['scholarid'])
        authors = filtered_series['name'].to_list()

        institution_result = {
            json_keys.TOTAL_SCORE: Decimal(0),
            json_keys.AREA_SCORES: {},
            json_keys.AREA_PAPER_COUNTS: {},
            json_keys.AUTHORS: {author: {json_keys.DBLP_LINK: '', json_keys.PAPER_COUNT: 0, json_keys.AREA_PAPER_COUNTS: {}} for author in authors}
        }

        for author in authors:
            self.score_calculator.get_author_publication_score(author, institution_result, institution)

        total_score = Decimal(0)
        for author_scores in institution_result[json_keys.AUTHORS].values():
            scores = self.get_filtered_dict(
                author_scores,
                [json_keys.AREA_PAPER_COUNTS, json_keys.PAPER_COUNT, json_keys.DBLP_LINK]
            )
            total_score += self.sum_dict_values(scores)

        institution_result[json_keys.TOTAL_SCORE] = total_score

        return institution_result


school_score_calculator = InstitutionScoreCalculator(
    api_client=api_client,
    score_calculator=score_calc_service
)
