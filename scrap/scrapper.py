import requests
from bs4 import BeautifulSoup

url = "https://www.cardmarket.com/en/Pokemon"
req = requests.get(url)
soup = BeautifulSoup(req.content, "html.parser")

print(soup.prettify())