بخش ۱ — ADRها
docs/adr/README.md
markdown
# Architecture Decision Records — CEUO

فهرست تصمیم‌های معماری ثبت‌شده:

| ADR | عنوان | وضعیت |
|---|---|---|
| 001 | زبان و فریم‌ورک | Accepted |
| 002 | مدل پیش‌بینی مصرف | Accepted |
| 003 | مدل تشخیص انحراف | Accepted |
| 004 | رویکرد بهینه‌سازی | Accepted |
| 005 | پایگاه داده سری‌زمانی | Accepted |

قالب: Michael Nygard. هر ADR تغییرناپذیر است؛ تصمیم جدید = ADR جدید با ارجاع به قبلی.
docs/adr/ADR-001-language.md
markdown
# ADR-001 — زبان و فریم‌ورک اصلی

- **Status:** Accepted
- **Date:** 2025-01-15
- **Deciders:** Tech Lead, ML Lead, CTO

## Context
CEUO نیاز به پوشش هم‌زمان این حوزه‌ها دارد: مدل‌سازی ML، پردازش داده سری‌زمانی، بهینه‌سازی ریاضی، API inference، و داشبورد مدیریتی. تیم ۳ نفره، بودجه محدود، الزام کارفرما به استقلال فنی (بدون قفل ابری).

## Decision
- **Python 3.11** برای تمام لایه‌های ML، ETL، optimization، API.
- **Streamlit** برای داشبورد، **FastAPI** برای API.
- **SQL (PostgreSQL/TimescaleDB)** برای لایه داده تحلیلی.
- **Docker** برای استقرار.

## Alternatives Considered

| گزینه | رد شد به دلیل |
|---|---|
| R + Shiny | بوم‌سازگان ضعیف برای اتصال صنعتی و optimization |
| Julia | کتابخانه Gurobi/CBC/MLflow ناقص؛ ریسک نگهداشت |
| Scala + Spark ML | Overkill برای ۵۲k ردیف؛ هزینه تیم |
| React + FastAPI + Python | فرانت‌اند نیاز به نفر-ماه اضافه؛ فاز ۱ توجیه ندارد |
| Power BI | نمی‌تواند مدل ML را درون خود اجرا کند؛ مجوز گران |

## Consequences

**مثبت:**
- یک تیم واحد کل چرخه را تحویل می‌دهد؛ کاهش ریسک همگام‌سازی.
- زمان تحویل MVP ≈ ۴–۶ ماه (در مقابل ۸–۱۰ ماه polyglot).
- همه ابزارها open-source و self-hosted → استقلال فنی کارفرما.

**منفی:**
- Streamlit برای UI سازمانی بزرگ مقیاس محدود است؛ در فاز ۳ ممکن است به React مهاجرت کند.
- Python برای پردازش‌های CPU-bound سنگین کند است؛ در صورت نیاز به Rust/Cython در فاز ۲.

**خنثی:**
- فرانت‌اند و بک‌اند هم‌زبان‌اند؛ مرز API از ابتدا رعایت می‌شود تا مهاجرت آسان باشد.
docs/adr/ADR-002-forecast-model.md
markdown
# ADR-002 — مدل پیش‌بینی مصرف

- **Status:** Accepted
- **Date:** 2025-01-20
- **Deciders:** ML Lead, Domain Expert

## Context
پیش‌بینی مصرف برق/گاز/بخار/آب در ۳ کارخانه. داده تاریخی: ۱۲ ماه ساعتی (~۵۲k ردیف). الزام تفسیرپذیری برای مدیر و ممیز. آموزش روزانه در Airflow.

## Decision
**LightGBM** به‌عنوان مدل اصلی + **Prophet** به‌عنوان مدل مکمل برای افق میان‌مدت.

## Evaluation Matrix

| مدل | MAPE (bench) | تفسیرپذیری | داده لازم | آموزش | تصمیم |
|---|---|---|---|---|---|
| Naive / MA | ۱۵–۲۵٪ | بالا | کم | ثانیه | فقط Baseline |
| SARIMAX | ۱۲–۱۸٪ | متوسط | متوسط | دقیقه | رد |
| Prophet | ۱۰–۱۴٪ | متوسط | متوسط | دقیقه | مکمل |
| **LightGBM** | **۵–۹٪** | **بالا (SHAP)** | متوسط | ثانیه | ✅ اصلی |
| LSTM / GRU | ۶–۱۰٪ | پایین | زیاد | ساعت | رد (داده کم) |
| Transformer (TFT) | ۵–۸٪ | پایین | بسیار زیاد | روز | فاز ۲ |

## Rationale
1. **دقت رقابتی** روی داده جدولی (مرجع: Grinsztajn et al. 2022).
2. **SHAP** برای الزام تفسیرپذیری مالیاتی.
3. **آموزش سریع** → بازآموزی روزانه ممکن.
4. **داده کم** برخلاف LSTM/Transformer.
5. **پایداری** کمتر دچار drift نسبت به شبکه عصبی.

## Consequences

**مثبت:** دقت کافی، تفسیرپذیری، سرعت، داده کم، پایداری.
**منفی:** سقف دقت نسبت به TFT ~۲–۳٪ پایین‌تر؛ در صورت نیاز به دقت بالاتر باید ensemble شود.
**خنثی:** مدل‌های آینده به‌صورت plugin در Registry اضافه می‌شوند بدون تغییر API.

## Review Trigger
اگر در ۳ ماه پس از استقرار، MAPE میانگین > ۱۲٪ باشد، ADR-006 (ارتقا به TFT) باز می‌شود.
docs/adr/ADR-003-anomaly-model.md
markdown
# ADR-003 — مدل تشخیص انحراف

- **Status:** Accepted
- **Date:** 2025-01-20

## Context
رخدادهای انحرافی گذشته برچسب‌گذاری نشده‌اند. تشخیص باید در داشبورد با علت محتمل نمایش داده شود. داده multimodal و فصلی است.

## Decision
**Isolation Forest** روی فیچرهای مهندسی‌شده (kWh/ton، steam/ton، gas/steam) + **SHAP + قواعد خبره** برای RCA.

## Alternatives Considered

| مدل | برچسب | تفسیرپذیری | دلیل رد |
|---|---|---|---|
| Z-score / IQR | خیر | بالا | حساس به توزیع؛ با multimodal شکست می‌خورد |
| One-Class SVM | خیر | پایین | کند روی ۵۲k ردیف؛ حساس به hyperparameter |
| Autoencoder | خیر | پایین | نیاز به GPU؛ داده بیشتر برای پایداری |
| LSTM Autoencoder | خیر | پایین | توالی طولانی؛ پیچیدگی نگهداشت |

## Rationale
1. **Unsupervised** — بدون نیاز به برچسب.
2. **O(n log n)** روی ۵۲k ردیف.
3. **بدون فرض توزیع** — مناسب multimodal.
4. **فیچر مهندسی‌شده** همبستگی را حذف و آنومالی را برجسته می‌کند.

## Consequences
**مثبت:** سریع، ساده، بدون برچسب.
**منفی:** False Positive بالاتر از مدل supervised؛ آستانه باید با بازخورد بهره‌بردار تنظیم شود.
**Review Trigger:** اگر در ۶ ماه ≥ ۲۰۰ برچسب تأییدشده انباشته شد، Random Forest Classifier به‌عنوان مدل مکمل فعال شود (ADR-007).
docs/adr/ADR-004-optimization.md
markdown
# ADR-004 — رویکرد بهینه‌سازی

- **Status:** Accepted
- **Date:** 2025-01-25

## Context
تصمیم بهره‌برداری: کدام دیگ‌ها روشن، کدام توربین چقدر، چقدر از شبکه خرید شود. محدودیت‌ها: ظرفیت، حداقل بار، تعمیرات، تقاضای بخار/برق.

## Decision
**MILP** با حل‌کننده CBC (پیش‌فرض) / Gurobi (اختیاری) + **NSGA-II** برای حالت چندهدفه (هزینه + انتشار).

## Alternatives Considered

| رویکرد | دلیل رد |
|---|---|
| LP ساده | محدودیت on/off دیگ را نمی‌گیرد |
| Genetic Algorithm | کند، غیرقابل تکرار، غیرقابل حسابرسی |
| Reinforcement Learning | داده کافی نیست؛ غیرقابل ممیزی؛ ریسک عملیاتی |
| Heuristic | بهینه سراسری نمی‌دهد |

## Rationale
1. مسئله ذاتاً **MILP** است (پیوسته + باینری).
2. **قابل حسابرسی** — هر تصمیم قابل ردیابی به محدودیت/ضریب.
3. CBC رایگان؛ Gurobi فقط در صورت نیاز سرعت.

## Consequences
**مثبت:** بهینه سراسری، قابل حسابرسی، سریع (ثانیه–دقیقه).
**منفی:** محدودیت‌های غیرخطی (راندمان تابع بار) باید خطی‌سازی شوند یا در NSGA-II لحاظ شوند.
**Review Trigger:** اگر مدل MILP در > ۵٪ موارد infeasible شود، reformulation با متغیرهای slack.
docs/adr/ADR-005-database.md
markdown
# ADR-005 — پایگاه داده سری‌زمانی

- **Status:** Accepted
- **Date:** 2025-01-25

## Decision
**TimescaleDB** (PostgreSQL extension).

## Alternatives

| گزینه | مزیت | دلیل رد |
|---|---|---|
| InfluxDB | عملکرد نوشتن بالا | No JOIN؛ تحلیل‌گر SQL بلد نیست |
| Prometheus | مانیتورینگ عالی | برای analytic workload مناسب نیست |
| ClickHouse | OLAP فوق‌سریع | پیچیدگی عملیاتی؛ تیم کوچک |
| **TimescaleDB** ✅ | SQL + time-series + JOIN | انتخاب شد |

## Rationale
1. **SQL آشنا** — تحلیل‌گر و مدیر می‌توانند مستقیم کوئری بزنند.
2. **JOIN** با داده رابطه‌ای (تولید، تجهیزات، قیمت).
3. **Continuous Aggregates** برای داشبورد سریع.
4. **PostgreSQL ecosystem** — backup، monitoring، ORM بالغ.

## Consequences
**مثبت:** یک پایگاه داده برای همه؛ کوئری‌های پیچیده تحلیلی ممکن.
**منفی:** در نوشتن > ۱M point/sec ضعیف‌تر از Influx است — برای CEUO مسئله نیست.
