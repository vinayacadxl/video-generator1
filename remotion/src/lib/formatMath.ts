/** Convert LaTeX-ish strings into readable on-screen math (no raw backslashes). */

export function formatMath(input: string): string {
  if (!input) return "";
  let s = String(input).trim();

  // If it doesn't look like LaTeX, return as-is
  if (!/[\\{}^_]/.test(s) && !/\$/.test(s)) return s;

  s = s.replace(/\$\$?/g, "");
  s = s.replace(/\\vec\{([^}]+)\}/g, "⃗$1");
  s = s.replace(/\\mathbf\{([^}]+)\}/g, "$1");
  s = s.replace(/\\mathrm\{([^}]+)\}/g, "$1");
  s = s.replace(/\\text\{([^}]+)\}/g, "$1");
  s = s.replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, "($1)/($2)");
  s = s.replace(/\\dfrac\{([^}]+)\}\{([^}]+)\}/g, "($1)/($2)");
  s = s.replace(/\\sqrt\{([^}]+)\}/g, "√($1)");
  s = s.replace(/\\left/g, "");
  s = s.replace(/\\right/g, "");
  s = s.replace(/\\cdot/g, "·");
  s = s.replace(/\\times/g, "×");
  s = s.replace(/\\pm/g, "±");
  s = s.replace(/\\approx/g, "≈");
  s = s.replace(/\\neq/g, "≠");
  s = s.replace(/\\leq/g, "≤");
  s = s.replace(/\\geq/g, "≥");
  s = s.replace(/\\rightarrow/g, "→");
  s = s.replace(/\\to/g, "→");
  s = s.replace(/\\infty/g, "∞");
  s = s.replace(/\\partial/g, "∂");
  s = s.replace(/\\nabla/g, "∇");
  s = s.replace(/\\pi/g, "π");
  s = s.replace(/\\theta/g, "θ");
  s = s.replace(/\\phi/g, "φ");
  s = s.replace(/\\rho/g, "ρ");
  s = s.replace(/\\epsilon_?0|\\varepsilon_?0|\\epsilon_\{0\}/g, "ε₀");
  s = s.replace(/\\epsilon/g, "ε");
  s = s.replace(/\\varepsilon/g, "ε");
  s = s.replace(/\\mu_?0|\\mu_\{0\}/g, "μ₀");
  s = s.replace(/\\alpha/g, "α");
  s = s.replace(/\\beta/g, "β");
  s = s.replace(/\\gamma/g, "γ");
  s = s.replace(/\\delta/g, "δ");
  s = s.replace(/\\omega/g, "ω");
  s = s.replace(/\\Omega/g, "Ω");
  s = s.replace(/\\sum/g, "Σ");
  s = s.replace(/\\int/g, "∫");
  s = s.replace(/\\oint/g, "∮");

  // subscripts / superscripts _{...} ^{...}
  const subMap: Record<string, string> = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
    a: "ₐ", e: "ₑ", o: "ₒ", x: "ₓ", i: "ᵢ", r: "ᵣ", n: "ₙ",
  };
  const supMap: Record<string, string> = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻",
  };

  s = s.replace(/_\{([^}]+)\}/g, (_m, body: string) =>
    body
      .split("")
      .map((ch) => subMap[ch] || ch)
      .join("")
  );
  s = s.replace(/\^\{([^}]+)\}/g, (_m, body: string) =>
    body
      .split("")
      .map((ch) => supMap[ch] || ch)
      .join("")
  );
  s = s.replace(/_([A-Za-z0-9])/g, (_m, ch: string) => subMap[ch] || `_${ch}`);
  s = s.replace(/\^([A-Za-z0-9])/g, (_m, ch: string) => supMap[ch] || `^${ch}`);

  // Remove remaining latex commands/braces lightly
  s = s.replace(/\\[a-zA-Z]+/g, "");
  s = s.replace(/[{}]/g, "");
  s = s.replace(/\s+/g, " ").trim();
  return s;
}
