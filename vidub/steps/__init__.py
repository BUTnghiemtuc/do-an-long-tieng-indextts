"""8 bước của pipeline, theo đúng thứ tự chạy."""

from .align import Align
from .diarize import Diarize
from .extract import Extract
from .mix import Mix
from .separate import Separate
from .synthesize import Synthesize
from .transcribe import Transcribe
from .translate import Translate

STEPS = [Extract(), Separate(), Diarize(), Transcribe(), Translate(), Synthesize(), Align(), Mix()]
