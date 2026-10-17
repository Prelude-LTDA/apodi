"""Line-break comparison: Apodi vs the reference fonts, shaped with HarfBuzz.

  APTOS_DIR=/path/to/aptos python -I linebreak.py --fonts fonts/ttf [--json out.json]

For every style pair: ~20 business paragraphs (English, Portuguese, Italian; numbers and
currency) are broken greedily at several column widths and font sizes, with kerning on and
off; a line's width is the HarfBuzz-shaped advance of the whole line (so kerning across spaces
and ligatures count). For the Narrow styles, spreadsheet-like cell strings are also checked
against Excel-style column widths: does the string fit, and where does a wrapped cell break.
Any line whose break differs is reported.
"""
import argparse
import json
import os
import sys

import uharfbuzz as hb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_metrics import PAIRS  # noqa: E402

PARAGRAPHS = [
    # English
    "Revenue for the third quarter of 2026 reached $4,218,750, an increase of 12.4% over the same period last year, driven primarily by the expansion of our enterprise contracts in Latin America and Southern Europe.",
    "The Board of Directors approved the revised operating budget of €1,250,000 for fiscal year 2027, including a contingency reserve of 8% and capital expenditures of approximately £310,000 for the new office.",
    "Please review the attached agreement (Version 3.2, dated 14 October 2026) and return the signed copy by Friday. Any amendments to Sections 4.1 through 4.7 must be initialed by both parties.",
    "Accounts receivable over 90 days decreased to 6.1% of the total portfolio, compared with 9.8% in Q2. Write-offs totaled $27,430.15, mainly related to two customers in bankruptcy proceedings.",
    "Following the audit, the Finance team will implement quarterly reconciliations, segregation of duties for vendor master data, and a two-step approval workflow for payments above $50,000.",
    "WHEREAS the Parties wish to set forth the terms and conditions under which the Supplier shall provide the Services; NOW, THEREFORE, in consideration of the mutual covenants herein, the Parties agree as follows.",
    "Headcount grew from 184 to 212 full-time employees; average cost per employee rose 3.7% to $96,400, while revenue per employee improved to $318,200 (up from $297,900).",
    # Portuguese
    "A Prelude Ltda. registrou receita líquida de R$ 4.218.750,00 no terceiro trimestre de 2026, alta de 12,4% sobre o mesmo período do ano anterior, impulsionada pela expansão dos contratos corporativos.",
    "Conforme deliberado na Assembleia Geral Ordinária de 30 de abril, os dividendos de R$ 0,87 por ação serão pagos em duas parcelas, nos dias 15 de junho e 15 de dezembro, sem atualização monetária.",
    "O contratante deverá apresentar, no prazo de 10 (dez) dias úteis, a certidão negativa de débitos trabalhistas, o comprovante de regularidade fiscal e a garantia contratual equivalente a 5% do valor global.",
    "As despesas administrativas somaram R$ 1.327.904,18, queda de 3,2% em relação ao exercício anterior, em razão da renegociação de aluguéis e da migração dos sistemas para a nuvem.",
    "Fica eleito o foro da Comarca de São Paulo, Estado de São Paulo, com exclusão de qualquer outro, por mais privilegiado que seja, para dirimir as questões oriundas deste contrato.",
    "Informamos que a reunião de alinhamento orçamentário foi remarcada para quinta-feira, às 14h30, na sala 1203. Pedimos que tragam as projeções de fluxo de caixa atualizadas até 31/12/2027.",
    "O índice de inadimplência recuou para 2,7% da carteira, ante 3,9% no trimestre anterior; a provisão para devedores duvidosos foi ajustada em R$ 212.450,00, conforme a política contábil vigente.",
    # Italian
    "La società Milano S.r.l. ha registrato un fatturato di € 876.300 nel terzo trimestre, in crescita del 7,9% rispetto allo stesso periodo dell'anno precedente, grazie all'aumento delle vendite all'estero.",
    "Il Consiglio di Amministrazione ha approvato all'unanimità il bilancio d'esercizio chiuso al 31 dicembre 2026, che evidenzia un utile netto di € 1.204.560,32 e un patrimonio netto di € 9,8 milioni.",
    "Si prega di inviare la documentazione richiesta entro e non oltre venerdì 20 novembre; eventuali ritardi potrebbero comportare l'applicazione delle penali previste dall'articolo 12 del contratto.",
    "Le spese di trasferta, comprensive di vitto e alloggio, non potranno superare l'importo di € 180,00 al giorno per dipendente, salvo autorizzazione scritta del responsabile dell'ufficio acquisti.",
    "Il presente accordo entra in vigore alla data della sottoscrizione e avrà durata di ventiquattro (24) mesi, rinnovabile tacitamente per ulteriori periodi di dodici mesi, salvo disdetta scritta.",
    "Nel corso dell'anno l'azienda ha ridotto le emissioni di CO₂ del 14% e ha investito € 2,3 milioni in efficienza energetica, formazione del personale e digitalizzazione dei processi produttivi.",
]

# (font size pt, column width pt): letter/A4 body text, two-column, narrow sidebar, wide
LAYOUTS = [(11, 451.3), (12, 451.3), (10, 451.3), (11, 216.0), (9, 160.0), (11, 523.3), (14, 451.3), (8, 120.0)]

CELLS = [
    "Total receita líquida", "R$ 1.234.567,89", "31/12/2026", "Fornecedor: Acme Ltda.", "€ 12.450,00",
    "Accounts payable", "(1,204.50)", "#N/A", "12.4%", "Q3 2026 forecast", "Descrição do item",
    "Quantità", "Prezzo unitario", "IVA 22%", "Totale documento", "Centro de custo 4401", "Status: Pago",
    "Customer ID", "Invoice date", "Due in 30 days", "Variação % a/a", "-3,2%", "1.000.000", "Sim",
    "Departamento Financeiro", "Approved by J. Smith", "Gennaio", "Fevereiro", "Weighted average cost",
    "$ 0.87", "Saldo anterior", "Juros e multa", "Notes / Observações", "Ordine n. 2026/0457",
]
COLUMN_CHARS = [8.43, 10, 12, 15, 20]   # Excel column widths in "characters" (8.43 is the default)
NARROW_SIZE = 11


class Shaper:
    def __init__(self, path):
        self.face = hb.Face(open(path, "rb").read())
        self.font = hb.Font(self.face)
        self.upem = self.face.upem
        self.cache = {}

    def width(self, text, kern):
        key = (text, kern)
        if key not in self.cache:
            buf = hb.Buffer()
            buf.add_str(text)
            buf.guess_segment_properties()
            hb.shape(self.font, buf, {"kern": kern})
            self.cache[key] = sum(p.x_advance for p in buf.glyph_positions)
        return self.cache[key]


def greedy(text, shaper, limit_units, kern):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        cand = (cur + " " + w) if cur else w
        if not cur or shaper.width(cand, kern) <= limit_units:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def excel_col_units(chars, shaper, size_pt, kern):
    # Excel: column width in characters of the maximum digit width (+ 5 px padding at 96 dpi)
    px_per_unit = size_pt * 96 / 72 / shaper.upem
    digit = max(shaper.width(str(d), kern) for d in range(10))
    digit_px = round(digit * px_per_unit)
    col_px = int(((256 * chars + int(128 / digit_px)) / 256) * digit_px) + 5
    return (col_px - 5) / px_per_unit  # usable width (without padding) in font units


def compare_style(ref_path, mine_path, narrow):
    R, M = Shaper(ref_path), Shaper(mine_path)
    out = dict(paragraph_cases=0, paragraph_diffs=[], lines=0, cell_cases=0, cell_diffs=[])
    for kern in (True, False):
        for size, col in LAYOUTS:
            limit = col / size * R.upem
            for i, p in enumerate(PARAGRAPHS):
                a, b = greedy(p, R, limit, kern), greedy(p, M, limit, kern)
                out["paragraph_cases"] += 1
                out["lines"] += len(a)
                if a != b:
                    for j, (x, y) in enumerate(zip(a, b)):
                        if x != y:
                            out["paragraph_diffs"].append(dict(kern=kern, size=size, col=col, para=i, line=j, ref=x, mine=y))
                            break
        if narrow:
            for chars in COLUMN_CHARS:
                for text in CELLS:
                    ra = excel_col_units(chars, R, NARROW_SIZE, kern)
                    ma = excel_col_units(chars, M, NARROW_SIZE, kern)
                    fit_r, fit_m = R.width(text, kern) <= ra, M.width(text, kern) <= ma
                    wrap_r, wrap_m = greedy(text, R, ra, kern), greedy(text, M, ma, kern)
                    out["cell_cases"] += 1
                    if fit_r != fit_m or wrap_r != wrap_m or ra != ma:
                        out["cell_diffs"].append(dict(kern=kern, chars=chars, text=text, fit_ref=fit_r, fit_mine=fit_m,
                                                      wrap_ref=wrap_r, wrap_mine=wrap_m))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", default="fonts/ttf")
    ap.add_argument("--aptos", default=os.environ.get("APTOS_DIR"))
    ap.add_argument("--json")
    a = ap.parse_args()
    if not a.aptos:
        sys.exit("set APTOS_DIR or pass --aptos")
    res, bad = {}, 0
    print(f"{'style':26} {'para cases':>10} {'lines':>6} {'diffs':>6} {'cell cases':>10} {'diffs':>6}")
    for stem, refname in PAIRS.items():
        mine, ref = os.path.join(a.fonts, stem + ".ttf"), os.path.join(a.aptos, refname)
        if not (os.path.exists(mine) and os.path.exists(ref)):
            continue
        r = compare_style(ref, mine, "Narrow" in stem)
        res[stem] = r
        bad += len(r["paragraph_diffs"]) + len(r["cell_diffs"])
        print(f"{stem:26} {r['paragraph_cases']:10} {r['lines']:6} {len(r['paragraph_diffs']):6} "
              f"{r['cell_cases']:10} {len(r['cell_diffs']):6}")
        for d in (r["paragraph_diffs"] + r["cell_diffs"])[:5]:
            print("   ", d)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(res, fh, indent=1, ensure_ascii=False)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
