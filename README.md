# JARVIS Solana Trend Scanner v1

Python скенер за Solana пулове. GitHub Actions обновява отчета по график на 15 минути. Отделен експериментален слушател записва събития от Pump.fun в локална SQLite база.

[Изтегли проекта като ZIP](https://github.com/georg-cpu/jarvis-solana-scanner/archive/refs/heads/main.zip) · [Виж изходния код](https://github.com/georg-cpu/jarvis-solana-scanner/tree/main)

## ☕ Почерпи ме с кафе

Доброволна подкрепа с **native SOL** в мрежата **Solana mainnet**. Копирай публичния адрес в своя портфейл.

`CYmGyR3E2rEheJiG48t9LNPjCU9dxGG6sBeUh9mJB9Fy`

[Виж адреса в Solana Explorer](https://explorer.solana.com/address/CYmGyR3E2rEheJiG48t9LNPjCU9dxGG6sBeUh9mJB9Fy)

## Стартиране

За локален отчет изпълни `python scanner.py` от корена на проекта с Python 3.12. За автоматични обновявания активирай Actions в свое копие на хранилището и разреши запис на резултатите. Стартирай ръчно от [JARVIS Solana Scanner](https://github.com/georg-cpu/jarvis-solana-scanner/actions/workflows/scan.yml). Графикът е на минути 07, 22, 37 и 52 от часа и може да има забавяне.

## Четене на резултатите

[Последният отчет](report.md) показва откритите кандидати, ликвидност и наличните данни за обем. При изпълнени правила скенерът може да покаже условен вход, стоп и цели въз основа на затворени свещи. Покритието на публичните източници е частично. Проверките за концентрация на притежателите и възможност за продажба остават неизвестни. За непрекъснато наблюдение виж [инструкциите за Pump.fun слушателя](PUMP_LISTENER.md).

## Файлове в проекта

| Файл | Предназначение |
|---|---|
| [.github/workflows/scan.yml](./.github/workflows/scan.yml) | График, изпълнение и запис на резултатите |
| [PUMP_LISTENER.md](./PUMP_LISTENER.md) | Настройка и ограничения на слушателя |
| [README.md](./README.md) | Описание, стартиране и навигация |
| [jarvis-solana-scanner.zip](./jarvis-solana-scanner.zip) | Архив, съхранен в хранилището |
| [pump_listener.py](./pump_listener.py) | WebSocket слушател за събития от Pump.fun |
| [report.md](./report.md) | Последен записан отчет |
| [requirements-listener.txt](./requirements-listener.txt) | Python зависимости за слушателя |
| [scanner.py](./scanner.py) | Откриване, оценка на кандидати и генериране на отчет |
| [state.json](./state.json) | Запазено състояние на скенера |

## Други публични проекти на JARVIS

- [jarvis-command-center](https://github.com/georg-cpu/jarvis-command-center)
- [jarvis-solana-intelligence](https://github.com/georg-cpu/jarvis-solana-intelligence)
- [jarvis-solana-intelligence1](https://github.com/georg-cpu/jarvis-solana-intelligence1)
