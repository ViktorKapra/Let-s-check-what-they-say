# Промптове, използвани при работата по проекта

Този файл съдържа подбор от по-съществените инструкции и обяснения, дадени към AI асистента (Claude, Anthropic) по време на разработването на проекта. Селекцията се фокусира върху промптовете, които задават посока, обясняват очаквания или поставят концептуални въпроси — кратките потвърждения, корекциите от типа „махни този ред" и техническите grep-вания не са включени.

Промптовете са в хронологичен ред в рамките на всяка фаза. Оригиналният език (български или английски) е запазен.

---
## фаза 0 - Съставяне на задание

1
Да но какво ще кажеш за нещо чиито резултат да е нещо по-забавно или смислено, примерно нека измислим социален въпрос, след това ще намерим източници, които да използваме и накрая на база на анализите (които ще са паралелни) да се опитаме да дадем отговор, как ти се струва това

2
а какви видове анализ мога да направя върху текст, които да са подходящи за текстообработка

3
мисля да опитам да ползвам www.strazha.bg понеже стенограмите са разделени и по политици и мога да ползвам даните като ги спомена като източник. може ли да провериш дали мога да правя автоматични заявки към тях и да видиш дали имат описателно API

4
следното дали ще ти помогне повече:
Request URL: https://www.strazha.bg/sessions/2026-04-01/steno/?_data=root
Request Method: GET
Status Code: 200 OK
Remote Address: [2606:4700:3033::ac43:d913]:443
Referrer Policy: strict-origin-when-cross-origin

5
може ли за теста да ми напишеш powershell скрипт, ама постарай се да е правилен, за да видя че наистина може (а и сгреши с предположението че strazha е само front-end)

6
следнотто парче от имейла мисля да го променим:
„Целта на проекта е да се приложат различни подходи за паралелна обработка върху реален и обществено значим текстов корпус, а резултатите да дадат отговор на въпроса дали и как се различава езикът на отделните парламентарни групи — по честота на ключови думи, използвана лексика и реторични шаблони."

7
ок, добавих и изисквания за проекта, така че ми хайде да започнем с разработването на план за действие за създаване на доклада и проекта

8
now write as descriptive as you can write phase 1

9
ок все пак може да преведеш понеже ще представям нещата на български

10
изпълних фаза 1 с дребни изменения можем ли да изгенерираме фаза 2

11
може ли обаче и да видиш фаза 1 и 2 и да опишеш какъв формат трябва да генерира фаза 1 така че фаза 2 да започне безпроблемно

12
ок може ли като последна фаза, която може би няма да влезе в проекта да опишеш multithreading реализация с no GIL Python — нея ще я опитам само ако ми остане време
## Фаза 1 — Събиране на данни (скрапер)

**16 май 2026 — стартиране:**

> ok first task is ok, what is next

**17 май — изследване на API на strazha.bg:**

> make request via shell and save the result in the docs so i can peek to the structure whenever needed

> try with earlier stenograms but if you fail tell me how to pull it myself

**17 май — концептуален въпрос за asyncio и GIL:**

> in order to use async methods do i need another version of python with no GIL

**17 май — структуриране на работата:**

> please refactor the sequential approach and add __main__ i want to test both solutions myself

**19 май — споделяне на собствен код за ревю:**

> i have created common.py please check my work

**20 май — управление на зависимости (uv vs pip):**

> can you view do i need to install additional packages in the requirments.txt and how to add them to the venv

> i don't want to install python 3.12 i will use less aggressive requirement format

> now how to create virtual env with uv and how to install requirements there

> why do i need to install only binaries

**20 май — фиксиране на counter-intuitive грешка с wheels:**

> Using Python 3.14.3 environment at: venv
>   × No solution found when resolving dependencies:
>   ╰─▶ Because aiohttp==3.9.1 has no usable wheels and you require aiohttp==3.9.1, we can conclude that your requirements are unsatisfiable.

> think longer view my project and tell me the RIGHT REQUIREMENTS

---

## Фаза 2 — Реализация на анализа (серийно, mp, векторизирано)

**23 май — преглед на собствен код:**

> ok what do you think about my code

> the code is that fast because there is only one or two speeches that are downloaded

> but the idea is to check all sessions from a mandate

**23 май — установяване на работен ритъм („обясни ми преди да правиш"):**

> can i ask you for each new library to give me small source so i can read what it does and the function that i will use

> i just wanted to ask, what is faster using multiprocessing or multithreading especially for current task

> just list me the libraries that i need to read about and the functions that i will use

> can you explain me the following from the documentation

**24 май — преминаване към multiprocessing:**

> ok lets begin with the implementation of analyse_mp

> ok switch your explanation of run_parallel with the better function, can you think something else you missed

**24 май — концептуален въпрос за векторизация:**

> can you shortly explain each function which we will use and are they vectorized (they use matrices and get benefit from the special vector processing unit in my laptop)

> ok, can you write this analysis somewhere it will be needed in phase 4

**24 май — sklearn параметри:**

> i don't fully understand the following 2 arguments in the vectorizer min_df=2, # ignore words appearing in <2 parties (noise) sublinear_tf=True, # use log(1+tf) — dampens very frequent words

**24 май — изравняване на работата между подходите:**

> i wanted to ask why do we before make cosine similarity because in vectorized step there is cosine similarity but in the others there is no such thing

> yes but lets add cosine similarity in the two other approaches in order to be fair

**25 май — пускане на скриптове върху реални данни:**

> ok, write yourself the file verify_correctness.py

> can you write the code about scraping the sessions of one parliament

> i would like to use option 2 with output folders

---

## Фаза 3 — Бенчмарк и измервания

**25 май — преценка на смислеността на ново измерване:**

> log it in the notes but i am not sure is the result fast enough

> ok the processed data is ready

> ok can you create the benchmark.py

**25 май — преобмисляне на корпусите и графиките:**

> no it is not worth it if we expect not at least x3 optimization and the serial work is too fast do i need to create new input size like extra large which will contain around 500 sessions (or 3 parliaments)?

> no lets inspect the benchmarking, i need more diagrams lets have diagram with the 3 inputs and time and to show all three methods times additionally i would like to present and the scraping optimization using async http calls because i think it is worth to show

> no it is better, now we will talk about the scraping i don't like what you made, if you want you can make small script that will run async and serialize script for all three sizes (don't mention the scraping without session reuse in the diagrams) and from that information to make diagrams

**26 май — изравняване на работата във векторизирания вариант:**

> do in vectorized approach most used word analysis and bigrams and trigrams are calculated even in sequential manner

> i saw the results and i would add stopwords

> no just use the trigrams and bigrams that are used in mp and serial approach so the work and the way it is done is the same

> you are stupid why you want to make serial and mp slower, no we need to make vectorized faster

**26 май — край на измерванията, решение за big серийно scraping:**

> we will not scrape big input make the report structure but make it in Bulgarian

---

## Фаза 4 — Писане на отчета (на български)

**28 май — стартиращ промпт за плана за документацията:**

> базирайки се на записките, материалите и изискванията направи план за създаване на нужната документация. Постарай се по-подробен план да направиш използвай графиките, добавяй таблици. Ще направим документацията и после ще я проверим абзац по абзац

**28 май — поставяне на принципа „базирай се на това, което знаем":**

> това не го добавяй защото видяхме че може да не е точно така: този обем е достатъчно голям, за да направи серийната обработка осезаемо бавна и да има практически смисъл да се търсят паралелни решения, и достатъчно структуриран, за да позволи смислени лингвистични наблюдения по партии.

**28 май — обективност в стила:**

> Опитай се да бъдеш обективен (следното показва лично отношение — всеки такт на процесора прави смислена работа). Изреченията не са свързани по смисъл и не показват за какво ще говориш в този абзац

**28 май — установяване на „обясни преди да правиш промени":**

> Защо си се забил да обясняваш за GIL първо ми обясни преди да правиш промени

> да това което ми написа като предложение ми харесва повече, ако искаш го допълни и ми покажи какво си направил

**28 май — изискване за източници на чужди фрази:**

> за следното ми покажи източник от къде си го чул „embarrassingly parallel" и ако не успееш за напред не ползвай такива фразички

> използвай следното „задача без нужда от комуникация между процесите" вместо англицизмът

**30 май — съответствие с официалните изисквания:**

> този абзац май не е нужен, защо трябва да обяснявам какви фази съм правил за изграждането на проекта, има ли го като изискване?

> хей добавил съм файл с изисквания в папката docs прегледай го и виж дали този абзац трябва да бъде включен

**30 май — проверка на твърдения срещу кода:**

> имаме ли данни за това изречение „Подробности по методологията — брой повторения, осредняване, warm-up — са разгледани в §8."

> това изречение вярно ли е „Всеки ред представлява едно изказване и съдържа полета за дата на заседанието, идентификатор на говорителя, партийна принадлежност, изчистен текст и брой думи (session_date, mp_id, party, text, word_count и др.).", и това така ли е в кода „изказванията с по-малко от 10 значими думи (твърде кратките записи не дават достатъчно сигнал за честотен анализ и биха внесли шум в TF-IDF)."

> наистина ли се пуска 3 пъти подред къде мога да видя това в кода

> провери дали абзаца съответства на кода

**30 май — терминология на български:**

> смени „избор на минимум" с „най-добър резултат", звучи по-добре на български

> не знам какво е попарна матрица дай ми българския термин

> ама на български не се казва прегъва, а се казва достига пик

> ще ти забраня да ползваш думи като флективен и лематизация изразявай мислите просто

**30 май — разграничаване на правила за код vs отчет:**

> това правило е приложимо като пишем код, но тук пишем отчет така че няма нужда да го прилагаш. Още нужен ли е този абзац

**30 май — преглед срещу изискванията и честност на анализа:**

> всъщност критерия за коректност го няма в изискванията на проекта поне аз не го видях

> може ли да е съкратен абзаца до едно изречение, защото той няма голяма тежест в отчета, а е много дълъг за четене

> гледам глупостите които си писал и ми се струва че преди твоята промяна изводите бяха по-честни

**30 май — финален преглед на §11–§13 и обхвата на бъдещата работа:**

> приложи (А) но не прави прекалено дълги изводи, за future work добави това което не успяхме да направим а именно threading вариант с No GIL python

> добре накрая прегледай приложение 12 и структурата на файловете, както и преговори изискванията към документацията

> за точка 1 можеш да добавиш линк към всички python библиотеки които сме ползвали в кода (ако не помниш кои са провери в кода + линкове към някои конкретни функции които сме ползвали, плюс статия по твой избор за TF-IDF и косинусова близост) плюс strazha.bg, 2 Б) като избери по-големите където ти се карам по-малко а повече ти обяснява

---

## Бележка за подбора

Този подбор е извлечен от запазените локални транскрипти на разговорите с AI асистента и съдържа около 50 от приблизително 290-те съществени промпта, дадени през петте седмици работа по проекта. Включени са:

- промптовете, които поставят концептуални въпроси или установяват работен принцип;
- промптовете, които описват желан резултат или ограничение (а не само го коригират);
- промптовете, които обясняват защо някоя посока не е приемлива.

Изключени са кратките потвърждения от типа „ок", „продължи", изолираните корекции на отделни редове и техническите оплаквания за бъгове в инструментите.
