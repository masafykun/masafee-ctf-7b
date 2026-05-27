.PHONY: all clean en ja

all: paper_en.pdf paper_ja.pdf

en: paper_en.pdf

ja: paper_ja.pdf

paper_en.pdf: paper_en.tex
	pdflatex -interaction=nonstopmode paper_en.tex
	pdflatex -interaction=nonstopmode paper_en.tex
	rm -f paper_en.aux paper_en.log paper_en.out paper_en.toc

paper_ja.pdf: paper_ja.tex
	lualatex -interaction=nonstopmode paper_ja.tex
	lualatex -interaction=nonstopmode paper_ja.tex
	rm -f paper_ja.aux paper_ja.log paper_ja.out paper_ja.toc

clean:
	rm -f *.aux *.log *.out *.toc *.pdf
