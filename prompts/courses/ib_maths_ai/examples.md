# Example questions: IB Mathematics: applications and interpretation

Style examples for the generator, written as drafts for SST tutor review. Not past-paper
material. One per type. The GDC is allowed in every AI paper.

## mcq, difficulty 2, AI-1.2, SL

A length is measured as 12.4 cm. The exact length is 12.0 cm. Which is the percentage error?
A. \(0.4\%\)  B. \(3.23\%\)  C. \(3.33\%\)  D. \(32.3\%\)
Answer: C. Solution: \(\left|\frac{12.4 - 12.0}{12.0}\right| \times 100 = 3.33\%\).
Distractors: absolute error quoted as a percentage (A), dividing by the measured value (B),
slip by a factor of ten (D).

## numeric, difficulty 3, AI-1.1, SL

An account pays 2.4% interest per year, compounded monthly. CHF 5 000 is invested. Find the
value of the account after 6 years, to the nearest franc.
Answer: 5771 (CHF), tolerance 0.001.
Solution: \(5000\left(1 + \frac{2.4}{100 \times 12}\right)^{12 \times 6} = 5771.3\ldots\), or
the GDC finance solver with \(N = 72\), \(I\% = 2.4\), \(PV = -5000\), \(P/Y = C/Y = 12\).

## short, difficulty 3, AI-2.1, SL

A straight-line model gives a cost of CHF 240 for 20 units and CHF 390 for 50 units. Write
the model in the form \(C = mn + c\).
Answer: `C = 5n + 140`. Solution: gradient \(\frac{390 - 240}{50 - 20} = 5\); then
\(240 = 5(20) + c\) gives \(c = 140\).

## structured, difficulty 4, AI-4.3, SL, 6 marks

A school claims that students' choice of science subject is independent of their year group.
A sample gives the table: Year 12 (Biology 18, Chemistry 12, Physics 10); Year 13 (Biology 12,
Chemistry 16, Physics 12).
(a) State the null and alternative hypotheses. [1]
(b) Find the chi-squared statistic and the p-value. [3]
(c) At the 5% significance level, state the conclusion in context. [2]
Mark scheme: (a) A1 both hypotheses in terms of independence. (b) M1 using the GDC with a
2 by 3 table; A1 \(\chi^2 = 2.78\) (3 s.f.); A1 \(p = 0.249\). (c) M1 comparing \(p\) with
0.05; A1 insufficient evidence to reject \(H_0\): subject choice appears independent of year.
Final answers: \(H_0\): independent, \(H_1\): not independent; \(\chi^2 \approx 2.78\),
\(p \approx 0.249\); do not reject \(H_0\).
