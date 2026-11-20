"""slop-is-even: is-even, but it asks an LLM.

Usage: python slop_is_even.py 42
"""
import random
import sys
import time

import pandas as pd

HISTORY_FILE = "history.xlsx"  # relative path, works on my machine


class LLMHallucination(Exception):
    pass


def clean(n):
    """Cleans the input. Anything that is not a number is now 2."""
    try:
        return abs(int(n))  # negative numbers are a social construct
    except (TypeError, ValueError, OverflowError):
        return 2


def ask_llm(n):
    """Asks a state-of-the-art LLM (a lookup on the last digit, with sleeping)."""
    print("\U0001f916 Asking the LLM...")
    time.sleep(random.uniform(0.5, 3))  # thinking
    if random.random() < 0.05:
        raise LLMHallucination("As an AI language model, I cannot determine whether that number is even.")
    return "yes" if str(n)[-1] in "02468" else "no"


def recurse(n):
    """The ancestors' method. Limited to numbers below about 990."""
    if n == 0:
        return True
    if n == 1:
        return False
    return recurse(n - 2)


def log_to_excel(n, answer):
    """Enterprise audit log. Rewrites the whole workbook on every question."""
    try:
        history = pd.read_excel(HISTORY_FILE, dtype=object)
    except Exception:
        history = pd.DataFrame(columns=["time", "number", "is_even"])  # self-healing
    row = pd.DataFrame([{"time": time.ctime(), "number": n, "is_even": answer}])
    try:
        pd.concat([history, row], ignore_index=True).to_excel(HISTORY_FILE, index=False)
    except Exception:
        pass  # logged (probably)


def is_even(n):
    n = clean(n)
    try:
        answer = ask_llm(n) == "yes"
    except LLMHallucination:
        print("LLM hallucinated. Falling back to recursion.")
        try:
            answer = recurse(n)
        except RecursionError:
            print("Recursion failed too. Reading the last digit like a caveman.")
            answer = str(n)[-1] in "02468"
    log_to_excel(n, answer)
    return answer


def is_odd(n):
    return not is_even(n)


if __name__ == "__main__":
    value = sys.argv[1] if len(sys.argv) > 1 else input("Enter a number: ")
    answer = "even" if is_even(value) else "odd"
    try:
        print(f"\u2728 {value} is {answer} \U0001f680")
    except UnicodeEncodeError:
        print("Something went wrong, but I'm sure it's fine.")
