import requests
from bs4 import BeautifulSoup

import pprint, logging

logger = logging.getLogger("business_hours_extractor")
logger.setLevel(logging.DEBUG)

pp = pprint.PrettyPrinter(indent=2)


def extract_business_hours():
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; System x86_64) AppleWebKit/537.123 (KHTML, like Gecko) Chrome/100.0.111.111 Safari/537.123"
    }

    params = {
        "q": "hestia austin hours",
        "hl": "en",
    }

    response = requests.get(
        "https://www.google.com/search", headers=headers, params=params
    )

    soup = BeautifulSoup(response.text, "lxml")

    logger.debug(f"Write file for debugging: {params['q']}.html")
    with open(f"{params['q']}.html", "w") as f:
        f.write(response.text)

    hours_wrapper_node = soup.select_one("[data-attrid='kc:/location/location:hours']")

    if hours_wrapper_node is None:
        logger.info("Business hours node is not found")
        return

    business_hours = {"open_closed_state": "", "hours": []}

    business_hours["open_closed_state"] = hours_wrapper_node.select_one(
        ".JjSWRd span span span"
    ).text.strip()

    location_hours_rows_nodes = hours_wrapper_node.select("table tr")
    for location_hours_rows_node in location_hours_rows_nodes:
        [day_of_week, hours] = [
            td.text.strip() for td in location_hours_rows_node.select("td")
        ]

        business_hours["hours"].append(
            {"day_of_week": day_of_week, "business_hours": hours}
        )

    return business_hours


def main():
    logging.basicConfig(level=logging.DEBUG)

    result = extract_business_hours()

    logger.info(f"Business hours: {pp.pformat(result)}")


main()
