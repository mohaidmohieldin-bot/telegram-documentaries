"""Gateway routing: Bouncer, interview, finale, portrait, narration script and voiceover."""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Chat, Document, Message, PhotoSize, Update
from telegram.error import NetworkError
from telegram.ext import Application, BaseHandler

from telegram_documentaries import gateway
from telegram_documentaries.bouncer import BouncerError, BouncerVerdict
from telegram_documentaries.converter import ConverterError
from telegram_documentaries.gateway import DEPS_KEY, Deps, build_application
from telegram_documentaries.interviewer import InterviewerError, NextQuestion
from telegram_documentaries.media import MAX_IMAGE_BYTES, ImageInput, PortraitImage, VoiceoverAudio
from telegram_documentaries.narrator import NarratorError
from telegram_documentaries.scripter import ScripterError
from telegram_documentaries.session import (
    QA,
    Dossier,
    InterviewHandoff,
    NarrationScript,
    Phase,
    SessionStore,
)
from tests.audio_fakes import make_wav

FAKE_TOKEN = "123456789:AAH-fake-token-for-tests"
PHOTO_BYTES = b"\xff\xd8person-or-landscape"
PHOTO = ImageInput(data=PHOTO_BYTES, mime_type="image/jpeg")

HUMAN = BouncerVerdict(human_present=True, reason="A person smiling.")
NO_HUMAN = BouncerVerdict(human_present=False, reason="A mountain landscape.")
DOSSIER = Dossier(
    profile="A nocturnal snack strategist who alphabetises spices.",
    quirks=("hums while thinking", "collects mugs"),
    suggested_animal="raccoon",
    animal_rationale="Night-time foraging and a love of shiny things.",
)


class FakeBouncer:
    def __init__(self, verdict: BouncerVerdict | None = HUMAN, error: Exception | None = None):
        self.verdict = verdict
        self.error = error
        self.images: list[ImageInput] = []

    async def check(self, image: ImageInput) -> BouncerVerdict:
        self.images.append(image)
        if self.error:
            raise self.error
        assert self.verdict is not None
        return self.verdict


Step = NextQuestion | Dossier | Exception


class FakeInterviewer:
    """Returns scripted steps; records every transcript it was shown."""

    def __init__(self, first: str | Exception = "What do you hoard?", *steps: Step) -> None:
        self.first = first
        self.steps = list(steps)
        self.transcripts: list[tuple[QA, ...]] = []

    async def first_question(self) -> str:
        if isinstance(self.first, Exception):
            raise self.first
        return self.first

    async def next_step(self, transcript: Sequence[QA]) -> NextQuestion | Dossier:
        self.transcripts.append(tuple(transcript))
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


class FakeConverter:
    """Returns scripted portraits or errors; records every handoff it received."""

    def __init__(self, *results: PortraitImage | Exception) -> None:
        self.results = list(results) or [PORTRAIT]
        self.handoffs: list[InterviewHandoff] = []

    async def convert(self, handoff: InterviewHandoff) -> PortraitImage:
        self.handoffs.append(handoff)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


PORTRAIT = PortraitImage(data=b"\x89PNG-hybrid", mime_type="image/png")
SCRIPT = NarrationScript(text=" ".join(["Here, in the hush of dusk, the raccoon stirs."] * 7))


VOICEOVER = VoiceoverAudio(data=make_wav(25.0))


class FakeNarrator:
    """Returns scripted voiceovers or errors; records every script it narrated."""

    def __init__(self, *results: VoiceoverAudio | Exception) -> None:
        self.results = list(results) or [VOICEOVER]
        self.scripts: list[NarrationScript] = []

    async def narrate(self, script: NarrationScript) -> VoiceoverAudio:
        self.scripts.append(script)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeScripter:
    """Returns scripted narrations or errors; records every handoff it received."""

    def __init__(self, *results: NarrationScript | Exception) -> None:
        self.results = list(results) or [SCRIPT]
        self.handoffs: list[InterviewHandoff] = []

    async def write(self, handoff: InterviewHandoff) -> NarrationScript:
        self.handoffs.append(handoff)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def ask(question: str) -> NextQuestion:
    return NextQuestion(question=question, enough_information=False)


# --- Fake Telegram objects ------------------------------------------------------------


def telegram_file(data: bytes = PHOTO_BYTES, error: Exception | None = None) -> MagicMock:
    tg_file = MagicMock()
    tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(data), side_effect=error)
    return tg_file


def fake_message(
    *,
    text: str | None = None,
    photo_size: int | None = None,
    document_mime: str | None = None,
    document_size: int = 1_000,
    tg_file: MagicMock | None = None,
) -> MagicMock:
    message = MagicMock()
    message.reply_text = AsyncMock()
    message.reply_photo = AsyncMock()
    message.reply_document = AsyncMock()
    message.text = text
    message.photo = ()
    message.document = None
    tg_file = tg_file or telegram_file()
    if photo_size is not None:
        small = MagicMock(file_size=100, get_file=AsyncMock(return_value=telegram_file(b"tiny")))
        large = MagicMock(file_size=photo_size, get_file=AsyncMock(return_value=tg_file))
        message.photo = (small, large)  # Telegram lists sizes smallest first
    if document_mime is not None:
        message.document = MagicMock(
            mime_type=document_mime,
            file_size=document_size,
            get_file=AsyncMock(return_value=tg_file),
        )
    return message


def fake_update(message: MagicMock | None, chat_id: int = 42) -> MagicMock:
    update = MagicMock(spec=Update)
    update.update_id = 1
    update.effective_message = message
    update.effective_chat = MagicMock(id=chat_id) if message is not None else None
    return update


def make_deps(
    bouncer: FakeBouncer | None = None,
    interviewer: FakeInterviewer | None = None,
    converter: FakeConverter | None = None,
    scripter: FakeScripter | None = None,
    narrator: FakeNarrator | None = None,
) -> Deps:
    return Deps(
        bouncer=bouncer or FakeBouncer(),
        interviewer=interviewer or FakeInterviewer(),
        converter=converter or FakeConverter(),
        scripter=scripter or FakeScripter(),
        narrator=narrator or FakeNarrator(),
        sessions=SessionStore(),
    )


def make_context(deps: Deps) -> MagicMock:
    context = MagicMock()
    context.bot_data = {DEPS_KEY: deps}
    return context


def replies(message: MagicMock) -> list[str]:
    return [str(call.args[0]) for call in message.reply_text.await_args_list]


def replied(message: MagicMock) -> str:
    message.reply_text.assert_awaited_once()
    return replies(message)[0]


async def send_photo(deps: Deps, chat_id: int = 42, **kwargs: object) -> MagicMock:
    message = fake_message(photo_size=50_000, **kwargs)  # type: ignore[arg-type]
    await gateway.on_photo(fake_update(message, chat_id), make_context(deps))
    return message


async def send_text(deps: Deps, text: str | None, chat_id: int = 42) -> MagicMock:
    message = fake_message(text=text)
    await gateway.on_other(fake_update(message, chat_id), make_context(deps))
    return message


def interviewing(deps: Deps, question: str = "What do you hoard?", chat_id: int = 42) -> Deps:
    deps.sessions.start_interview(chat_id, PHOTO, question)
    return deps


# --- Before the interview ---------------------------------------------------------------


async def test_text_before_photo_gets_nudge() -> None:
    message = await send_text(make_deps(), "hi")
    assert replied(message) == gateway.NUDGE_SEND_PHOTO


async def test_landscape_photo_is_rejected_and_resets() -> None:
    deps = make_deps(FakeBouncer(NO_HUMAN))
    message = await send_photo(deps)
    assert replied(message) == gateway.BOUNCER_REJECTION
    assert deps.sessions.get(42).phase is Phase.AWAITING_PHOTO


# --- Starting the interview --------------------------------------------------------------


async def test_person_photo_starts_interview_with_first_question() -> None:
    deps = make_deps(FakeBouncer(HUMAN), FakeInterviewer("What do you hoard?"))
    message = await send_photo(deps)

    assert replies(message) == [
        gateway.PHOTO_ACCEPTED,
        gateway.format_question(1, "What do you hoard?"),
    ]
    session = deps.sessions.get(42)
    assert session.phase is Phase.INTERVIEWING
    assert session.photo == PHOTO
    assert session.pending_question == "What do you hoard?"


async def test_first_question_failure_keeps_awaiting_photo() -> None:
    deps = make_deps(FakeBouncer(HUMAN), FakeInterviewer(InterviewerError("timed out")))
    message = await send_photo(deps)
    assert replied(message) == gateway.INTERVIEWER_UNAVAILABLE_START
    assert deps.sessions.get(42).phase is Phase.AWAITING_PHOTO


# --- Answering, one question per turn ----------------------------------------------------


async def test_answer_is_recorded_and_next_question_sent() -> None:
    interviewer = FakeInterviewer("Q1?", ask("Q2?"))
    deps = interviewing(make_deps(interviewer=interviewer), "Q1?")
    message = await send_text(deps, "  Spoons.  ")

    assert replied(message) == gateway.format_question(2, "Q2?")
    assert interviewer.transcripts == [(QA(question="Q1?", answer="Spoons."),)]
    session = deps.sessions.get(42)
    assert session.transcript == (QA(question="Q1?", answer="Spoons."),)
    assert session.pending_question == "Q2?"


async def test_full_run_delivers_portrait_then_narration(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="telegram_documentaries")
    interviewer = FakeInterviewer("Q1?", ask("Q2?"), ask("Q3?"), ask("Q4?"), ask("Q5?"), DOSSIER)
    converter = FakeConverter(PORTRAIT)
    scripter = FakeScripter(SCRIPT)
    narrator = FakeNarrator(VOICEOVER)
    deps = make_deps(FakeBouncer(HUMAN), interviewer, converter, scripter, narrator)
    await send_photo(deps)

    for n in range(1, 5):
        message = await send_text(deps, f"Answer {n}")
        assert replied(message) == gateway.format_question(n + 1, f"Q{n + 1}?")
        assert len(deps.sessions.get(42).transcript) == n

    finale = await send_text(deps, "Answer 5")
    texts = replies(finale)
    assert texts == [
        gateway.format_finale(DOSSIER),
        gateway.format_script(SCRIPT),
        gateway.THATS_A_WRAP,
    ]
    assert SCRIPT.text in texts[1]
    finale.reply_document.assert_awaited_once_with(
        document=VOICEOVER.data,
        filename="voiceover.wav",
        caption=gateway.VOICEOVER_CAPTION,
        write_timeout=gateway.MEDIA_TRANSFER_TIMEOUT_S,
        read_timeout=gateway.MEDIA_TRANSFER_TIMEOUT_S,
    )
    assert narrator.scripts == [SCRIPT]
    for expected in (DOSSIER.profile, "hums while thinking", "raccoon", "Developing"):
        assert expected in texts[0]

    finale.reply_photo.assert_awaited_once_with(
        photo=PORTRAIT.data,
        caption=gateway.format_caption(DOSSIER),
        write_timeout=gateway.MEDIA_TRANSFER_TIMEOUT_S,
        read_timeout=gateway.MEDIA_TRANSFER_TIMEOUT_S,
    )
    session = deps.sessions.get(42)
    handoff = InterviewHandoff(photo=PHOTO, dossier=DOSSIER, transcript=session.transcript)
    assert converter.handoffs == [handoff]
    assert scripter.handoffs == [handoff]
    assert session.phase is Phase.DONE
    assert session.script == SCRIPT
    assert [qa.answer for qa in session.transcript] == [f"Answer {n}" for n in range(1, 6)]
    assert "event=interview_handoff_ready chat_id=42" in caplog.text
    assert "event=portrait_delivered chat_id=42 animal='raccoon'" in caplog.text
    assert "event=script_ready chat_id=42 words=63" in caplog.text
    assert "event=voiceover_delivered chat_id=42 seconds=25.0" in caplog.text
    assert "PNG-hybrid" not in caplog.text  # portrait bytes never logged


def test_media_transfers_allow_time_for_large_files() -> None:
    # python-telegram-bot defaults to 5 s, which large generated images exceed: the photo
    # arrives but the bot times out and the session wrongly stays undelivered.
    assert gateway.MEDIA_TRANSFER_TIMEOUT_S >= 60


def test_caption_names_the_animal() -> None:
    assert gateway.format_caption(DOSSIER) == "📸 Exhibit A: Homo sapiens × raccoon"


# --- Wrong input mid-interview: nudge, no state change -----------------------------------


@pytest.mark.parametrize("text", [None, "", "   ", "/start", "/restart now"])
async def test_non_answers_get_nudge_repeating_the_question(text: str | None) -> None:
    interviewer = FakeInterviewer("Q1?")
    deps = interviewing(make_deps(interviewer=interviewer), "Q1?")
    before = deps.sessions.get(42)
    message = await send_text(deps, text)

    assert replied(message) == gateway.format_nudge(1, "Q1?")
    assert deps.sessions.get(42) == before
    assert interviewer.transcripts == []


async def test_overlong_answer_is_refused() -> None:
    interviewer = FakeInterviewer("Q1?")
    deps = interviewing(make_deps(interviewer=interviewer), "Q1?")
    message = await send_text(deps, "x" * 1001)
    assert replied(message) == gateway.format_too_long(1, "Q1?")
    assert interviewer.transcripts == []
    assert deps.sessions.get(42).transcript == ()


async def test_photo_mid_interview_gets_nudge_without_bouncer() -> None:
    bouncer = FakeBouncer()
    deps = interviewing(make_deps(bouncer), "Q1?")
    deps.sessions.record_answer(42, "A1", "Q2?")
    message = await send_photo(deps)
    assert replied(message) == gateway.format_nudge(2, "Q2?")
    assert bouncer.images == []
    assert deps.sessions.get(42).pending_question == "Q2?"


async def test_interviewer_failure_does_not_record_and_retry_works() -> None:
    interviewer = FakeInterviewer("Q1?", InterviewerError("quota"), ask("Q2?"))
    deps = interviewing(make_deps(interviewer=interviewer), "Q1?")

    failed = await send_text(deps, "Spoons.")
    assert replied(failed) == gateway.INTERVIEWER_UNAVAILABLE
    assert deps.sessions.get(42).transcript == ()

    retried = await send_text(deps, "Spoons.")
    assert replied(retried) == gateway.format_question(2, "Q2?")
    assert len(deps.sessions.get(42).transcript) == 1


# --- Portrait: failure, retry, afterwards ---------------------------------------------------


def completed(deps: Deps) -> Deps:
    interviewing(deps, "Q1?")
    deps.sessions.complete_interview(42, "A1", DOSSIER)
    return deps


async def test_converter_failure_keeps_results_and_invites_retry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    converter = FakeConverter(ConverterError("model returned no image"))
    deps = interviewing(make_deps(interviewer=FakeInterviewer("Q1?", DOSSIER), converter=converter))
    message = await send_text(deps, "Final answer")

    assert replies(message) == [gateway.format_finale(DOSSIER), gateway.CONVERTER_FAILED]
    message.reply_photo.assert_not_awaited()
    session = deps.sessions.get(42)
    assert session.phase is Phase.INTERVIEW_COMPLETE
    assert session.dossier == DOSSIER
    assert "event=converter_failed chat_id=42" in caplog.text


async def test_any_text_after_failure_retries_the_portrait() -> None:
    converter = FakeConverter(PORTRAIT)
    deps = completed(make_deps(converter=converter))
    message = await send_text(deps, "try again please")

    assert replies(message) == [
        gateway.RETRYING_PORTRAIT,
        gateway.format_script(SCRIPT),
        gateway.THATS_A_WRAP,
    ]
    message.reply_photo.assert_awaited_once()
    assert len(converter.handoffs) == 1
    assert deps.sessions.get(42).phase is Phase.DONE


async def test_failed_retry_stays_retryable() -> None:
    deps = completed(make_deps(converter=FakeConverter(ConverterError("timed out"))))
    message = await send_text(deps, "again")
    assert replies(message) == [gateway.RETRYING_PORTRAIT, gateway.CONVERTER_FAILED]
    assert deps.sessions.get(42).phase is Phase.INTERVIEW_COMPLETE


async def test_telegram_send_failure_leaves_portrait_retryable() -> None:
    deps = completed(make_deps())
    message = fake_message(text="again")
    message.reply_photo = AsyncMock(side_effect=NetworkError("upload failed"))
    with pytest.raises(NetworkError):  # the application's error handler logs it
        await gateway.on_other(fake_update(message), make_context(deps))
    assert deps.sessions.get(42).phase is Phase.INTERVIEW_COMPLETE


# --- Script: failure, retry, afterwards ---------------------------------------------------------


def portrait_delivered(deps: Deps) -> Deps:
    completed(deps).sessions.deliver_portrait(42)
    return deps


async def test_scripter_failure_keeps_portrait_and_invites_retry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    scripter = FakeScripter(ScripterError("draft rejected twice: narration has 41 words"))
    deps = completed(make_deps(scripter=scripter))
    message = await send_text(deps, "go")  # retries the portrait, which succeeds

    assert replies(message) == [gateway.RETRYING_PORTRAIT, gateway.SCRIPTER_FAILED]
    message.reply_photo.assert_awaited_once()
    assert deps.sessions.get(42).phase is Phase.PORTRAIT_DELIVERED
    assert "event=scripter_failed chat_id=42" in caplog.text


async def test_text_after_script_failure_retries_only_the_script() -> None:
    converter = FakeConverter()
    scripter = FakeScripter(SCRIPT)
    deps = portrait_delivered(make_deps(converter=converter, scripter=scripter))
    message = await send_text(deps, "again")

    assert replies(message) == [
        gateway.RETRYING_SCRIPT,
        gateway.format_script(SCRIPT),
        gateway.THATS_A_WRAP,
    ]
    message.reply_photo.assert_not_awaited()
    assert converter.handoffs == []
    assert deps.sessions.get(42).phase is Phase.DONE


async def test_failed_script_retry_stays_retryable() -> None:
    deps = portrait_delivered(make_deps(scripter=FakeScripter(ScripterError("timed out"))))
    message = await send_text(deps, "again")
    assert replies(message) == [gateway.RETRYING_SCRIPT, gateway.SCRIPTER_FAILED]
    assert deps.sessions.get(42).phase is Phase.PORTRAIT_DELIVERED


# --- Voiceover: failure, retry, afterwards ---------------------------------------------------


def script_ready(deps: Deps) -> Deps:
    portrait_delivered(deps).sessions.store_script(42, SCRIPT)
    return deps


async def test_narrator_failure_keeps_script_and_invites_retry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    narrator = FakeNarrator(NarratorError("TTS returned no audio"))
    deps = portrait_delivered(make_deps(narrator=narrator))
    message = await send_text(deps, "go")  # retries the script, which succeeds

    assert replies(message) == [
        gateway.RETRYING_SCRIPT,
        gateway.format_script(SCRIPT),
        gateway.NARRATOR_FAILED,
    ]
    message.reply_document.assert_not_awaited()
    session = deps.sessions.get(42)
    assert session.phase is Phase.SCRIPT_READY
    assert session.script == SCRIPT
    assert "event=narrator_failed chat_id=42" in caplog.text


async def test_text_after_narrator_failure_retries_only_the_voiceover() -> None:
    scripter = FakeScripter()
    narrator = FakeNarrator(VOICEOVER)
    deps = script_ready(make_deps(scripter=scripter, narrator=narrator))
    message = await send_text(deps, "again")

    assert replies(message) == [gateway.RETRYING_VOICEOVER, gateway.THATS_A_WRAP]
    message.reply_document.assert_awaited_once()
    message.reply_photo.assert_not_awaited()
    assert scripter.handoffs == []
    assert narrator.scripts == [SCRIPT]
    assert deps.sessions.get(42).phase is Phase.DONE


async def test_failed_voiceover_retry_stays_retryable() -> None:
    deps = script_ready(make_deps(narrator=FakeNarrator(NarratorError("timed out"))))
    message = await send_text(deps, "again")
    assert replies(message) == [gateway.RETRYING_VOICEOVER, gateway.NARRATOR_FAILED]
    assert deps.sessions.get(42).phase is Phase.SCRIPT_READY


async def test_telegram_upload_failure_leaves_voiceover_retryable() -> None:
    deps = script_ready(make_deps())
    message = fake_message(text="again")
    message.reply_document = AsyncMock(side_effect=NetworkError("upload failed"))
    with pytest.raises(NetworkError):  # the application's error handler logs it
        await gateway.on_other(fake_update(message), make_context(deps))
    assert deps.sessions.get(42).phase is Phase.SCRIPT_READY


async def test_text_when_done_gets_wrap_reply() -> None:
    narrator = FakeNarrator()
    deps = script_ready(make_deps(narrator=narrator))
    deps.sessions.finish(42)
    message = await send_text(deps, "hello?")
    assert replied(message) == gateway.THATS_A_WRAP
    assert narrator.scripts == []


@pytest.mark.parametrize("stage", ["completed", "portrait", "script", "done"])
async def test_new_photo_after_interview_starts_fresh(stage: str) -> None:
    deps = completed(make_deps(interviewer=FakeInterviewer("Fresh Q?")))
    if stage in ("portrait", "script", "done"):
        deps.sessions.deliver_portrait(42)
    if stage in ("script", "done"):
        deps.sessions.store_script(42, SCRIPT)
    if stage == "done":
        deps.sessions.finish(42)
    message = await send_photo(deps)
    assert replies(message)[-1] == gateway.format_question(1, "Fresh Q?")
    session = deps.sessions.get(42)
    assert session.phase is Phase.INTERVIEWING
    assert session.dossier is None
    assert session.script is None


async def test_chats_are_isolated() -> None:
    interviewer = FakeInterviewer("Q1?")
    deps = make_deps(FakeBouncer(HUMAN), interviewer)
    await send_photo(deps, chat_id=1)
    other = await send_text(deps, "hi", chat_id=2)
    assert replied(other) == gateway.NUDGE_SEND_PHOTO
    assert deps.sessions.get(1).phase is Phase.INTERVIEWING
    assert interviewer.transcripts == []


# --- Photo intake edge cases (Bouncer stage, unchanged behaviour) ----------------------------


async def test_png_sent_as_file_is_checked_as_png() -> None:
    bouncer = FakeBouncer(HUMAN)
    message = fake_message(document_mime="image/png")
    await gateway.on_photo(fake_update(message), make_context(make_deps(bouncer)))
    assert bouncer.images[0].mime_type == "image/png"


async def test_unsupported_image_type_is_refused_before_bouncer() -> None:
    bouncer = FakeBouncer()
    message = fake_message(document_mime="image/gif")
    await gateway.on_photo(fake_update(message), make_context(make_deps(bouncer)))
    assert replied(message) == gateway.UNSUPPORTED_IMAGE
    assert bouncer.images == []


async def test_oversized_photo_is_refused_without_downloading() -> None:
    bouncer = FakeBouncer()
    tg_file = telegram_file()
    message = fake_message(photo_size=MAX_IMAGE_BYTES + 1, tg_file=tg_file)
    await gateway.on_photo(fake_update(message), make_context(make_deps(bouncer)))
    assert replied(message) == gateway.PHOTO_TOO_LARGE
    tg_file.download_as_bytearray.assert_not_awaited()
    assert bouncer.images == []


async def test_largest_photo_size_is_downloaded() -> None:
    bouncer = FakeBouncer()
    await send_photo(make_deps(bouncer))
    assert bouncer.images[0].data == PHOTO_BYTES  # not the b"tiny" thumbnail


@pytest.mark.parametrize("data", [b"", None])
async def test_download_failure_gets_friendly_reply(
    data: bytes | None, caplog: pytest.LogCaptureFixture
) -> None:
    error = NetworkError("down") if data is None else None
    deps = make_deps()
    message = await send_photo(deps, tg_file=telegram_file(data or b"", error=error))
    assert replied(message) == gateway.PHOTO_DOWNLOAD_FAILED
    assert deps.sessions.get(42).phase is Phase.AWAITING_PHOTO
    assert "event=photo_download_failed" in caplog.text


async def test_bouncer_failure_gets_friendly_reply(caplog: pytest.LogCaptureFixture) -> None:
    deps = make_deps(FakeBouncer(error=BouncerError("timed out")))
    message = await send_photo(deps)
    assert replied(message) == gateway.BOUNCER_UNAVAILABLE
    assert "event=bouncer_failed" in caplog.text


async def test_verdict_is_logged_without_image_bytes(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="telegram_documentaries")
    await send_photo(make_deps(FakeBouncer(NO_HUMAN)), chat_id=777)
    assert "event=bouncer_verdict chat_id=777 human_present=False" in caplog.text
    assert "person-or-landscape" not in caplog.text


async def test_update_without_message_is_ignored() -> None:
    interviewer = FakeInterviewer()
    deps = make_deps(interviewer=interviewer)
    await gateway.on_photo(fake_update(None), make_context(deps))
    await gateway.on_other(fake_update(None), make_context(deps))
    assert interviewer.transcripts == []


# --- Application routing (real Telegram objects) ------------------------------------------------


def real_message(**kwargs: object) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=42, type=Chat.PRIVATE),
        **kwargs,  # type: ignore[arg-type]
    )


def matching_callbacks(app: Application, update: Update) -> list[object]:  # type: ignore[type-arg]
    """Callbacks of the handlers that would receive this update (first match per group)."""
    callbacks: list[object] = []
    for group in app.handlers.values():
        handler: BaseHandler  # type: ignore[type-arg]
        for handler in group:
            if handler.check_update(update):
                callbacks.append(handler.callback)
                break
    return callbacks


@pytest.fixture
def app() -> Application:  # type: ignore[type-arg]
    return build_application(FAKE_TOKEN, make_deps())


def test_photo_routes_to_photo_handler(app: Application) -> None:  # type: ignore[type-arg]
    photo = PhotoSize(file_id="f", file_unique_id="u", width=10, height=10)
    update = Update(update_id=1, message=real_message(photo=(photo,)))
    assert matching_callbacks(app, update) == [gateway.on_photo]


def test_image_document_routes_to_photo_handler(app: Application) -> None:  # type: ignore[type-arg]
    doc = Document(file_id="f", file_unique_id="u", mime_type="image/png")
    update = Update(update_id=1, message=real_message(document=doc))
    assert matching_callbacks(app, update) == [gateway.on_photo]


@pytest.mark.parametrize("text", ["hi", "/help", "🦁"])
def test_text_routes_to_other_handler(app: Application, text: str) -> None:  # type: ignore[type-arg]
    update = Update(update_id=1, message=real_message(text=text))
    assert matching_callbacks(app, update) == [gateway.on_other]


def test_edited_messages_are_ignored(app: Application) -> None:  # type: ignore[type-arg]
    update = Update(update_id=2, edited_message=real_message(text="edited"))
    assert matching_callbacks(app, update) == []


def test_application_registers_an_error_handler(app: Application) -> None:  # type: ignore[type-arg]
    assert app.error_handlers


def test_application_stores_deps(app: Application) -> None:  # type: ignore[type-arg]
    assert isinstance(app.bot_data[DEPS_KEY], Deps)
