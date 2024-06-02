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
from area_conference_mapping import categorize_venue
from services.page_counter import page_range_counter

# global variables
backoff_time_in_ms = 180000
backoff_time_in_seconds = 180
min_page_count = 12
missed_authors = set()
retry_interval_seconds = 600

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


def delete_current_day_log_files():
    log_directory = 'logs'
    current_date = datetime.now().strftime('%Y-%m-%d')
    log_filename_pattern = f"{current_date}-log"

    try:
        # Iterate over the files in the 'logs' directory
        for filename in os.listdir(log_directory):
            file_path = os.path.join(log_directory, filename)

            # Check if the file is a regular file and matches the current day's log filename pattern
            if os.path.isfile(file_path) and filename.startswith(log_filename_pattern):
                os.remove(file_path)
                print(f"Deleted log file: {filename}")

    except FileNotFoundError:
        print(f"The 'logs' directory does not exist.")

    except Exception as e:
        print(f"An error occurred while deleting log files: {str(e)}")


def generate_author_pub_count_api_url_with_year(author, year=None):
    publication_url = "https://dblp.uni-trier.de/search/publ/api"
    json_format = "&h=1000&format=json"
    formatted_author = f"?q={quote(author)}"
    if year:
        formatted_year = f"%20year%3A{year}%3A"
        return f"{publication_url}{formatted_author}{formatted_year}{json_format}"
    return f"{publication_url}{formatted_author}{json_format}"



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


def update_dict_scores(result: dict, author: str, area_scores: str, this_hit_area: str,
                       this_hit_score: Decimal, pub: str, pub_year: str) -> None:
    try:
        # TODO move to a later point after all authors in a school have been done
        if this_hit_area not in result[area_scores]:
            result[area_scores][this_hit_area] = 0

        result[area_scores][this_hit_area] += this_hit_score

        if this_hit_area not in result['area_paper_counts']:
            result['area_paper_counts'][this_hit_area] = 0

        result['area_paper_counts'][this_hit_area] += 1
        # TODO move to a later point after all authors in a school have been done

        # update author pub category score
        if this_hit_area not in result["authors"][author]:
            result["authors"][author][this_hit_area] = 0
        result["authors"][author][this_hit_area] += this_hit_score

        # update author total pub count
        result["authors"][author]["paper_count"] += 1

        # update author pub category score
        if this_hit_area not in result["authors"][author]['area_paper_counts']:
            result["authors"][author]['area_paper_counts'][this_hit_area] = {}

        if 'area_adjusted_score' not in result["authors"][author]['area_paper_counts'][this_hit_area]:
            result["authors"][author]['area_paper_counts'][this_hit_area]['area_adjusted_score'] = 0

        result["authors"][author]['area_paper_counts'][this_hit_area]['area_adjusted_score'] += this_hit_score

        if pub not in result["authors"][author]['area_paper_counts'][this_hit_area]:
            result["authors"][author]['area_paper_counts'][this_hit_area][pub] = {}

        if pub_year not in result["authors"][author]['area_paper_counts'][this_hit_area][pub]:
            result["authors"][author]['area_paper_counts'][this_hit_area][pub][pub_year] = {}

        if 'score' not in result["authors"][author]['area_paper_counts'][this_hit_area][pub][pub_year]:
            result["authors"][author]['area_paper_counts'][this_hit_area][pub][pub_year]['score'] = 0

        result["authors"][author]['area_paper_counts'][this_hit_area][pub][pub_year]['score'] += this_hit_score

        if 'year_paper_count' not in result["authors"][author]['area_paper_counts'][this_hit_area][pub][pub_year]:
            result["authors"][author]['area_paper_counts'][this_hit_area][pub][pub_year]['year_paper_count'] = 0

        result["authors"][author]['area_paper_counts'][this_hit_area][pub][pub_year]['year_paper_count'] += 1

    except KeyError as e:
        logger.error(f"update_dict_scores encountered an error: {e}")
        raise


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

        this_hit_area = categorize_venue.categorize_venue(hit_info.get("venue"))
        if not this_hit_area:
            continue

        page_range = hit_info.get("pages", "1")
        page_count = page_range_counter.count_pages(page_range)

        if not page_count or page_count < min_page_count:
            continue

        pub_year = hit_info.get('year', 0)
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
            this_hit_score=this_hit_score,
            pub=hit_info.get("venue"),
            pub_year=pub_year
        )
        total_score += this_hit_score
        school_result["total_score"] += total_score


def get_year_list() -> list:
    start = 1935
    current_year = datetime.now().year
    return list(range(start, current_year + 1))


def retry_if_429_error(exception):
    if isinstance(exception, requests.exceptions.RequestException):
        if exception.response is not None:
            return exception.response.status_code == 429
        else:
            # Handle the case when response is None
            return False
    return False


@retry(stop_max_attempt_number=3, wait_fixed=backoff_time_in_ms, retry_on_exception=retry_if_429_error)
def send_get_request(api_url: str, school, author) -> dict | None:
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes

        if response.status_code == 200:
            return response.json()

    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
            if e.response.status_code == 429:
                logger.info(f"Too Many Requests, retrying after {backoff_time_in_seconds} seconds.")
            elif e.response.status_code == 500:
                logger.error(f"Internal Server Error (500) occurred for URL: {api_url}")
                missed_authors.add(f"{school.replace(' ', '-')} {author.replace(' ', '-')}")
                return {}  # Return an empty dictionary to skip processing the response
            elif e.response.status_code == 413:
                logger.error(f"Payload Too Large! {e}")
                missed_authors.add(f"{school.replace(' ', '-')} {author.replace(' ', '-')}")
                return {}
            else:
                logger.error(f"Error occurred during the request: {str(e)}")
        else:
            logger.error(f"Error occurred during the request: {str(e)}")
        raise

    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise


def author_has_less_than_1001_hits(url: str, school: str, author: str) -> tuple:
    json_data = send_get_request(url, school, author)
    result = None
    if json_data:
        hits = json_data["result"]["hits"]
        hit_key_value = hits.get("hit", [])
        if len(hit_key_value) < 1001:
            result = True

    return result, json_data


def get_author_publication_score(author: str, school_result: dict, school: str):
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
    url = generate_author_pub_count_api_url_with_year(author)

    # if the author has less than 1001 pubs, only 1 API call is needed
    has_less_than_1001_hits, api_call_json = author_has_less_than_1001_hits(url, school, author)
    if has_less_than_1001_hits:
        calculate_score(api_call_json, school_result, author)

    # otherwise call the DBLP API once for each year for the same author's pubs
    elif api_call_json:
        for year in get_year_list():
            api_url = generate_author_pub_count_api_url_with_year(author, year=year)
            result = send_get_request(api_url, school, author)
            calculate_score(result, school_result, author)

    elif not has_less_than_1001_hits:
        missed_authors.add(f"{school.replace(' ', '-')} {author.replace(' ', '-')}")


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


def get_filtered_dict(input_dict: dict, remove_keys: list):
    filtered_dict = {}
    for key, value in input_dict.items():
        if key not in remove_keys:
            filtered_dict[key] = value
    return filtered_dict


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
        'area_paper_counts': {},
        'authors': {author: {'paper_count': 0, 'area_paper_counts': {}} for author in authors}
    }

    for author in authors:
        get_author_publication_score(author, institution_result, institution)

    # Sum up the scores of all authors for the institution
    total_score = Decimal(0)
    for author_scores in institution_result['authors'].values():
        scores = get_filtered_dict(
            author_scores,
            ['area_paper_counts', 'paper_count']
        )
        total_score += sum_dict_values(scores)

    institution_result['total_score'] = total_score

    return institution_result


def generate_all_scores():
    logger.info("Generating scores for all institutions")
    df_cs_rankings = pl.read_csv(r'C:\Users\jmckerra\PycharmProjects\comp_sys_rankings_backend\files\csrankings.csv')

    # Get the unique values from the 'affiliation' column
    affiliations = df_cs_rankings['affiliation'].unique()

    # Convert the unique values to a set
    prelim_affiliations_set = set(affiliations)
    affiliations_set = {uni for uni in prelim_affiliations_set if finder.search_university(uni)}
    clean_data(affiliations_set)

    total_schools = len(affiliations_set)
    processed_schools = 0

    school_scores = {}
    for school in affiliations_set:
        school_score = calculate_institution_score(school, df_cs_rankings)
        school_scores[school] = school_score
        write_dict_to_file(data=school_scores, file_path="old-scores/all-school-scores")

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


def get_month_day_year():
    now = datetime.now()
    return now.strftime("%B-%d-%Y")


def add_author_count(_data):
    new_data = {}
    for school, info in _data.items():
        author_count = len(info["authors"])
        new_info = info.copy()  # Create a copy to avoid modifying the original data
        new_info["author_count"] = author_count
        new_data[school] = new_info

    write_dict_to_file(data=new_data, file_path=f"all-school-scores-final-{get_month_day_year()}")


def clean_data(_data: set):
    remove_list = ["HUST", "UFF", "UNSW", "Heidelberg University", "JUST", "CMI"]
    for item in remove_list:
        if item in _data:
            _data.remove(item)


def log_total_time_taken(start, end):
    execution_time = end - start
    formatted_time = format_time(execution_time)
    logger.info(f"Execution time of generate_all_scores(): {formatted_time} (days:hours:minutes:seconds)")


def retry_missed_authors(school_scores):
    iteration = 0
    try:
        while missed_authors and iteration < 16:
            iteration += 1
            for entry in missed_authors.copy():
                school, author = entry.split(' ', 2)
                school = school.replace('-', ' ')
                author = author.replace('-', ' ')
                url = generate_author_pub_count_api_url_with_year(author)
                result = send_get_request(url, school, author)
                if result:
                    if author not in school_scores[school]['authors']:
                        school_scores[school]['authors'][author] = {'paper_count': 0, 'area_paper_counts': {}}
                    calculate_score(result, school_scores[school], author)
                    missed_authors.remove(entry)
            if len(missed_authors) > 0:
                logger.info(f"Iteration: {iteration} -> missed = {missed_authors}")
                time.sleep(retry_interval_seconds)
    except Exception as e:
        logger.error(f"retry_missed_authors got this error: {e}")


def run():
    start_time = time.time()

    # get all school scores
    all_school_scores = generate_all_scores()

    # get the missed authors data until missed_authors is empty
    logger.info(f"Missed authors: {missed_authors}")
    retry_missed_authors(all_school_scores)

    # adds the author count key to all_school_scores
    add_author_count(all_school_scores)

    end_time = time.time()
    log_total_time_taken(start_time, end_time)


run()
