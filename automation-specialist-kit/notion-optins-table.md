# Notion opt-ins table

Claude creates this for you. If you build it by hand, use these columns:

| Column | Type |
|---|---|
| First Name | title |
| Email | email |
| Opted In | date with time |
| Source | select (Landing page, Test) |
| Page URL | URL |
| Day | formula `formatDate(prop("Opted In"), "YYYY-MM-DD")` |
| Week | formula `year(prop("Opted In")) + "-W" + (if(week(prop("Opted In")) < 10, "0", "")) + week(prop("Opted In"))` |
| Month | formula `formatDate(prop("Opted In"), "YYYY-MM")` |

Dashboard: number tiles for today, last 7 days, last 30 days and all time, plus column charts by Day, Week and Month.
