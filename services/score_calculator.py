from decimal import Decimal
import logging
from datetime import datetime

from services.area_conference_mapping import categorize_venue
from services.page_counter import page_range_counter
from services.api_client_service import api_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScoreCalculator:
    def __init__(self, api_client):
        self.api_client = api_client

    def update_dict_scores(self, result: dict, author: str, area_scores: str, this_hit_area: str,
                           this_hit_score: Decimal, pub: str, pub_year: str) -> None:
        try:
            self.update_area_scores(result, area_scores, this_hit_area, this_hit_score)
            self.update_area_paper_counts(result, this_hit_area)
            self.update_author_area_score(result, author, this_hit_area, this_hit_score)
            self.update_author_paper_count(result, author)
            self.update_author_area_paper_counts(result, author, this_hit_area, this_hit_score, pub, pub_year)
        except KeyError as e:
            logger.error(f"update_dict_scores encountered an error: {e}")
            raise

    def update_area_scores(self, result: dict, area_scores: str, this_hit_area: str, this_hit_score: Decimal) -> None:
        if this_hit_area not in result[area_scores]:
            result[area_scores][this_hit_area] = 0
        result[area_scores][this_hit_area] += this_hit_score

    def update_area_paper_counts(self, result: dict, this_hit_area: str) -> None:
        if this_hit_area not in result['area_paper_counts']:
            result['area_paper_counts'][this_hit_area] = 0
        result['area_paper_counts'][this_hit_area] += 1

    def update_author_area_score(self, result: dict, author: str, this_hit_area: str, this_hit_score: Decimal) -> None:
        if this_hit_area not in result["authors"][author]:
            result["authors"][author][this_hit_area] = 0
        result["authors"][author][this_hit_area] += this_hit_score

    def update_author_paper_count(self, result: dict, author: str) -> None:
        result["authors"][author]["paper_count"] += 1

    def update_author_area_paper_counts(self, result: dict, author: str, this_hit_area: str, this_hit_score: Decimal,
                                        pub: str, pub_year: str) -> None:
        author_area_paper_counts = result["authors"][author]['area_paper_counts']
        if this_hit_area not in author_area_paper_counts:
            author_area_paper_counts[this_hit_area] = {}

        if 'area_adjusted_score' not in author_area_paper_counts[this_hit_area]:
            author_area_paper_counts[this_hit_area]['area_adjusted_score'] = 0
        author_area_paper_counts[this_hit_area]['area_adjusted_score'] += this_hit_score

        if pub not in author_area_paper_counts[this_hit_area]:
            author_area_paper_counts[this_hit_area][pub] = {}

        if pub_year not in author_area_paper_counts[this_hit_area][pub]:
            author_area_paper_counts[this_hit_area][pub][pub_year] = {'score': 0, 'year_paper_count': 0}

        author_area_paper_counts[this_hit_area][pub][pub_year]['score'] += this_hit_score
        author_area_paper_counts[this_hit_area][pub][pub_year]['year_paper_count'] += 1

    def calculate_score(self, json_data: dict, school_result: dict, author: str):
        hits = json_data["result"]["hits"]
        hit_key_value = hits.get("hit", [])
        total_score = Decimal(0)

        for hit in hit_key_value:
            hit_info = hit["info"]

            this_hit_area = self.get_hit_area(hit_info)
            if not this_hit_area:
                continue

            page_count = self.get_page_count(hit_info)
            if not self.is_valid_page_count(page_count):
                continue

            pub_year = hit_info.get('year', 0)
            this_hit_score = self.calculate_hit_score(hit_info)

            self.update_dict_scores(
                result=school_result,
                author=author,
                area_scores="area_scores",
                this_hit_area=this_hit_area,
                this_hit_score=this_hit_score,
                pub=hit_info.get("venue"),
                pub_year=pub_year
            )
            total_score += this_hit_score
            school_result["total_score"] += total_score

    def get_hit_area(self, hit_info: dict) -> str:
        return categorize_venue.categorize_venue(hit_info.get("venue"))

    def get_page_count(self, hit_info: dict) -> int:
        page_range = hit_info.get("pages", "1")
        return page_range_counter.count_pages(page_range)

    def is_valid_page_count(self, page_count: int) -> bool:
        return page_count and page_count >= self.api_client.min_page_count

    def calculate_hit_score(self, hit_info: dict) -> Decimal:
        this_hit_score = Decimal(0)
        hit_authors = hit_info.get("authors", None)
        if hit_authors:
            author_list = hit_authors["author"]
            num_authors = len(author_list)
            this_hit_score += Decimal(1) / Decimal(num_authors)
        return this_hit_score

    def get_author_publication_score(self, author: str, school_result: dict, school: str):
        school_result['authors'][author]['dblp_link'] = self.api_client.get_author_url(author)

        url = self.api_client.generate_author_pub_count_api_url_with_year(author)

        has_less_than_1001_hits, api_call_json = self.api_client.author_has_less_than_1001_hits(url, school, author)
        if has_less_than_1001_hits:
            self.calculate_score(api_call_json, school_result, author)

        elif api_call_json:
            for year in self.get_year_list():
                api_url = self.api_client.generate_author_pub_count_api_url_with_year(author, year=year)
                result = self.api_client.send_get_request(api_url, school, author)
                self.calculate_score(result, school_result, author)

        elif not has_less_than_1001_hits:
            self.api_client.missed_authors.add(f"{school.replace(' ', '-')} {author.replace(' ', '-')}")

    @staticmethod
    def get_year_list() -> list:
        start = 1935
        current_year = datetime.now().year
        return list(range(start, current_year + 1))


score_calc_service = ScoreCalculator(api_client=api_client)
