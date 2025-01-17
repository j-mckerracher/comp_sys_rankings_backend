import logging
import time
from services.score_generator import score_generator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run():
    start_time = time.time()

    # get all school scores
    all_school_scores = score_generator.generate_all_scores()

    # get the missed authors data until missed_authors is empty
    score_generator.retry_missed_authors(all_school_scores)

    # adds the author count key to all_school_scores
    score_generator.add_author_count(all_school_scores)

    end_time = time.time()
    score_generator.log_total_time_taken(start_time, end_time)


run()
