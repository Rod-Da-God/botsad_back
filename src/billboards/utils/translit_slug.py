from slugify import slugify


def translit_address(city: str, name: str) -> str:
    """
    Формирует чистый URL-slug: город/улица-дом

    Примеры:
         translit_address("Хабаровск", "ул. Краснореченская 92")
            → "khabarovsk/ul-krasnorechenskaia-92"

        translit_address("Москва", "пр-т Ленина 5")
            → "moskva/pr-t-lenina-5"

        translit_address("Санкт-Петербург", "шоссе Революции 14")
            → "sankt-peterburg/shosse-revoliutsii-14"

        translit_address("Нижний Новгород", "мкр. Северный 12")
            → "nizhnii-novgorod/mkr-severnyi-12"

    """
    if not city or not name:
        return ""

    city_slug = slugify(city.strip(), separator="-", lowercase=True)

    street_slug = slugify(name.strip(), separator="-", lowercase=True)

    return f"{city_slug}/{street_slug}"


def translit_city(city: str):
    """
    Преобразует название города в URL-дружественный транслитерированный slug:
    убирает пробелы по краям, переводит в латиницу, приводит к нижнему регистру
    и заменяет пробелы/разделители на дефисы.
    Примеры:
      "Хабаровск" -> "khabarovsk"
      "Санкт-Петербург" -> "sankt-peterburg"
      "Нижний Новгород" -> "nizhnii-novgorod"
    """
    return slugify(city.strip(), separator="-", lowercase=True)
