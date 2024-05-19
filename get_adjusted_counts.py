import json
import logging
import os
import time
from datetime import datetime
from decimal import Decimal
from urllib.parse import quote
from services.university_finder import finder
import polars as pl
import requests
from retrying import retry
from logging.handlers import TimedRotatingFileHandler

backoff_time_in_ms = 180000
backoff_time_in_seconds = 180
# backoff_time_in_ms = 60000
# backoff_time_in_seconds = 60
min_page_count = 6

# Configure logging
log_filename = f"{datetime.now().strftime('%Y-%m-%d')}-log"
log_filepath = os.path.join('logs', log_filename)
os.makedirs('logs', exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a TimedRotatingFileHandler
file_handler = TimedRotatingFileHandler(log_filepath, when='midnight', backupCount=7)
file_handler.setLevel(logging.INFO)

# Create a formatter and set it for the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the file handler to the logger
logger.addHandler(file_handler)


def generate_author_pub_count_api_url_with_year(author, year=None):
    publication_url = "https://dblp.uni-trier.de/search/publ/api"
    json_format = "&h=1000&format=json"
    formatted_author = f"?q={quote(author)}"
    if year:
        formatted_year = f"%20year%3A{year}%3A"
        return f"{publication_url}{formatted_author}{formatted_year}{json_format}"
    return f"{publication_url}{formatted_author}{json_format}"


def count_pages(page_range: str):
    try:
        if not page_range:
            return 1

        total_pages = 0
        page_ranges = page_range.split(',')

        for range_str in page_ranges:
            range_str = range_str.strip()

            if ':' in range_str and '-' in range_str:
                parts = range_str.split('-')
                if len(parts) != 2:
                    logger.warning(f"Invalid page range format: {range_str}")
                    continue

                start_page_parts = parts[0].split(':')
                end_page_parts = parts[1].split(':')

                if len(start_page_parts) != 2 or len(end_page_parts) != 2:
                    logger.warning(f"Invalid page range format: {range_str}")
                    continue

                start_page = start_page_parts[-1].strip()
                end_page = end_page_parts[-1].strip()
            elif '-' in range_str:
                parts = range_str.split('-')
                if len(parts) != 2:
                    logger.warning(f"Invalid page range format: {range_str}")
                    continue

                start_page, end_page = parts
                start_page = start_page.split(':')[-1].strip()
                end_page = end_page.split(':')[-1].strip()
            else:
                total_pages += 1
                continue

            # Convert roman numerals to integers if necessary
            start_page = convert_to_int(start_page)
            end_page = convert_to_int(end_page)

            # Calculate the number of pages in the current range
            num_pages = abs(end_page - start_page) + 1
            total_pages += num_pages

        return total_pages
    except Exception as e:
        logger.error(f"count_pages got this error: {e} - > args = {page_range}")
        return 1


def convert_to_int(page: str):
    try:
        return int(page)
    except ValueError:
        # Convert roman numerals to integers
        roman_numerals = {
            'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5,
            'vi': 6, 'vii': 7, 'viii': 8, 'ix': 9, 'x': 10,
            'xi': 11, 'xii': 12, 'xiii': 13, 'xiv': 14, 'xv': 15
        }
        return roman_numerals.get(page.lower(), 0)


def categorize_venue(venue: str) -> str | None:
    if not venue:
        return None

    # Check if venue is a list and convert it to a string
    if isinstance(venue, list):
        venue = ', '.join(venue)

    conferences = {
        'sys_arch': ['ASPLOS', 'ASPLOS (1)', 'ASPLOS (2)', 'ASPLOS (3)', 'ISCA', 'MICRO', 'MICRO (1)', 'MICRO (2)',
                     'HPCA'],
        'sys_net': ['SIGCOMM', 'NSDI'],
        'sys_sec': ['CCS', 'ACM Conference on Computer and Communications Security', 'USENIX Security',
                    'USENIX Security Symposium', 'NDSS', 'IEEE Symposium on Security and Privacy', 'SP', 'S&P'],
        'sys_db': ['SIGMOD Conference', 'VLDB', 'PVLDB', 'Proc. VLDB Endow.'],
        'sys_design': ['DAC', 'ICCAD'],
        'sys_embed': ['EMSOFT', 'RTAS', 'RTSS'],
        'sys_hpc': ['HPDC', 'ICS', 'SC'],
        'sys_mob': ['MobiSys', 'MobiCom', 'MOBICOM', 'SenSys'],
        'sys_mes': ['IMC', 'Internet Measurement Conference', 'Proc. ACM Meas. Anal. Comput. Syst.'],
        'sys_os': ['SOSP', 'OSDI', 'EuroSys', 'USENIX Annual Technical Conference',
                   'USENIX Annual Technical Conference, General Track', 'FAST'],
        'sys_pl': ['PLDI', 'POPL', 'ICFP', 'OOPSLA', 'OOPSLA/ECOOP'],
        'sys_se': ['SIGSOFT FSE', 'ESEC/SIGSOFT FSE', 'ICSE', 'ICSE (1)', 'ICSE (2)']
    }

    conf_short = {
        'sys_arch': ['ASPLOS', 'ISCA', 'MICRO', 'HPCA'],
        'sys_net': ['SIGCOMM', 'NSDI'],
        'sys_sec': ['CCS', 'USENIX Security', 'NDSS', 'Oakland'],
        'sys_db': ['SIGMOD', 'VLDB', 'ICDE', 'PODS'],
        'sys_design': ['DAC', 'ICCAD'],
        'sys_embed': ['EMSOFT', 'RTAS', 'RTSS'],
        'sys_hpc': ['HPDC', 'ICS', 'SC'],
        'sys_mob': ['MobiSys', 'MobiCom', 'SenSys'],
        'sys_mes': ['IMC', 'SIGMETRICS'],
        'sys_os': ['SOSP', 'OSDI', 'EuroSys', 'USENIX ATC', 'FAST'],
        'sys_pl': ['PLDI', 'POPL', 'ICFP', 'OOPSLA'],
        'sys_se': ['FSE', 'ICSE', 'ASE', 'ISSTA']
    }

    for area, confs in conf_short.items():
        for conf in confs:
            if venue.casefold() == conf.casefold():
                return area

    for area, confs in conferences.items():
        for conf in confs:
            if venue.casefold() == conf.casefold():
                return area

    return None


def update_dict_scores(result: dict, author: str, area_scores: str, this_hit_area: str,
                       this_hit_score: Decimal) -> None:
    try:
        if this_hit_area not in result[area_scores]:
            result[area_scores][this_hit_area] = 0

        result[area_scores][this_hit_area] = this_hit_score

        if this_hit_area not in result["authors"][author]:
            result["authors"][author][this_hit_area] = 0

        result["authors"][author][this_hit_area] = this_hit_score
    except KeyError as e:
        logger.error(f"update_dict_scores encountered an error: {e}")


def calculate_score(json_data: dict, school_result: dict, author: str):
    """
    Retrieves

    :param author:
    :param json_data:
    :param school_result: format = {
        'total_score': Decimal(0),
        'area_scores': {},
        'authors': {author: {} for author in authors}
    }
    """
    hits = json_data["result"]["hits"]
    hit_key_value = hits.get("hit", [])
    total_score = Decimal(0)

    for hit in hit_key_value:
        hit_info = hit["info"]
        page_range = hit_info.get("pages", "1")
        page_count = count_pages(page_range)

        this_hit_area = categorize_venue(hit_info.get("venue"))
        if not this_hit_area:
            continue

        if not page_count or page_count < min_page_count:
            continue

        this_hit_score = Decimal(0)
        hit_authors = hit_info.get("authors", None)
        if hit_authors:
            author_list = hit_authors["author"]
            num_authors = len(author_list)
            this_hit_score += Decimal(1) / Decimal(num_authors)

        update_dict_scores(
            result=school_result,
            author=author,
            area_scores="area_scores",
            this_hit_area=this_hit_area,
            this_hit_score=this_hit_score
        )
        total_score += this_hit_score
        school_result["total_score"] += total_score


def get_year_list() -> list:
    start = 1935
    current_year = datetime.now().year
    return list(range(start, current_year + 1))


def retry_if_429_error(exception):
    return isinstance(exception, requests.exceptions.RequestException) and exception.response.status_code == 429


def send_get_request(api_url: str) -> dict:
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes

        logger.info(f"Request URL: {api_url}")
        logger.info(f"Response code: {response.status_code}")

        if response.status_code == 200:
            return response.json()

    except requests.exceptions.RequestException as e:
        if e.response.status_code == 429:
            logger.info(f"Too Many Requests, retrying after {backoff_time_in_seconds} seconds.")
        else:
            logger.error(f"Error occurred during the request: {str(e)}")
        raise

    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


def author_has_less_than_1001_hits(url: str) -> tuple:
    json_data = send_get_request(url)
    hits = json_data["result"]["hits"]
    hit_key_value = hits.get("hit", [])
    return len(hit_key_value) < 1001, json_data


@retry(stop_max_attempt_number=3, wait_fixed=backoff_time_in_ms, retry_on_exception=retry_if_429_error)
def get_author_publication_score(author: str, school_result: dict):
    """
    Retrieves the publication score for a given author.

    :param school_result: format = {
        'total_score': Decimal(0),
        'area_scores': {},
        'authors': {author: {} for author in authors}
    }
    :param author: The name of the author.
    :return: The publication score as a Decimal value.
    """
    ex = "https://dblp.dagstuhl.de/search/publ/api?q=A.%20Aldo%20Faisal&h=1000&format=json"
    url = generate_author_pub_count_api_url_with_year(author)
    has_less_than_1001_hits, api_call_json = author_has_less_than_1001_hits(url)
    if has_less_than_1001_hits:
        calculate_score(api_call_json, school_result, author)
    else:
        for year in get_year_list():
            api_url = generate_author_pub_count_api_url_with_year(author, year=year)
            result = send_get_request(api_url)
            calculate_score(result, school_result, author)


def sum_dict_values(data: dict) -> Decimal:
    """
    Sums all the values from a dictionary and returns the result as a Decimal.

    :param data: The input dictionary.
    :return: The sum of all values as a Decimal.
    """
    total = Decimal(0)

    for value in data.values():
        if isinstance(value, (int, float, Decimal)):
            total += Decimal(value)
        else:
            raise ValueError(f"Unsupported value type: {type(value)}")

    return total


def calculate_institution_score(institution: str, df: pl.DataFrame) -> dict:
    logger.info(f"Calculating score for institution: {institution}")

    # Filter the DataFrame based on the institution
    filtered_series = df.filter(pl.col('affiliation') == institution)

    # Remove duplicate rows based on the 'scholarid' column
    filtered_series = filtered_series.unique(subset=['scholarid'])

    # Get all the authors for the institution
    authors = filtered_series['name'].to_list()

    institution_result = {
        'total_score': Decimal(0),
        'area_scores': {},
        'authors': {author: {} for author in authors}
    }

    for author in authors:
        logger.info(f"Retrieving publication score for author: {author}")
        get_author_publication_score(author, institution_result)

    # Sum up the scores of all authors for the institution
    total_score = Decimal(0)
    for author_scores in institution_result['authors'].values():
        total_score += sum_dict_values(author_scores)

    institution_result['total_score'] = total_score

    return institution_result


def generate_all_scores():
    logger.info("Generating scores for all institutions")
    df_cs_rankings = pl.read_csv(r'C:\Users\jmckerra\PycharmProjects\comp_sys_rankings_backend\files\csrankings.csv')

    # Get the unique values from the 'affiliation' column
    affiliations = df_cs_rankings['affiliation'].unique()

    # Convert the unique values to a set
    affiliations_set = set(affiliations)

    total_schools = len(affiliations_set)
    processed_schools = 0

    school_scores = {}
    for school in affiliations_set:
        if finder.search_university(school):
            school_score = calculate_institution_score(school, df_cs_rankings)
            school_scores[school] = school_score
            write_dict_to_file(data=school_scores, file_path="all-school-scores")

            processed_schools += 1
            percentage_completed = (processed_schools / total_schools) * 100
            logger.info(f"Processed {processed_schools} out of {total_schools} schools ({percentage_completed:.2f}%)")

    return school_scores


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def write_dict_to_file(data: dict, file_path: str) -> None:
    """
    Writes the contents of a dictionary to a file in JSON format, overwriting any existing content.

    :param data: The input dictionary.
    :param file_path: The path to the output file.
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, cls=DecimalEncoder, ensure_ascii=False, indent=4)
        logger.info(f"Successfully wrote data to file: {file_path}")
    except IOError as e:
        logger.error(f"An error occurred while writing to the file: {str(e)}")


def format_time(seconds):
    days = seconds // (24 * 3600)
    seconds %= (24 * 3600)
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return f"{int(days):02d}:{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"


def log_total_time_taken(start, end):
    execution_time = end - start
    formatted_time = format_time(execution_time)
    logger.info(f"Execution time of generate_all_scores(): {formatted_time} (days:hours:minutes:seconds)")


start_time = time.time()
all_school_scores = generate_all_scores()
end_time = time.time()

log_total_time_taken(start_time, end_time)
