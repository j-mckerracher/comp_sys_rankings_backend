import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PageNumberConverter:
    @staticmethod
    def convert_to_int(page: str):
        try:
            return int(page)
        except ValueError:
            roman_numerals = {
                'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5,
                'vi': 6, 'vii': 7, 'viii': 8, 'ix': 9, 'x': 10,
                'xi': 11, 'xii': 12, 'xiii': 13, 'xiv': 14, 'xv': 15
            }
            return roman_numerals.get(page.lower(), 0)


class PageNumberExtractor:
    @staticmethod
    def extract_page_number(page_str: str) -> str:
        match = re.search(r'(\d+)', page_str)
        return match.group(1) if match else page_str


class PageRangeCounter:
    def __init__(self, page_number_converter: PageNumberConverter, page_number_extractor: PageNumberExtractor):
        self.page_number_converter = page_number_converter
        self.page_number_extractor = page_number_extractor

    def count_pages(self, page_range: str):
        try:
            if not page_range:
                return 1
            total_pages = 0
            page_ranges = page_range.split(',')

            for range_str in page_ranges:
                range_str = range_str.strip()

                if '-' in range_str:
                    start_page, end_page = self.extract_start_end_pages(range_str)
                    if start_page is None or end_page is None:
                        continue
                else:
                    total_pages += 1
                    continue

                start_page = self.page_number_converter.convert_to_int(start_page)
                end_page = self.page_number_converter.convert_to_int(end_page)

                if start_page > end_page:
                    logger.warning(f"Invalid page range format: {range_str}. args = {page_range}")
                    continue

                num_pages = abs(end_page - start_page) + 1
                total_pages += num_pages

            return total_pages
        except Exception as e:
            logger.error(f"count_pages got this error: {e} - > args = {page_range}")
            return 1

    def extract_start_end_pages(self, range_str: str) -> tuple:
        parts = range_str.split('-')
        if len(parts) == 3 and ':' in parts[0] and ':' in parts[2]:
            return self.extract_pages_with_colons(parts)
        elif len(parts) == 2 and ': ' in parts[0] and ':' not in parts[1]:
            return self.extract_pages_with_colon_space(parts)
        elif len(parts) == 4 and parts[0].isalpha() and parts[2].isalpha():
            return parts[1], parts[3]
        else:
            return self.extract_pages_without_special_chars(parts)

    def extract_pages_with_colons(self, parts: list) -> tuple:
        left_start_index = parts[0].index(':') + 1
        right_start_index = parts[2].index(':') + 1
        start_page = parts[0][left_start_index:]
        end_page = parts[2][right_start_index:]
        return start_page, end_page

    def extract_pages_with_colon_space(self, parts: list) -> tuple:
        start_index = parts[0].index(':') + 1
        start_page = parts[0][start_index:].strip()
        end_page = parts[1].strip()
        return start_page, end_page

    def extract_pages_without_special_chars(self, parts: list) -> tuple:
        start_page = self.page_number_extractor.extract_page_number(parts[0].strip())
        end_page = self.page_number_extractor.extract_page_number(parts[1].strip())
        return start_page, end_page


page_number_converter = PageNumberConverter()
page_number_extractor = PageNumberExtractor()
page_range_counter = PageRangeCounter(page_number_converter, page_number_extractor)