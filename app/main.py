import csv
import json
import logging
import sys
from dataclasses import dataclass, astuple, fields
from urllib.parse import urljoin
import requests

from bs4 import BeautifulSoup


BASE_URL = "https://jobs.dou.ua/companies/"
POST_URL = "xhr-load/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"


logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)


@dataclass
class CompanyData:
    url: str
    name: str
    size: str
    description: str
    website: str


def get_init_data(s: requests.Session) -> str:
    s.headers.update(
        {
            "user-agent": USER_AGENT,
            "referer": BASE_URL,
        }
    )

    response = s.get(BASE_URL, verify=True)
    soup = BeautifulSoup(response.content, "html.parser")
    csrf_middleware_token = soup.select_one("div.modal-wrap + script").next.text.split(";")[0].split("=")[1].strip().replace('"', "")
    return csrf_middleware_token


def get_detail_company(s: requests.Session, link: str) -> CompanyData:
    url = link
    response = s.get(link).content
    detail_soup = BeautifulSoup(response, "html.parser")
    name_tag = detail_soup.select_one("h1.g-h2")
    name = name_tag.text.strip() if name_tag else None
    size = name_tag.next_sibling.text.strip() if name_tag else None
    description_img = detail_soup.select_one(".b-typo img")
    description_text = detail_soup.select_one(".b-typo p")

    if description_img:
        description = description_img.get("src")
    elif description_text:
        description = description_text.text.replace("\u00a0", " ")
    else:
        description = None

    website_tag = detail_soup.select_one("div.site a")
    website = website_tag.get("href") if website_tag else None

    return CompanyData(url, name, size, description, website)


def get_twenty_companies(s: requests.Session, count: int, csrf_middleware_token: str) -> list[CompanyData] | bool:
    company_list = []
    payload = {
        "csrfmiddlewaretoken": csrf_middleware_token,
        "count": count
    }

    response = s.post(urljoin(BASE_URL, POST_URL), data=payload).content
    if json.loads(response)["num"] > 0:
        soup = BeautifulSoup(json.loads(response)["html"], "html.parser")
        detail_links = soup.select("a.logo")
        for detail_link in detail_links:
            company_list.append(get_detail_company(s, detail_link.get("href")))
        return company_list
    return False


def write_csv_file(
        file_name: str,
        all_content: list[CompanyData]
) -> None:
    with open(file_name, "w", encoding="utf-8", newline="") as csvfile:
        object_writer = csv.writer(csvfile)
        object_writer.writerow([field.name for field in fields(CompanyData)])
        object_writer.writerows([astuple(content) for content in all_content])


def parse_all_companies() -> None:
    logging.info("Start parse...")
    all_companies = []
    s = requests.Session()
    data = get_init_data(s)
    count = 0
    while True:
        logging.info(f"Parse company count {count} ...")
        companies = get_twenty_companies(s, count, data)
        if companies:
            all_companies += companies
            count += 20
        else:
            break
    logging.info("Write csv file...")
    write_csv_file("companies.csv", all_companies)
    logging.info("End parse.")


if __name__ == '__main__':
    parse_all_companies()
