import io
import re
import textwrap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image


class MathRenderer:
    @staticmethod
    def clean_latex(latex_str):
        if not latex_str:
            return ""
        s = latex_str.strip()
        if s.startswith("$$") and s.endswith("$$"):
            s = s[2:-2].strip()
        elif s.startswith("$") and s.endswith("$"):
            s = s[1:-1].strip()
        return s

    @staticmethod
    def is_pure_math(latex_str):
        if not latex_str:
            return False
        clean = MathRenderer.clean_latex(latex_str)
        # Check if it has many plain English words without standard math syntax
        words = [w for w in clean.split() if len(w) > 1]
        if len(words) >= 3 and not any(c in clean for c in ['\\', '^', '_', '=']):
            return False
        if any(c in clean for c in ['\\frac', '\\sqrt', '^', '_', '\\cdot', '\\times', '\\approx', '\\pm']):
            return True
        if '=' in clean and len(words) <= 4:
            return True
        return False

    @staticmethod
    def render_equation_to_image(latex_str, font_size=28, color="#00e5ff", dpi=200):
        """Renders LaTeX mathematical equation to PIL Image with transparent background."""
        clean = MathRenderer.clean_latex(latex_str)
        fig = plt.figure(figsize=(8, 2), dpi=dpi)
        fig.patch.set_alpha(0.0)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.patch.set_alpha(0.0)
        ax.axis('off')

        if MathRenderer.is_pure_math(clean):
            try:
                formatted_tex = f"${clean}$"
                ax.text(
                    0.5, 0.5, formatted_tex,
                    fontsize=font_size,
                    color=color,
                    ha='center', va='center',
                    transform=ax.transAxes,
                    math_fontfamily='cm'
                )
            except Exception:
                ax.text(
                    0.5, 0.5, clean,
                    fontsize=font_size - 4,
                    color=color,
                    fontweight='bold',
                    ha='center', va='center',
                    transform=ax.transAxes
                )
        else:
            ax.text(
                0.5, 0.5, clean,
                fontsize=font_size - 4,
                color=color,
                fontweight='bold',
                ha='center', va='center',
                transform=ax.transAxes
            )

        buf = io.BytesIO()
        plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0.1, dpi=dpi)
        plt.close(fig)
        buf.seek(0)
        return Image.open(buf)
