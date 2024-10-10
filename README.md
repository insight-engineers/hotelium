# Hotelium

Hotelium is a Python package designed for crawling hotel data from *Booking.com, TripAdvisor, Agoda,...*. It leverages Selenium and BeautifulSoup4 for web scraping.

## Features

- Crawl hotel data from *Booking.com, TripAdvisor, Agoda,...*
- Extract useful information using BeautifulSoup4.
- Automate browser interactions with Selenium.

## Usage

To start crawling, run the following command:

```bash
# site: booking, tripadvisor, agoda
hotelium crawl --site booking --city "Hanoi" --checkin "2021-12-01" --checkout "2021-12-02"
hotelium crawl --site tripadvisor --city "Hanoi" --checkin "2021-12-01" --checkout "2021-12-02"
hotelium crawl --site agoda --city "Hanoi" --checkin "2021-12-01" --checkout "2021-12-02"

# output: json file
```

## Development

To install the development environment, use [Poetry](https://python-poetry.org/):

```bash
# Install Poetry if you haven't already
curl -sSL https://install.python-poetry.org | python3 -

# Navigate to the project directory
git clone https://github.com/insight-engineers/hotelium.git
cd hotelium

# Install dependencies
poetry install
```

## Dependencies

- Python ^3.9
- Selenium
- BeautifulSoup4

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
```