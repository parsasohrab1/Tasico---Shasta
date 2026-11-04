# Tasico Shasta

پایهٔ اجرایی و قابل‌آزمون CEUO برای دریافت توکن، تولید پیشنهاد بهینه‌سازی و ارزیابی
زمانی مدل‌ها. این نسخه فقط پیشنهاد می‌دهد و به PLC/DCS فرمان ارسال نمی‌کند.

## نیازمندی و اجرا

Python 3.10 یا جدیدتر لازم است. در PowerShell:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### پیکربندی امن

هیچ کلید JWT، حساب یا رمز پیش‌فرضی در برنامه وجود ندارد. برای ساخت hash رمز:

```powershell
tasico hash-password
```

سپس `.env.example` را به `.env` کپی کنید و `JWT_SECRET` را با دست‌کم ۳۲ بایت
تصادفی و `AUTH_USERS_JSON` را با hash تولیدشده پر کنید. نمونهٔ ساخت secret در
PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

ساختار `AUTH_USERS_JSON`:

```json
[
  {
    "username": "operator1",
    "password_hash": "$2b$12$REPLACE_WITH_HASH_FROM_tasico_hash-password",
    "role": "operator",
    "factories": ["F1-PAPER"]
  }
]
```

نقش‌های مجاز `admin`, `manager`, `operator`, `viewer` هستند. فقط `admin` به همهٔ
کارخانه‌ها دسترسی دارد؛ نقش‌های دیگر باید شناسهٔ کارخانهٔ مجاز داشته باشند. کاربر
بیننده نمی‌تواند درخواست بهینه‌سازی ثبت کند. تنظیمات در زمان شروع اعتبارسنجی
می‌شوند و نبود کلید یا کاربر باعث شکست صریح شروع سرویس می‌شود.

برای اجرای محلی، پس از بارگذاری متغیرهای `.env` در محیط:

```powershell
$env:JWT_SECRET = (python -c "import secrets; print(secrets.token_urlsafe(48))")
$env:JWT_EXPIRE_MINUTES = "60"
$env:AUTH_USERS_JSON = '[{"username":"operator1","password_hash":"<paste bcrypt hash from tasico hash-password>","role":"operator","factories":["F1-PAPER"]}]'
uvicorn tasico_shasta.api:app --app-dir src --host 127.0.0.1 --port 8000
```

یا برای Docker Compose:

```powershell
docker compose up --build
```

درخواست توکن از `POST /auth/token` با فرم OAuth2 و بررسی سلامت از `GET /health`
در دسترس است. `POST /optimization/dispatch` فقط برای کاربر مجاز و با ضرایب کالیبره‌شدهٔ
تجهیزات کار می‌کند. مستندات تعاملی API در `/docs` ارائه می‌شوند.

## بهینه‌سازی

برای هر دیگ، ظرفیت بخار و مصرف ویژهٔ کالیبره‌شدهٔ گاز (`gas_m3_per_tonne_steam`)
و برای هر توربین ظرفیت و بخار مصرفی کالیبره‌شدهٔ هر MWh
(`steam_tonnes_per_mwh`) لازم است. هیچ ضریب صنعتی حدس‌زده نمی‌شود. مدل تراز بخار،
تراز برق، حداقل/حداکثر بار تجهیزات و ورود/صدور غیرهم‌زمان برق را اعمال می‌کند.
اگر حل‌گر پاسخ بهینه ندهد، سرویس صرفه‌جویی موفق‌نما گزارش نمی‌کند. اعداد و واحدها
باید پیش از استفادهٔ عملی توسط مهندس فرایند تأیید شوند.

## هشدار انحراف مصرف

کاربر احراز هویت‌شده می‌تواند مصرف مشاهده‌شده را با مقدار مورد انتظار و آستانه‌های
مطلق همان شاخص مقایسه کند:

```text
POST /alerts/deviation
```

بدنه شامل `factory_id`، زمان منطقه‌دار `observed_at` و فهرستی از سیگنال‌هاست.
هر سیگنال یکی از شاخص‌های برق، بخار، گاز یا آب را با `actual`، `expected` و
آستانه‌های مثبت `warning_threshold` و `critical_threshold` می‌فرستد؛ آستانهٔ بحرانی
باید بزرگ‌تر از آستانهٔ هشدار باشد. این آستانه‌ها در واحد خود شاخص هستند و محصول
مقدار صنعتی پیش‌فرضی فرض نمی‌کند. هشدار فقط از رسیدن قدرمطلق اختلاف به آستانهٔ
هشدار ساخته می‌شود؛ درصد اختلاف وقتی مقدار مورد انتظار صفر باشد `null` است.

این نسخه فقط هشدار را محاسبه و برمی‌گرداند؛ آن را ذخیره یا تخصیص نمی‌دهد و علت
ریشه‌ای را تشخیص نمی‌دهد. نقش‌های غیرمدیر فقط به کارخانه‌های مجاز خود دسترسی دارند.

## اعتبارسنجی مدل با دادهٔ آزمون

مخزن دادهٔ واقعی یا مدل آموزش‌دیدهٔ تأییدشده ندارد. برای تولید گزارش باید CSV
واقعی و دارای ستون‌های `timestamp`, `factory_id`, `elec_consumption_kwh`,
`steam_demand_t`, `gas_consumption_m3`, `water_intake_m3` ارائه شود. مدل
برای هر کارخانه به‌صورت زمانی تقسیم می‌شود و فقط یک گام جلو را می‌سنجد:

```powershell
tasico evaluate --input .\data\holdout.csv --report .\reports\metrics.json --models .\models
```

ویژگی‌های lag و میانگین متحرک فقط از مشاهدات پیشین ساخته می‌شوند؛ مقدار جاری
هدف وارد ویژگی نمی‌شود. MAPE فقط روی مقادیر واقعی غیرصفر محاسبه و تعداد نمونه‌های
آن گزارش می‌شود؛ WAPE نیز همراه آن ارائه می‌شود. گزارش hash داده، مرز زمانی و
تعداد سطرهای آزمون را ثبت می‌کند. اصالت داده مستقلاً قابل تأیید نیست و معیارها
تا وقتی دادهٔ واقعی و ممیزی‌شده ارائه نشده، ادعای عملکرد محصول نیستند.

### بازآزمایی هزینه و صرفه‌جویی بالقوه

CSV بازآزمایی باید دارای `factory_id`, `steam_demand_tph`,
`electricity_demand_kw`, `actual_gas_m3`, `actual_grid_import_kwh`,
`gas_price_per_m3`, `electricity_import_price_per_kwh` باشد. `actual_gas_m3` و
مقادیر برق، انرژی اندازه‌گیری‌شده در هر بازه‌اند. فایل تجهیزات JSON بر اساس
شناسهٔ کارخانه تعریف می‌شود:

```json
{
  "F1-PAPER": {
    "boilers": [
      {
        "id": "B1",
        "capacity_tph": 30,
        "gas_m3_per_tonne_steam": 2.4,
        "minimum_load": 0.2
      }
    ],
    "turbines": []
  }
}
```

```powershell
tasico backtest-savings --input .\data\holdout.csv --equipment .\equipment.json --report .\reports\savings.json
```

خروجی با `claim_type=counterfactual_modeled_potential` مشخص می‌شود و هرگز صرفه‌جویی
محقق‌شده را ادعا نمی‌کند. این برآورد فقط وقتی معنا دارد که صورت‌حساب اندازه‌گیری‌شده،
تعرفه و ضرایب تجهیزات معتبر و هم‌واحد باشند. Go/No-Go تنها پس از ثبت و بازبینی
معیارهای واقعی و تأیید ذی‌نفعان قابل تصمیم‌گیری است.

## آزمون و CI

```powershell
python -m pytest
```

GitHub Actions تست‌ها را روی Python 3.10 تا 3.12 اجرا می‌کند. برای پذیرش استقرار
واقعی هنوز دادهٔ کارخانه، کالیبراسیون تجهیزات، اتصال امن به منابع داده، ذخیره‌سازی
پایدار و آزمون بار/بازیابی لازم است.
