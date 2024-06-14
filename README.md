# Institution Score Calculator - CompSysRankings Backend

This code calculates scores for institutions based on author publication data from the DBLP (Digital Bibliography & Library Project) database. It retrieves publication information for authors affiliated with various institutions, categorizes the publications into different areas, and calculates scores based on the number of publications and co-authors.

## Features

- Retrieves author publication data from the DBLP API
- Categorizes publications into different areas based on venue
- Calculates scores for authors and institutions based on publication counts and co-authorship
- Handles API rate limiting and retries for missed authors
- Generates a JSON file with the calculated scores for each institution

## Prerequisites

- Python 3.x
- Required dependencies (listed in `requirements.txt`)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/j-mckerracher/comp_sys_rankings_backend.git
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Prepare the input CSV file:
   - The input CSV file should contain institution and author information. The file used here comes from CSRankings.org
   - The file should have columns: `affiliation`, `name`, and `scholarid`.
   - Update the file path in the `generate_all_scores()` function of the `ScoreGenerator` class.

2. Run the script:
   ```
   python institution_score_calculator.py
   ```

3. The script takes roughly 12 hours and will retrieve publication data from the DBLP API, calculate scores for each institution, and generate a JSON file with the results.

4. The output JSON file will be saved as `all-school-scores-final-<date>.json`, where `<date>` is the current date in the format "Month-Day-Year".

## Code Structure

The code is organized into several classes based on their responsibilities:

- `APIClient`: Handles API requests and related utility functions.
- `ScoreCalculator`: Calculates scores for individual authors and updates the institution results dictionary.
- `InstitutionScoreCalculator`: Calculates scores for institutions by filtering data and calling the `ScoreCalculator`.
- `ScoreGenerator`: Generates scores for all institutions, handles retrying missed authors, and performs additional data manipulation and logging.

The `run()` function in the script creates instances of these classes and orchestrates the overall execution flow.

## JSON Structure
The generated JSON file has the following structure:
```json
{
  "Institution 1": {
    "total_score": number,
    "area_scores": {
      "area_1": number,
      "area_2": number,
      ...
    },
    "area_paper_counts": {
      "area_1": number,
      "area_2": number,
      ...
    },
    "authors": {
      "Author 1": {
        "dblp_link": string,
        "paper_count": number,
        "area_paper_counts": {
          "area_1": {
            "area_adjusted_score": number,
            "Venue 1": {
              "Year 1": {
                "score": number,
                "year_paper_count": number
              },
              "Year 2": {
                "score": number,
                "year_paper_count": number
              },
              ...
            },
            "Venue 2": {
              ...
            },
            ...
          },
          "area_2": {
            ...
          },
          ...
        },
        "area_1_score": number,
        "area_2_score": number,
        ...
      },
      "Author 2": {
        ...
      },
      ...
    }
  },
  "Institution 2": {
    ...
  },
  ...
}
```

### The JSON file is structured as follows

- The <strong>top-level object</strong> represents the entire dataset, with each key being an institution name and its corresponding value being an object containing the institution's data.
Each institution object contains the following fields:

- <strong>total_score</strong>: The total score of the institution (number).
- <strong>area_scores</strong>: An object where each key is an research area and its corresponding value is the institution's score in that area (number).
- <strong>area_paper_counts</strong>: An object where each key is a research area and its corresponding value is the number of papers published by the institution in that area (number).
- <strong>authors</strong>: An object representing the authors affiliated with the institution.


#### Each author object within the authors field contains the following fields

- <strong>dblp_link</strong>: The URL to the author's DBLP profile (string).
- <strong>paper_count</strong>: The total number of papers published by the author (number).
- <strong>area_paper_counts</strong>: An object where each key is a research area and its corresponding value is an object containing the author's paper counts and scores in that area.

#### Each area object within area_paper_counts contains

- <strong>area_adjusted_score</strong>: The author's adjusted score in that area (number).
- <strong>Venue objects</strong>: Each key is a venue name and its corresponding value is an object containing the years and scores of the author's papers published in that venue.

#### Each year object within a venue object contains

- <strong>score</strong>: The author's score for papers published in that venue and year (number).
- <strong>year_paper_count</strong>: The number of papers published by the author in that venue and year (number). 
- <strong>area_1_score, area_2_score, etc.</strong>: The author's score in each research area (number).

This JSON structure allows for easy parsing and analysis of the institution and author data, including total scores, area-specific scores, paper counts, and detailed information about each author's publications in different venues and years.

## Contributing

We welcome contributions. If you would like to contribute, please follow these steps:

1. Fork the repository
2. Create a new branch for your changes
3. Make your changes and commit them to your branch
4. Create a pull request to merge your changes into the main repository

Please ensure that your contributions adhere to the license terms and do not introduce any commercial or derivative elements.

## Feedback and Support

If you have any feedback, suggestions, or issues, please [open an issue](https://github.com/j-mckerracher/comp_sys_rankings_backend/issues) on the GitHub repository. We appreciate your input and will strive to address any concerns in a timely manner.

## License

This code is covered by the Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License. You are free to use and share the code for non-commercial purposes, but you must give appropriate credit, provide a link to the license, and indicate if changes were made. You may not use the code for commercial purposes or create derivatives of the code without permission.

For more information, please see the [Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License](https://creativecommons.org/licenses/by-nc-nd/4.0/).

## Acknowledgements

This script utilizes data from the DBLP (Digital Bibliography & Library Project) database and CSRankings. We acknowledge and appreciate their efforts.

## Contact

If you have any questions or suggestions regarding this script, please feel free to contact Josh McKerracher at [compsysrankings@gmail.com](mailto:compsysrankings@gmail.com)