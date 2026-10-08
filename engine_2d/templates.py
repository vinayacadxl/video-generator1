"""Pure High-Fidelity PIL Slide Engine for 2D Mathematical & Physics Explanations.
Eliminates font/latex drops and renders 100% visible, sharp, beautiful slides.
Supports progressive disclosure: steps and answers appear only when actively explained.
"""

import os
import re
import textwrap
from PIL import Image, ImageDraw, ImageFont


def sanitize_math_text(text):
    """Sanitizes raw LaTeX expressions and mathematical terms into clean, elegant, 100% readable text."""
    if not text:
        return ""
    s = str(text)

    # 1. LaTeX fractions: \frac{a}{b} or frac{a}{b} -> (a / b)
    s = re.sub(r"\\?frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"(\1 / \2)", s)
    s = re.sub(r"\\?frac\s*([a-zA-Z0-9_]+)\s*\{([^{}]+)\}", r"(\1 / \2)", s)

    # 2. Square roots: \sqrt{x} or sqrt{x} -> sqrt(x)
    s = re.sub(r"\\?sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", s)

    # 3. Subscripts & superscripts: Q_{enc} -> Q_enc
    s = re.sub(r"([a-zA-Z0-9])_\{([^{}]+)\}", r"\1_\2", s)
    s = re.sub(r"([a-zA-Z0-9])\^\{([^{}]+)\}", r"\1^\2", s)

    # 4. Standard symbols mapping to clean universal readable terms
    rep = {
        r"\lambda": "lambda", r"\epsilon_0": "eps0", r"\epsilon_{0}": "eps0", r"\varepsilon_0": "eps0",
        r"\sigma": "sigma", r"\rho": "rho", r"\pi": "pi", r"\infty": "infinity", r"\propto": "proportional to",
        r"\vec{E}": "E", r"\vec{A}": "A", r"\vec{r}": "r", r"\oint": "Integral", r"\int": "Integral",
        r"\cdot": " * ", r"\approx": " ~ ", r"\theta": "theta", r"\mu_0": "mu0", r"\Delta": "Delta",
        r"\partial": "d", r"\pm": "+/-", r"\times": " * ", r"\le": "<=", r"\ge": ">="
    }
    for k, v in rep.items():
        s = s.replace(k, v)

    # Clean backslashes and stray braces
    s = s.replace("\\", "")
    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def get_pil_fonts():
    """Loads clean TrueType system fonts with robust fallbacks."""
    for bold_f, reg_f in [("segoeuib.ttf", "segoeui.ttf"), ("arialbd.ttf", "arial.ttf")]:
        try:
            return {
                "badge": ImageFont.truetype(bold_f, 18),
                "title": ImageFont.truetype(bold_f, 32),
                "card_head": ImageFont.truetype(bold_f, 17),
                "body": ImageFont.truetype(reg_f, 20),
                "body_bold": ImageFont.truetype(bold_f, 20),
                "step_num": ImageFont.truetype(bold_f, 16),
                "ans_head": ImageFont.truetype(bold_f, 16),
                "ans": ImageFont.truetype(bold_f, 22),
                "q_title": ImageFont.truetype(bold_f, 18),
                "q_body": ImageFont.truetype(reg_f, 22),
                "caption_tag": ImageFont.truetype(bold_f, 14),
                "caption_text": ImageFont.truetype(reg_f, 19)
            }
        except Exception:
            continue

    default = ImageFont.load_default()
    return {k: default for k in [
        "badge", "title", "card_head", "body", "body_bold", "step_num",
        "ans_head", "ans", "q_title", "q_body", "caption_tag", "caption_text"
    ]}


class Scene2DTemplates:
    WIDTH = 1920
    HEIGHT = 1080

    @classmethod
    def _draw_background_grid(cls, draw):
        """Draws a subtle modern dark grid background."""
        for x in range(0, cls.WIDTH, 120):
            draw.line([(x, 0), (x, cls.HEIGHT)], fill=(18, 24, 38), width=1)
        for y in range(0, cls.HEIGHT, 120):
            draw.line([(0, y), (cls.WIDTH, y)], fill=(18, 24, 38), width=1)

    @classmethod
    def _draw_lecture_caption_bar(cls, draw, fonts, active_narration):
        """Draws a clean, dynamic lower-third narration card showing the active sentence being spoken."""
        if not active_narration:
            return

        clean_text = sanitize_math_text(str(active_narration))
        lines = textwrap.wrap(clean_text, width=105)
        if not lines:
            return

        # Lower-third glassmorphic bar (x: 80 to 1840, y: 920 to 1030)
        draw.rounded_rectangle([(80, 920), (1840, 1030)], radius=14, fill=(13, 20, 36), outline=(45, 60, 85), width=2)
        # Active speaker pill
        draw.rounded_rectangle([(105, 938), (285, 968)], radius=8, fill=(30, 41, 59), outline=(56, 189, 248), width=1)
        draw.text((120, 944), "* LECTURE FOCUS", fill=(56, 189, 248), font=fonts["caption_tag"])

        # Display active narration line(s)
        y_text = 942 if len(lines) == 1 else 932
        for l_idx, line in enumerate(lines[:2]):
            draw.text((310, y_text + (l_idx * 26)), line, fill=(241, 245, 249), font=fonts["caption_text"])

    @classmethod
    def create_title_slide(cls, title, subject="Physics", topic="Kinematics", question_text="", visible_question=True, active_narration="", spoken_text=""):
        """Generates an aesthetic educational title/intro slide using pure PIL."""
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), color=(7, 9, 14))
        draw = ImageDraw.Draw(img)
        fonts = get_pil_fonts()

        # Decorative background rings
        for r in range(200, 1100, 180):
            draw.ellipse([(1600 - r, 540 - r), (1600 + r, 540 + r)], outline=(24, 33, 50), width=1)

        # Subject & Topic Badge (Top Left)
        draw.rounded_rectangle([(160, 100), (620, 160)], radius=14, fill=(26, 24, 65), outline=(129, 140, 248), width=2)
        draw.text((190, 118), f"* {str(subject).upper()}  -  {str(topic).upper()}", fill=(165, 180, 252), font=fonts["badge"])

        # Title
        clean_title = sanitize_math_text(str(title))
        t_lines = textwrap.wrap(clean_title, width=44)
        t_y = 195
        for tl in t_lines[:2]:
            draw.text((160, t_y), tl, fill=(255, 255, 255), font=fonts["title"])
            t_y += 48

        # Keep the question visible while the spoken explanation advances beside it.
        if visible_question and question_text:
            draw.rounded_rectangle([(120, 320), (780, 880)], radius=18, fill=(15, 23, 42), outline=(56, 189, 248), width=2)
            draw.rounded_rectangle([(155, 350), (465, 392)], radius=8, fill=(30, 41, 59), outline=(56, 189, 248), width=1)
            draw.text((177, 360), "PROBLEM STATEMENT", fill=(56, 189, 248), font=fonts["q_title"])
            clean_q = sanitize_math_text(str(question_text))
            q_lines = textwrap.wrap(clean_q, width=43)
            q_y = 425
            for ql in q_lines[:13]:
                draw.text((155, q_y), ql, fill=(226, 232, 240), font=fonts["q_body"])
                q_y += 32

            draw.rounded_rectangle([(815, 320), (1800, 880)], radius=18, fill=(10, 18, 34), outline=(129, 140, 248), width=3)
            draw.rounded_rectangle([(855, 350), (1165, 392)], radius=8, fill=(32, 31, 76), outline=(129, 140, 248), width=1)
            draw.text((877, 360), "EXPLAINING NOW", fill=(190, 190, 255), font=fonts["q_title"])
            focus_text = sanitize_math_text(str(spoken_text or active_narration))
            focus_lines = textwrap.wrap(focus_text, width=66)
            focus_y = 445
            focus_font = ImageFont.truetype("segoeuib.ttf", 30) if os.path.exists("C:/Windows/Fonts/segoeuib.ttf") else fonts["q_body"]
            for line in focus_lines[:9]:
                draw.text((855, focus_y), line, fill=(248, 250, 252), font=focus_font)
                focus_y += 46
        elif spoken_text:
            draw.rounded_rectangle([(160, 320), (1760, 880)], radius=18, fill=(10, 18, 34), outline=(129, 140, 248), width=3)
            draw.text((200, 355), "EXPLAINING NOW", fill=(190, 190, 255), font=fonts["q_title"])
            focus_lines = textwrap.wrap(sanitize_math_text(str(spoken_text)), width=74)
            for index, line in enumerate(focus_lines[:9]):
                draw.text((200, 430 + index * 48), line, fill=(248, 250, 252), font=fonts["q_body"])

        # Active narration bar at bottom
        cls._draw_lecture_caption_bar(draw, fonts, active_narration)
        return img

    @classmethod
    def create_derivation_slide(cls, title, given_list, formula_tex, steps_list, visible_steps=0, active_step_idx=-1, subject="Physics", active_narration=""):
        """Generates a mathematical derivation slide with progressive reveal of steps.
        CRITICAL: Never renders the final answer box so students stay focused on current derivation.
        """
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), color=(8, 11, 18))
        draw = ImageDraw.Draw(img)
        fonts = get_pil_fonts()
        cls._draw_background_grid(draw)

        # Subject Badge (Top Left)
        draw.rounded_rectangle([(80, 35), (380, 80)], radius=12, fill=(24, 34, 52), outline=(56, 189, 248), width=2)
        draw.text((105, 46), f"* {str(subject).upper()} DERIVATION", fill=(56, 189, 248), font=fonts["badge"])

        # Slide Title
        clean_title = sanitize_math_text(str(title))
        draw.text((80, 98), clean_title[:65], fill=(248, 250, 252), font=fonts["title"])

        # Left Column: Given Values Card (x: 80 to 560, y: 165 to 480)
        draw.rounded_rectangle([(80, 165), (560, 480)], radius=16, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
        draw.text((110, 188), "GIVEN PARAMETERS", fill=(148, 163, 184), font=fonts["card_head"])

        y_g = 230
        givens = given_list or ["System configuration provided in problem"]
        for g in givens[:4]:
            clean_g = sanitize_math_text(str(g))
            lines = textwrap.wrap(clean_g, width=34)
            for l_idx, line in enumerate(lines[:2]):
                bullet = "- " if l_idx == 0 else "  "
                draw.text((110, y_g), f"{bullet}{line}", fill=(226, 232, 240), font=fonts["body"])
                y_g += 28
            y_g += 8

        # Left Column: Governing Formula Card (x: 80 to 560, y: 505 to 885)
        draw.rounded_rectangle([(80, 505), (560, 885)], radius=16, fill=(15, 23, 42), outline=(14, 165, 233), width=2)
        draw.text((110, 528), "GOVERNING FORMULA", fill=(56, 189, 248), font=fonts["card_head"])

        clean_formula = sanitize_math_text(str(formula_tex or "Apply Governing Relations"))
        f_lines = textwrap.wrap(clean_formula, width=28)
        y_f = 590
        for fl in f_lines[:5]:
            draw.text((110, y_f), fl, fill=(56, 189, 248), font=fonts["body_bold"])
            y_f += 34

        # Right Column: Step-by-Step Derivation Card (x: 600 to 1840, y: 165 to 885)
        # Note: Expands full height down to 885 since final answer box is intentionally omitted!
        draw.rounded_rectangle([(600, 165), (1840, 885)], radius=18, fill=(9, 14, 26), outline=(56, 189, 248), width=2)

        # Header with step progress indicator
        steps = steps_list or ["Execute analytical step substitution"]
        total_steps = min(len(steps), 4)
        progress_str = f"STEP-BY-STEP DERIVATION  ({min(visible_steps, total_steps)} of {total_steps} Revealed)"
        draw.text((640, 190), progress_str, fill=(56, 189, 248), font=fonts["card_head"])

        y_s = 245
        for idx in range(total_steps):
            is_revealed = (idx < visible_steps)
            is_active = (idx == active_step_idx)

            if not is_revealed:
                # Do NOT draw future steps so student is not distracted!
                continue

            clean_s = sanitize_math_text(str(steps[idx]))
            s_lines = textwrap.wrap(clean_s, width=72)
            card_height = max(70, len(s_lines[:3]) * 30 + 36)

            # Draw step card
            if is_active:
                # Active step: Elevated background, glowing electric cyan border, active badge
                draw.rounded_rectangle([(630, y_s), (1810, y_s + card_height)], radius=12, fill=(18, 32, 54), outline=(56, 189, 248), width=2)
                # Active step number circle
                draw.ellipse([(645, y_s + 14), (685, y_s + 54)], fill=(14, 165, 233), outline=(56, 189, 248), width=2)
                draw.text((660, y_s + 24), str(idx + 1), fill=(255, 255, 255), font=fonts["step_num"])
                # Active indicator badge
                draw.rounded_rectangle([(705, y_s + 12), (860, y_s + 38)], radius=6, fill=(14, 116, 144), outline=(56, 189, 248), width=1)
                draw.text((718, y_s + 17), "* EXPLAINING NOW", fill=(255, 255, 255), font=fonts["step_num"])
                # Step text in crisp white
                for l_idx, sl in enumerate(s_lines[:3]):
                    draw.text((705, y_s + 44 + (l_idx * 28)), sl, fill=(255, 255, 255), font=fonts["body_bold"])
            else:
                # Completed previous step: Calm slate styling
                draw.rounded_rectangle([(630, y_s), (1810, y_s + card_height)], radius=12, fill=(12, 18, 30), outline=(45, 58, 78), width=1)
                # Step circle
                draw.ellipse([(645, y_s + 14), (685, y_s + 54)], fill=(24, 34, 52), outline=(51, 65, 85), width=1)
                draw.text((660, y_s + 24), str(idx + 1), fill=(148, 163, 184), font=fonts["step_num"])
                # Step text in soft silver
                for l_idx, sl in enumerate(s_lines[:3]):
                    draw.text((705, y_s + 18 + (l_idx * 28)), sl, fill=(203, 213, 225), font=fonts["body"])

            y_s += card_height + 16

        # Active narration bar at bottom
        cls._draw_lecture_caption_bar(draw, fonts, active_narration)
        return img

    @classmethod
    def create_comparison_slide(cls, title, subject="Physics", formula_tex="", options=None,
                                active_narration="", active_option=""):
        """Shows answer choices for verification without replaying the derivation steps."""
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), color=(8, 11, 18))
        draw = ImageDraw.Draw(img)
        fonts = get_pil_fonts()
        cls._draw_background_grid(draw)

        draw.rounded_rectangle([(80, 35), (460, 80)], radius=12, fill=(24, 34, 52), outline=(56, 189, 248), width=2)
        draw.text((105, 46), f"* {str(subject).upper()} - OPTION CHECK", fill=(56, 189, 248), font=fonts["badge"])
        draw.text((80, 98), sanitize_math_text(str(title))[:65], fill=(248, 250, 252), font=fonts["title"])

        # Keep the governing relation visible as a compact reference, not the full
        # step list that was already taught in the derivation scene.
        draw.rounded_rectangle([(80, 165), (560, 885)], radius=16, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
        draw.text((110, 190), "REFERENCE RELATION", fill=(56, 189, 248), font=fonts["card_head"])
        formula_lines = textwrap.wrap(sanitize_math_text(str(formula_tex or "Compare each choice with the derived result.")), width=31)
        for index, line in enumerate(formula_lines[:10]):
            draw.text((110, 245 + index * 34), line, fill=(226, 232, 240), font=fonts["body_bold"])

        draw.rounded_rectangle([(600, 165), (1840, 885)], radius=18, fill=(9, 14, 26), outline=(56, 189, 248), width=2)
        draw.text((640, 190), "COMPARE THE GIVEN OPTIONS", fill=(56, 189, 248), font=fonts["card_head"])
        choice_list = list(options or [])[:4]
        if not choice_list:
            choice_list = ["Use the spoken explanation to compare each choice with the reference relation."]

        top = 245
        available_height = 600
        card_gap = 14
        card_height = min(132, (available_height - card_gap * (len(choice_list) - 1)) // len(choice_list))
        for index, option_text in enumerate(choice_list):
            y0 = top + index * (card_height + card_gap)
            is_active = bool(active_option and str(option_text).lstrip().upper().startswith(active_option.upper()))
            fill = (18, 32, 54) if is_active else (12, 18, 30)
            outline = (56, 189, 248) if is_active else (45, 58, 78)
            draw.rounded_rectangle([(630, y0), (1810, y0 + card_height)], radius=12, fill=fill, outline=outline, width=2 if is_active else 1)
            letter = str(option_text).strip()[:1].upper() if str(option_text).strip() else str(index + 1)
            draw.ellipse([(650, y0 + 14), (690, y0 + 54)], fill=(14, 165, 233) if is_active else (24, 34, 52), outline=outline, width=1)
            draw.text((664, y0 + 24), letter, fill=(255, 255, 255), font=fonts["step_num"])
            clean_option = sanitize_math_text(str(option_text))
            lines = textwrap.wrap(clean_option, width=88)
            for line_index, line in enumerate(lines[:3]):
                draw.text((710, y0 + 20 + line_index * 28), line, fill=(255, 255, 255) if is_active else (203, 213, 225), font=fonts["body_bold"] if is_active else fonts["body"])

        cls._draw_lecture_caption_bar(draw, fonts, active_narration)
        return img

    @classmethod
    def create_conclusion_slide(cls, title, subject="Physics", topic="Summary", takeaways_list=None, formula_tex=None, answer_str="", show_answer=False, active_narration=""):
        """Generates the dedicated Conclusion slide.
        CRITICAL: The Final Answer Box is shown ONLY when show_answer=True (at the end of the video).
        """
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), color=(8, 11, 18))
        draw = ImageDraw.Draw(img)
        fonts = get_pil_fonts()
        cls._draw_background_grid(draw)

        # Subject Badge (Top Left)
        draw.rounded_rectangle([(80, 35), (420, 80)], radius=12, fill=(30, 27, 75), outline=(129, 140, 248), width=2)
        draw.text((105, 46), f"* {str(subject).upper()} - CONCLUSION", fill=(165, 180, 252), font=fonts["badge"])

        # Slide Title
        clean_title = sanitize_math_text(str(title or "Conclusion & Final Solution"))
        draw.text((80, 98), clean_title[:65], fill=(248, 250, 252), font=fonts["title"])

        # Left Column: Problem Summary & Core Principle (x: 80 to 650, y: 165 to 500)
        draw.rounded_rectangle([(80, 165), (650, 500)], radius=16, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
        draw.text((110, 188), "CONCEPTUAL SUMMARY", fill=(148, 163, 184), font=fonts["card_head"])

        draw.text((110, 230), f"Topic: {str(topic).title()}", fill=(56, 189, 248), font=fonts["body_bold"])
        summary_points = [
            "Derived from foundational physical conservation laws",
            "Symmetry and boundary conditions verified analytical result",
            "Validated against all possible answer choices"
        ]
        y_sp = 275
        for sp in summary_points:
            draw.text((110, y_sp), f"* {sp}", fill=(203, 213, 225), font=fonts["body"])
            y_sp += 36

        # Left Column: Governing Equation Card (x: 80 to 650, y: 525 to 885)
        draw.rounded_rectangle([(80, 525), (650, 885)], radius=16, fill=(15, 23, 42), outline=(14, 165, 233), width=2)
        draw.text((110, 548), "GOVERNING PRINCIPLE APPLIED", fill=(56, 189, 248), font=fonts["card_head"])

        clean_formula = sanitize_math_text(str(formula_tex or "Symmetry & Integral Relation"))
        f_lines = textwrap.wrap(clean_formula, width=32)
        y_f = 610
        for fl in f_lines[:4]:
            draw.text((110, y_f), fl, fill=(56, 189, 248), font=fonts["body_bold"])
            y_f += 36

        # Right Column: Key Exam Takeaways Card (x: 690 to 1840, y: 165 to 500)
        draw.rounded_rectangle([(690, 165), (1840, 500)], radius=16, fill=(9, 14, 26), outline=(99, 102, 241), width=2)
        draw.text((720, 188), "KEY EXAM TAKEAWAYS & PROBLEM STRATEGY", fill=(165, 180, 252), font=fonts["card_head"])

        takeaways = takeaways_list or [
            "Always identify spatial symmetry before choosing coordinate axes or surfaces.",
            "Double-check units and dimensional consistency in the intermediate steps.",
            "Eliminate physically implausible options by testing boundary limits."
        ]
        y_t = 240
        for t_idx, item in enumerate(takeaways[:3]):
            clean_item = sanitize_math_text(str(item))
            draw.ellipse([(720, y_t), (752, y_t + 32)], fill=(30, 27, 75), outline=(129, 140, 248), width=1)
            draw.text((732, y_t + 7), str(t_idx + 1), fill=(165, 180, 252), font=fonts["step_num"])
            t_lines = textwrap.wrap(clean_item, width=70)
            for tl_idx, tl in enumerate(t_lines[:2]):
                draw.text((770, y_t + (tl_idx * 28)), tl, fill=(226, 232, 240), font=fonts["body"])
            y_t += max(48, len(t_lines[:2]) * 28 + 18)

        # Right Column: FINAL ANSWER BOX (x: 690 to 1840, y: 525 to 885)
        # CRITICAL: Revealed ONLY when show_answer=True!
        if not show_answer:
            # Placeholder before answer is officially stated: Clean analysis card
            draw.rounded_rectangle([(690, 525), (1840, 885)], radius=16, fill=(12, 18, 30), outline=(51, 65, 85), width=2)
            draw.rounded_rectangle([(720, 550), (950, 586)], radius=8, fill=(24, 34, 52), outline=(56, 189, 248), width=1)
            draw.text((735, 558), "ANALYSIS COMPLETE", fill=(56, 189, 248), font=fonts["card_head"])
            draw.text((720, 640), "Final algebraic derivation confirmed.", fill=(203, 213, 225), font=fonts["body_bold"])
            draw.text((720, 680), "Preparing definitive conclusion and verified answer statement...", fill=(148, 163, 184), font=fonts["body"])
        else:
            # Radiant Glassmorphic Emerald Celebration Card for the Final Answer!
            draw.rounded_rectangle([(690, 525), (1840, 885)], radius=16, fill=(6, 42, 28), outline=(52, 211, 153), width=3)
            # Emerald Header Badge
            draw.rounded_rectangle([(720, 550), (1050, 592)], radius=8, fill=(4, 120, 87), outline=(52, 211, 153), width=2)
            draw.text((740, 560), "* DEFINITIVE VERIFIED ANSWER *", fill=(255, 255, 255), font=fonts["ans_head"])

            clean_ans = sanitize_math_text(str(answer_str or "Verified Analytical Solution"))
            ans_lines = [l.strip() for l in clean_ans.split("\n") if l.strip()]
            if not ans_lines:
                ans_lines = [clean_ans]

            y_a = 625
            for al in ans_lines[:4]:
                wrapped_al = textwrap.wrap(al, width=65)
                for w_idx, wl in enumerate(wrapped_al[:2]):
                    prefix = "✔  " if w_idx == 0 else "   "
                    draw.text((720, y_a), f"{prefix}{wl}", fill=(167, 243, 208), font=fonts["ans"])
                    y_a += 38
                y_a += 8

        # Active narration bar at bottom
        cls._draw_lecture_caption_bar(draw, fonts, active_narration)
        return img

    @classmethod
    def create_calculation_slide(cls, title, given_list, formula_tex, steps_list, answer_str, subject="Physics", show_answer=False, active_narration=""):
        """Backwards compatibility wrapper for calculation slides."""
        if show_answer:
            return cls.create_conclusion_slide(
                title=title, subject=subject, takeaways_list=steps_list,
                formula_tex=formula_tex, answer_str=answer_str, show_answer=True,
                active_narration=active_narration
            )
        else:
            return cls.create_derivation_slide(
                title=title, given_list=given_list, formula_tex=formula_tex,
                steps_list=steps_list, visible_steps=len(steps_list) if steps_list else 1,
                active_step_idx=-1, subject=subject, active_narration=active_narration
            )
