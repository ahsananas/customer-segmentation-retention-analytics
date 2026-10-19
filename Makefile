.PHONY: all data workbook validate dashboard deck docs cover test
all: data workbook validate dashboard cover docs test
data:      ; python -m src.run_all
workbook:  ; python -m src.build_workbook
validate:  ; python -m src.validate
dashboard: ; python -m src.build_dashboard
cover:     ; python -m src.build_cover
deck:      ; node presentation/build_deck.js
docs:      ; python -m src.build_docs
test:      ; python -m pytest -q
