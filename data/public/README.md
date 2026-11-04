# Public steel-industry energy dataset

`steel_industry_energy_consumption.csv` is the `Steel_industry_data.csv` file
from the UCI Machine Learning Repository's [Steel Industry Energy
Consumption](https://archive.ics.uci.edu/dataset/851/steel+industry+energy+consumption+dataset)
dataset (DOI: [10.24432/C52G8C](https://doi.org/10.24432/C52G8C)).

The dataset page describes the 35,040 observations as electricity-consumption
data collected from a small-scale steel industry in Gwangyang, South Korea,
provided by Sathishkumar V E, Changsun Shin, and Yongyun Cho. The dataset is
licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Attribution: Sathishkumar V E, Changsun Shin, and Yongyun Cho, "Steel Industry
Energy Consumption," UCI Machine Learning Repository, DOI
10.24432/C52G8C. The source CSV is redistributed here under that license.

The `date` values are at 15-minute intervals and do not specify a timezone.
The evaluation treats them as timezone-naive timestamps (the current evaluator
normalizes them as UTC); this does not establish the plant's local timezone.
The dataset measures steel-industry electricity and does not contain paper-mill,
steam, gas, water, production, or equipment-calibration data.

The UCI repository provides the data and license statement; this project has not
independently audited the original meters, plant identity, or measurement
process. Do not treat results as evidence of performance at a Tasico factory.
