import linecache
from ._scrubber import scrub_vars

CONTEXT_LINES = 5


def _is_in_app(filename):
    return "site-packages" not in filename and "/lib/python" not in filename


def extract_frames(exc):
    """Walk exc.__traceback__, return list of frame dicts with rich context."""
    frames = []
    tb = exc.__traceback__
    while tb is not None:
        frame = tb.tb_frame
        lineno = tb.tb_lineno
        filename = frame.f_code.co_filename
        function = frame.f_code.co_name

        context_line = linecache.getline(filename, lineno).rstrip("\n")

        all_lines = linecache.getlines(filename)
        start = max(0, lineno - 1 - CONTEXT_LINES)
        end = min(len(all_lines), lineno + CONTEXT_LINES)
        pre_context = [l.rstrip("\n") for l in all_lines[start : lineno - 1]]
        post_context = [l.rstrip("\n") for l in all_lines[lineno:end]]

        local_vars = scrub_vars(frame.f_locals)

        frames.append(
            {
                "filename": filename,
                "function": function,
                "lineno": lineno,
                "context_line": context_line,
                "pre_context": pre_context,
                "post_context": post_context,
                "vars": local_vars,
                "in_app": _is_in_app(filename),
            }
        )
        tb = tb.tb_next
    return frames


def extract_exception_chain(exc):
    """Walk __cause__ and __context__ to build the full exception chain.

    Returns a list of dicts:
      - Index 0: the outermost (raised) exception, chain_type=None
      - Index 1+: causes/contexts, chain_type="cause" or "context"

    The chain is ordered outermost-first so the frontend can reverse for display.
    """
    chain = []
    seen = set()
    current = exc
    chain_type = None

    while current is not None and id(current) not in seen:
        seen.add(id(current))

        try:
            frames = extract_frames(current)
        except Exception:
            frames = []

        chain.append(
            {
                "type": type(current).__name__,
                "value": str(current),
                "stacktrace": frames,
                "chain_type": chain_type,
            }
        )

        # Follow the chain: __cause__ takes priority (explicit `raise X from Y`)
        if current.__cause__ is not None:
            current = current.__cause__
            chain_type = "cause"
        elif not getattr(current, "__suppress_context__", False) and current.__context__ is not None:
            current = current.__context__
            chain_type = "context"
        else:
            break

    return chain
