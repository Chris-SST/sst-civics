# Example questions: IB Mathematics: analysis and approaches

Style examples for the generator, written as drafts for SST tutor review. Not past-paper
material. One per type.

## mcq, difficulty 2, AA-1.2, SL, no calculator

Which expression is equal to \(\log_3 81 - \log_3 9\)?
A. \(\log_3 72\)  B. \(2\)  C. \(9\)  D. \(\log_3 90\)
Answer: B. Solution: \(\log_3 81 - \log_3 9 = \log_3 \frac{81}{9} = \log_3 9 = 2\).
Distractors: subtracting arguments (A), dividing arguments without taking the log (C), adding
arguments (D).

## numeric, difficulty 3, AA-5.1, SL, calculator allowed

The height of a plant \(t\) weeks after planting is modelled by
\(h(t) = 4 + 3\ln(t + 1)\) centimetres. Find the rate of growth, in cm per week, when
\(t = 5\). Give your answer to three significant figures.
Answer: 0.5 (cm per week), tolerance 0.01.
Solution: \(h'(t) = \frac{3}{t+1}\), so \(h'(5) = \frac{3}{6} = 0.500\).

## short, difficulty 3, AA-2.2, SL, no calculator

The quadratic \(f(x) = x^2 - 6x + k\) has exactly one real root. Write down the value of
\(k\).
Answer: `9`. Solution: one real root means the discriminant is zero: \(36 - 4k = 0\), so
\(k = 9\).

## structured, difficulty 4, AA-5.2, HL, no calculator, 6 marks

Let \(f(x) = x e^{2x}\).
(a) Find \(\int x e^{2x}\,dx\). [4]
(b) Hence find the exact area between the curve, the \(x\)-axis and the lines \(x = 0\) and
\(x = 1\). [2]
Mark scheme: (a) M1 choosing \(u = x\), \(dv = e^{2x}dx\); A1 \(v = \frac{1}{2}e^{2x}\);
M1 applying parts \(\frac{x}{2}e^{2x} - \int \frac{1}{2}e^{2x}dx\); A1
\(\frac{x}{2}e^{2x} - \frac{1}{4}e^{2x} + C\). (b) M1 substituting limits; A1
\(\frac{e^2}{4} + \frac{1}{4}\).
Final answers: \(\frac{x}{2}e^{2x} - \frac{1}{4}e^{2x} + C\); \(\frac{e^2 + 1}{4}\).
