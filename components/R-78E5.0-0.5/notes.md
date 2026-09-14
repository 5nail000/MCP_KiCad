# R-78E5.0-0.5 (RECOM)

Официальный символ KiCad 10: `Converter_DCDC:R-78E5.0-0.5`

Footprint в символе: `Converter_DCDC:Converter_DCDC_RECOM_R-78E-0.5_THT`

Ссылка из поля Datasheet символа KiCad:

https://www.recom-power.com/pdf/Innoline/R-78Exx-0.5.pdf

## Проверенные поля из библиотеки KiCad (не выдуманные)

- Description: 500mA Step-Down DC/DC-Regulator, 7-28V input, 5V fixed Output Voltage, LM78xx replacement, -40°C to +85°C, SIP3
- Pin 1: IN (power_in)
- Pin 2: GND (power_in)
- Pin 3: OUT (power_out)

## Что обязана проверить LLM по datasheet (не по одному имени)

- Vin: модуль **не** на 5V вход; для 12V входа 7–28V подходит.
- Iout max: 0.5 A
- Vout: фиксированные 5.0 V
- AMR и тепловой режим — только из PDF производителя, не из названия.
