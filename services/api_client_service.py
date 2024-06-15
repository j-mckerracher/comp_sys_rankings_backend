import logging
from urllib.parse import quote
from retrying import retry
import requests
from services.api_json_keys import api_keys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


backoff_time_in_ms = 180000


def retry_if_429_error(exception):
    if isinstance(exception, requests.exceptions.RequestException):
        if exception.response is not None:
            return exception.response.status_code == 429
        else:
            return False
    return False


class APIClient:
    def __init__(self):
        self.backoff_time_in_ms = 180000
        self.backoff_time_in_seconds = 180
        self.min_page_count = 12
        self.missed_authors = set()
        self.retry_interval_seconds = 600

    def generate_author_pub_count_api_url_with_year(self, author, year=None):
        publication_url = "https://dblp.uni-trier.de/search/publ/api"
        json_format = "&h=1000&format=json"
        formatted_author = f"?q={quote(author)}"
        if year:
            formatted_year = f"%20year%3A{year}%3A"
            return f"{publication_url}{formatted_author}{formatted_year}{json_format}"
        return f"{publication_url}{formatted_author}{json_format}"

    @retry(stop_max_attempt_number=3, wait_fixed=backoff_time_in_ms, retry_on_exception=retry_if_429_error)
    def send_get_request(self, api_url: str, school, author) -> dict | None:
        try:
            response = requests.get(api_url)
            response.raise_for_status()

            if response.status_code == 200:
                return response.json()

        except requests.exceptions.RequestException as e:
            if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
                if e.response.status_code == 429:
                    logger.info(f"Too Many Requests, retrying after {self.backoff_time_in_seconds} seconds.")
                elif e.response.status_code == 500:
                    logger.error(f"Internal Server Error (500) occurred for URL: {api_url}")
                    self.missed_authors.add(f"{school.replace(' ', '-')} {author.replace(' ', '-')}")
                    return {}
                elif e.response.status_code == 413:
                    logger.error(f"Payload Too Large! {e}")
                    self.missed_authors.add(f"{school.replace(' ', '-')} {author.replace(' ', '-')}")
                    return {}
                else:
                    logger.error(f"Error occurred during the request: {str(e)}")
            else:
                logger.error(f"Error occurred during the request: {str(e)}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}")
            raise

    def author_has_less_than_1001_hits(self, url: str, school: str, author: str) -> tuple:
        json_data = self.send_get_request(url, school, author)
        result = None
        if json_data:
            hits = json_data[api_keys.RESULT][api_keys.HITS]
            hit_key_value = hits.get(api_keys.HIT, [])
            if len(hit_key_value) < 1001:
                result = True

        return result, json_data

    def generate_author_search_api_url(self, author: str) -> str:
        base_url = "https://dblp.dagstuhl.de/search/author/api"
        formatted_author = quote(author)
        json_format = "&h=1000&format=json"
        return f"{base_url}?q={formatted_author}{json_format}"

    def get_author_url(self, author):
        api_url = self.generate_author_search_api_url(author)
        response_data = self.send_get_request(api_url, "", author)

        if response_data:
            hits = response_data.get(api_keys.RESULT, {}).get(api_keys.HITS, {}).get(api_keys.HIT, [])
            if hits:
                hit = hits[0]
                if api_keys.INFO in hit:
                    info = hit[api_keys.INFO]
                    if api_keys.URL in info:
                        return info[api_keys.URL]

        return None


api_client = APIClient()
