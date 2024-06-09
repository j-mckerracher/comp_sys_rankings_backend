import time
import logging
import json
import polars as pl
from datetime import datetime

from services.university_finder import finder
from services.decimal_encoder import DecimalEncoder
from services.api_client_service import api_client
from services.score_calculator import score_calc_service
from services.institution_score_calculator import school_score_calculator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScoreGenerator:
    def __init__(self, api_client, score_calculator, institution_score_calculator):
        self.api_client = api_client
        self.score_calculator = score_calculator
        self.institution_score_calculator = institution_score_calculator

    def generate_all_scores(self):
        logger.info("Generating scores for all institutions")
        df_cs_rankings = pl.read_csv(r'C:\Users\jmckerra\PycharmProjects\comp_sys_rankings_backend\files\csrankings.csv')

        affiliations = df_cs_rankings['affiliation'].unique()
        prelim_affiliations_set = set(affiliations)
        affiliations_set = {uni for uni in prelim_affiliations_set if finder.search_university(uni)}
        self.clean_data(affiliations_set)

        total_schools = len(affiliations_set)
        processed_schools = 0

        school_scores = {}
        for school in affiliations_set:
            school_score = self.institution_score_calculator.calculate_institution_score(school, df_cs_rankings)
            school_scores[school] = school_score
            self.write_dict_to_file(data=school_scores, file_path="all-school-scores")

            processed_schools += 1
            percentage_completed = (processed_schools / total_schools) * 100
            logger.info(f"Processed {processed_schools} out of {total_schools} schools ({percentage_completed:.2f}%)")

        return school_scores

    @staticmethod
    def clean_data(_data: set):
        remove_list = ["HUST", "UFF", "UNSW", "Heidelberg University", "JUST", "CMI"]
        for item in remove_list:
            if item in _data:
                _data.remove(item)

    @staticmethod
    def write_dict_to_file(data: dict, file_path: str) -> None:
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, cls=DecimalEncoder, ensure_ascii=False, indent=4)
            logger.info(f"Successfully wrote data to file: {file_path}")
        except IOError as e:
            logger.error(f"An error occurred while writing to the file: {str(e)}")

    @staticmethod
    def add_author_count(_data):
        new_data = {}
        for school, info in _data.items():
            author_count = len(info["authors"])
            new_info = info.copy()
            new_info["author_count"] = author_count
            new_data[school] = new_info

        ScoreGenerator.write_dict_to_file(data=new_data, file_path=f"all-school-scores-final-{ScoreGenerator.get_month_day_year()}.json")

    @staticmethod
    def get_month_day_year():
        now = datetime.now()
        return now.strftime("%B-%d-%Y")

    @staticmethod
    def log_total_time_taken(start, end):
        execution_time = end - start
        formatted_time = ScoreGenerator.format_time(execution_time)
        logger.info(f"Execution time of generate_all_scores(): {formatted_time} (days:hours:minutes:seconds)")

    @staticmethod
    def format_time(seconds):
        days = seconds // (24 * 3600)
        seconds %= (24 * 3600)
        hours = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60
        return f"{int(days):02d}:{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

    def retry_missed_authors(self, school_scores):
        iteration = 0
        try:
            while self.api_client.missed_authors and iteration < 16:
                iteration += 1
                for entry in self.api_client.missed_authors.copy():
                    school, author = entry.split(' ', 2)
                    school = school.replace('-', ' ')
                    author = author.replace('-', ' ')
                    url = self.api_client.generate_author_pub_count_api_url_with_year(author)
                    result = self.api_client.send_get_request(url, school, author)
                    if result:
                        if school not in school_scores:
                            logger.info(f"retry_missed_authors added this school: {school}")
                            school_scores[school] = {}
                        if author not in school_scores[school]['authors']:
                            logger.info(f"retry_missed_authors added this author: {author}")
                            school_scores[school]['authors'][author] = {'paper_count': 0, 'area_paper_counts': {}}
                        self.score_calculator.calculate_score(result, school_scores[school], author)
                        self.api_client.missed_authors.remove(entry)
                if len(self.api_client.missed_authors) > 0:
                    logger.info(f"Iteration: {iteration} -> missed = {self.api_client.missed_authors}")
                    time.sleep(self.api_client.retry_interval_seconds)
        except Exception as e:
            logger.error(f"retry_missed_authors got this error: {e}")


score_generator = ScoreGenerator(
    api_client=api_client,
    score_calculator=score_calc_service,
    institution_score_calculator=school_score_calculator
)