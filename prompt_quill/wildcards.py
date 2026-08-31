# Wildcard resolution and LLM output cleanup.
# Ported from the original Prompt Quill (llama_index_pq/pq/shared.py),
# with the globals/numpy dependencies removed.

import os
import random
import re
from typing import Dict, List, Optional, Tuple, Union


class WildcardResolver:
    def __init__(self, wildcards_dir: str = "wildcards", cache_files: bool = True):
        self.wildcards_dir = wildcards_dir
        self.cache_files = cache_files
        self.wildcard_cache: Dict[str, List[str]] = {}
        self.iter_state: Dict[str, int] = {}
        self.separator = " and "
        self.max_depth = 10
        self.max_retries = 1
        self.resolved_values = {}
        self.active_wildcards = set()

    def load_wildcard_file(self, wildcard: str, count: int = 1) -> List[str]:
        if wildcard in self.wildcard_cache and self.cache_files:
            options = self.wildcard_cache[wildcard]
        else:
            wildcard_file = os.path.join(self.wildcards_dir, f"{wildcard}.txt")
            if os.path.exists(wildcard_file):
                with open(wildcard_file, "r", encoding="utf-8") as f:
                    options = [line.strip() for line in f if line.strip()]
            else:
                found = False
                for root, _, files in os.walk(self.wildcards_dir):
                    if f"{wildcard}.txt" in files:
                        wildcard_file = os.path.join(root, f"{wildcard}.txt")
                        with open(wildcard_file, "r", encoding="utf-8") as f:
                            options = [line.strip() for line in f if line.strip()]
                        found = True
                        break
                if not found:
                    options = []

            if self.cache_files:
                self.wildcard_cache[wildcard] = options

        if not options:
            return ["MISSING_FILE"] * count

        unique_options = list(set(options))
        if len(unique_options) < count:
            selected = unique_options
        else:
            selected = random.sample(unique_options, count)
        return selected

    def parse_inline_options(self, options_str: str) -> List[Tuple]:
        if not options_str:
            return [(" ", 1.0)]
        parts = re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', options_str)
        is_iter = False
        repeat_count = 1
        if parts and parts[0].strip().startswith("iter"):
            is_iter = True
            iter_part = parts[0].strip()
            if iter_part.startswith("iter "):
                try:
                    repeat_count = int(iter_part.split(" ")[1])
                    parts = parts[1:]
                except (IndexError, ValueError):
                    parts = parts[1:]
            else:
                parts = parts[1:]

        options = []
        wildcard_pattern = r"(\d*)x?__([^_]+)__"
        for part in parts:
            part = part.strip()
            # Parse weight (e.g., "red:0.7")
            if ':' in part and not part.startswith('"'):
                opt, weight = part.rsplit(':', 1)
                try:
                    weight = float(weight)
                    if weight < 0:
                        weight = 0.0  # No negative weights
                except ValueError:
                    weight = 1.0  # Default if invalid
                opt = opt.strip()
            else:
                opt = part
                weight = 1.0

            if opt.startswith('"') and opt.endswith('"'):
                opt = opt[1:-1]
                if re.match(wildcard_pattern, opt):
                    match = re.findall(wildcard_pattern, opt)[0]
                    count = int(match[0]) if match[0] else 1
                    wildcard = match[1]
                    options.extend([(item, weight) for item in self.load_wildcard_file(wildcard, count)])
                else:
                    options.append((opt, weight))
            else:
                if re.match(wildcard_pattern, opt):
                    match = re.findall(wildcard_pattern, opt)[0]
                    count = int(match[0]) if match[0] else 1
                    wildcard = match[1]
                    options.extend([(item, weight) for item in self.load_wildcard_file(wildcard, count)])
                else:
                    options.append((opt, weight))

        if is_iter:
            return [("iter", repeat_count, options)]
        # Weighted random choice
        if options:
            items, weights = zip(*options)
            return [(random.choices(items, weights=weights, k=1)[0], 1.0)]
        return [(" ", 1.0)]

    def find_inline_matches(self, prompt: str) -> List[str]:
        matches = []
        i = 0
        while i < len(prompt):
            if prompt[i] == '[':
                start = i + 1
                depth = 1
                while i + 1 < len(prompt) and depth > 0:
                    i += 1
                    if prompt[i] == '[':
                        depth += 1
                    elif prompt[i] == ']':
                        depth -= 1
                if depth == 0:
                    matches.append(prompt[start:i])
            i += 1
        return matches

    def resolve_prompt(
            self,
            prompt: str,
            max_combinations: Optional[int] = None,
            recursive: bool = True,
            separator: str = " and ",
            max_depth: int = 10,
            max_retries: int = 1,
            resolved_values: Optional[dict] = None,
            depth: int = 0,
            active_wildcards: Optional[set] = None
    ) -> Union[str, List[str]]:
        wildcard_pattern = r"(\d*)x?__([\w-]+)__"
        multi_wildcard_pattern = r"\{(\d+)\$\$__([\w-]+)__(:[\d\.]+)?\}"
        weighted_wildcard_pattern = r"__([\w-]+)__:([\d\.]+)"
        choice_pattern = r"\{([^}]+)\}"

        # Stop if max depth is reached
        if depth >= max_depth:
            return prompt if max_combinations is None else [prompt]

        # Initialize resolved_values and active_wildcards if not provided (top-level call)
        if resolved_values is None:
            resolved_values = {}
        if active_wildcards is None:
            active_wildcards = set()

        wildcards = re.findall(wildcard_pattern, prompt)
        multi_wildcards = re.findall(multi_wildcard_pattern, prompt)
        weighted_wildcards = re.findall(weighted_wildcard_pattern, prompt)
        inline_matches = self.find_inline_matches(prompt)
        inline_options = [self.parse_inline_options(match) for match in inline_matches]
        choice_matches = re.findall(choice_pattern, prompt)

        if not wildcards and not multi_wildcards and not weighted_wildcards and not inline_matches and not choice_matches:
            return prompt if max_combinations is None else [prompt]

        def resolve_wildcard_replacement(key, count, wildcard, type=None, weight=None, depth=0):
            if depth >= max_depth:
                return f"{{MAX_DEPTH_REACHED:{wildcard}}}"
            if key in active_wildcards:
                return f"{{CYCLE_DETECTED:{wildcard}}}"

            active_wildcards.add(key)

            if key in resolved_values:
                active_wildcards.remove(key)
                return resolved_values[key]

            if type == "multi":
                options = self.load_wildcard_file(wildcard, count)
                if len(options) < count:
                    options = options * (count // len(options) + 1)[:count]
                weight_value = float(weight[1:]) if weight else 1.0
                replacement = separator.join(options) if random.random() < weight_value else ""
            elif type == "weighted":
                weight_value = float(weight)
                options = self.load_wildcard_file(wildcard, 1)
                replacement = separator.join(options) if random.random() < weight_value else ""
            else:
                options = self.load_wildcard_file(wildcard, count if count > 0 else 1)
                replacement = separator.join(options)

            if recursive and (
                    re.search(wildcard_pattern, replacement) or
                    re.search(multi_wildcard_pattern, replacement) or
                    re.search(weighted_wildcard_pattern, replacement)
            ):
                replacement = self.resolve_prompt(
                    replacement,
                    None,
                    recursive,
                    separator,
                    max_depth,
                    max_retries,
                    resolved_values,
                    depth + 1,
                    active_wildcards
                )

            active_wildcards.remove(key)
            resolved_values[key] = replacement
            return replacement

        def attempt_resolution(prompt, attempt, depth=0, recursive=True):
            if depth >= max_depth:
                return prompt
            resolved = prompt

            # Choice pattern first
            choice_matches = re.findall(r"\{([^}\$]+)\}", resolved)
            for match in choice_matches:
                options = [opt.strip() for opt in match.split("|")]
                if options:
                    replacement = random.choice(options)
                    if recursive and (
                            re.search(wildcard_pattern, replacement) or
                            re.search(multi_wildcard_pattern, replacement) or
                            re.search(weighted_wildcard_pattern, replacement) or
                            re.search(choice_pattern, replacement)
                    ):
                        replacement = self.resolve_prompt(
                            replacement, None, recursive, self.separator, self.max_depth, self.max_retries,
                            resolved_values, depth + 1, active_wildcards
                        )
                    target = f"{{{match}}}"
                    resolved = re.sub(re.escape(target), replacement, resolved)

            # Multi-wildcards
            for count, wildcard, weight in multi_wildcards:
                count = int(count)
                key = (count, wildcard, "multi", weight)
                if key not in resolved_values:
                    replacement = resolve_wildcard_replacement(key, count, wildcard, "multi", weight, depth + 1)
                else:
                    replacement = resolved_values[key]
                weight_str = weight if weight else ""
                target = f"{{{count}$$__{wildcard}__{weight_str}}}"
                resolved = re.sub(re.escape(target), replacement, resolved)

            # Weighted plain wildcards
            for wildcard, weight in weighted_wildcards:
                key = (0, wildcard, "weighted", weight)
                if key not in resolved_values:
                    replacement = resolve_wildcard_replacement(key, 0, wildcard, "weighted", weight, depth + 1)
                else:
                    replacement = resolved_values[key]
                target = f"__{wildcard}__:{weight}"
                resolved = re.sub(re.escape(target), replacement, resolved)

            # Plain wildcards
            for count, wildcard in wildcards:
                if wildcard not in [w for w, _ in weighted_wildcards]:
                    count = int(count) if count else 0
                    key = (count, wildcard)
                    if key not in resolved_values:
                        replacement = resolve_wildcard_replacement(key, count, wildcard, depth=depth + 1)
                    else:
                        replacement = resolved_values[key]
                    target = f"{count}x__{wildcard}__" if count > 0 else f"__{wildcard}__"
                    resolved = re.sub(re.escape(target), replacement, resolved)

            return resolved

        num_outputs = 1 if max_combinations is None else 1
        results = []
        for _ in range(num_outputs):
            best_resolved = prompt
            for attempt in range(max_retries):
                resolved = attempt_resolution(prompt, attempt, depth)
                best_resolved = resolved
                if not (re.search(wildcard_pattern, resolved) or
                        re.search(multi_wildcard_pattern, resolved) or
                        re.search(weighted_wildcard_pattern, resolved)):
                    break

            for match, opts in zip(inline_matches, inline_options):
                if len(opts) == 1 and isinstance(opts[0], tuple) and opts[0][0] == "iter":
                    repeat_count, iter_opts = opts[0][1], opts[0][2]
                    state_key = match
                    if state_key not in self.iter_state:
                        self.iter_state[state_key] = 0  # Initialize the iterator state
                    total_items = len(iter_opts) * repeat_count
                    current_idx = self.iter_state[state_key] % total_items
                    opt_idx = current_idx // repeat_count
                    replacement = iter_opts[opt_idx][0]
                    if recursive and re.search(r"[\[\]]|(\d*)x?__[\w-]+__|\{(\d+)\$\$__([\w-]+)__(:[\d\.]+)?\}", best_resolved):
                        replacement = self.resolve_prompt(
                            replacement,
                            None,
                            True,
                            separator,
                            max_depth,
                            max_retries,
                            resolved_values,
                            depth + 1,
                            active_wildcards
                        )
                    self.iter_state[state_key] += 1  # Increment the iterator state
                else:
                    replacement = opts[0][0]
                    if recursive and re.search(r"[\[\]]|(\d*)x?__[\w-]+__|\{(\d+)\$\$__([\w-]+)__(:[\d\.]+)?\}", best_resolved):
                        replacement = self.resolve_prompt(
                            replacement, None, recursive, self.separator, self.max_depth, self.max_retries,
                            resolved_values, depth + 1, active_wildcards
                        )
                best_resolved = best_resolved.replace(f"[{match}]", replacement, 1)
            results.append(best_resolved)

        return results[0]


def repair_brackets(txt):
    # split the text into words
    words = txt.split()
    # create an empty list to store the repaired words
    repaired_words = []
    # iterate over the words and check for unbalanced brackets
    for word in words:
        if word.startswith('('):
            if word.endswith(')'):
                repaired_words.append(word)
            else:
                if word[-1] in ',.!?':
                    repaired_words.append(word[:-1] + ')' + word[-1])
                else:
                    repaired_words.append(word + ')')
        elif word.endswith(')'):
            if word[0] in ',.!?':
                repaired_words.append(word[0] + '(' + word[1:])
            else:
                repaired_words.append('(' + word)
        elif word[-1] in ',.!?':
            if ')' in word:
                repaired_words.append('(' + word[:-1] + word[-1])
            else:
                repaired_words.append(word)
        else:
            repaired_words.append(word)
    return ' '.join(repaired_words)


def repair_brackets_snipets(text):
    text = list(text)
    out_text = list(text)
    stack = []

    for i, char in enumerate(text):
        if char == '(':
            stack.append(i)
        elif char == ')':
            if stack:
                stack.pop()
            else:
                out_text.insert(0, '(')

    for _ in stack:
        out_text.append(')')

    return ''.join(out_text)


def fix_array_brackets(text):
    out = []
    for word in text:
        if word != '':
            out.append(repair_brackets_snipets(word.strip()))
    return out


def clean_llm_artefacts(prompt):
    """
    Cleans potential artefacts left behind by LLMs from a given prompt.

    Removes leading newlines, an "Answer: " prefix and other common
    generation artefacts (verbatim port of the original implementation).
    """
    unfixed = prompt
    prompt = repair_brackets(prompt)
    if prompt == '':
        prompt = unfixed

    prompt = re.sub(r"\s+", " ", prompt)
    if '\n' in prompt:
        prompt = re.sub(r'.*\n', '', prompt)

    artefacts = ['Answer: ', 'Steps: ', 'scale: ', 'Seed: ', 'Face restoration: ', 'Size: ', 'Model hash: ', 'Model: ', 'Clip skip: ',
                 'Token merging ratio: ', r'ADetailer .*?: ', '"', r'\[', r'\]', r'\{', r'\}']

    for artefact in artefacts:
        if artefact in prompt:
            prompt = re.sub(rf'.*{artefact}', '', prompt)

    pattern = r"<\|(.*?)\|>"
    prompt = re.sub(pattern, "", prompt)
    pattern = r"<(.*?)>"
    prompt = re.sub(pattern, "", prompt)

    return prompt


def get_negative_prompt(negative_prompt_list, default_negative_prompt):
    """Pick the RAG-derived negative prompt if it is substantial, else the default."""
    if len(negative_prompt_list) > 0:
        fixed = fix_array_brackets(list(negative_prompt_list))
        last_negative_prompt = ','.join(fixed)
        if len(last_negative_prompt) < 30:
            last_negative_prompt = default_negative_prompt
        if last_negative_prompt != '':
            return last_negative_prompt
    return default_negative_prompt
