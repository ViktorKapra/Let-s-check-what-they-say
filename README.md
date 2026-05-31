# Паралелен анализ на политическия език в Българския парламент

Курсов проект по дисциплината **„Паралелно програмиране с Python"** — измерване и сравнение на паралелни подходи върху корпус от стенограми на **51-вото Народно събрание** на Република България. Данните са от публичната платформа [strazha.bg](https://www.strazha.bg).

## Реализации

| Тип работа | Реализация | Технология |
|---|---|---|
| Събиране на данни (I/O-bound) | серийна | `requests` + HTTP keep-alive |
| Събиране на данни (I/O-bound) | **асинхронна** | `asyncio` + `aiohttp`, семафор = 5 |
| Анализ (CPU-bound) | серийна (база) | чист Python + `collections.Counter` |
| Анализ (CPU-bound) | **многопроцесорна** | `multiprocessing.Pool` с map-reduce |
| Анализ (CPU-bound) | **векторизирана** | NumPy + scikit-learn (`TfidfVectorizer`, `cosine_similarity`) |

## Ключови резултати

**Анализ — ускорение спрямо серийното решение:**

| Корпус | Изказвания | Векторизирано | Многопроцесорно (най-добро) |
|---|---:|---:|---:|
| Малък | 354 | **1.07×** | 0.23× @ 4 процеса |
| Среден | 5 871 | **1.31×** | 1.07× @ 4 процеса |
| Голям | 21 907 | 1.17× | **1.56× @ 8 процеса** |

**Събиране на данни — асинхронно vs серийно:**

| Корпус | Заседания | Ускорение |
|---|---:|---:|
| Малък | 10 | 4.69× |
| Среден | 50 | **5.30×** |

Подробен анализ на причините за тези резултати — в раздел 10 на отчета.

## Структура

```
src/
  collecting_data/        # серийни + асинхронен скрапер; изброяване на дати
  analysis_serial.py      # серийна реализация на анализа (база за сравнение)
  analysis_mp.py          # многопроцесорна (map-reduce декомпозиция)
  analysis_vectorized.py  # NumPy / sklearn
  benchmark.py            # измервания на трите анализни варианта
  benchmark_scraping.py   # измервания на скрапера
  verify_correctness.py   # проверка на еквивалентност на трите варианта
  dump_results.py         # дъмп на TF-IDF, биграми/триграми, сходство
  common.py               # токенизация, стоп-думи, зареждане на CSV
docs/
  отчет.md / отчет.docx   # финален отчет (13 раздела, на български)
  promptove.md            # подбор от AI-промптовете при разработката
```

## Стартиране

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirments.txt

# Изброяване на датите на заседанията
python src\collecting_data\scrape_mandate.py

# Събиране на данни (асинхронно е препоръчителното)
python src\collecting_data\scraper_async.py --corpus medium
python src\parse_and_save.py --corpus medium

# Проверка на коректност между трите реализации
python -X utf8 src\verify_correctness.py

# Бенчмарк + графики
python src\benchmark.py
python src\benchmark_scraping.py
python src\dump_results.py --corpus all
```

## Документация

- Финален отчет: [`docs/отчет.docx`](docs/отчет.docx) (markdown източник: [`docs/отчет.md`](docs/отчет.md)).

