from typing import Callable, List, Union, Dict, TypedDict, cast, Callable, Set, Sequence
import urllib.request
import json
import aqt
from aqt import mw
import aqt.gui_hooks
from aqt.main import AnkiQt
from aqt.utils import showInfo
from aqt.operations import QueryOp
from aqt.qt.qt6 import (
    QDialog,
    QComboBox,
    QPushButton,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QHBoxLayout,
    pyqtSignal,
    QObject,
    QApplication,
    QVBoxLayout,
    QWidget,
    QFont,
    QCloseEvent,
    QIcon,
    QFontDatabase,
)
from anki.collection import Collection
from anki.decks import DeckId, DeckDict
from anki.notes import NoteId, Note
from anki.models import NotetypeDict

AI_BUTTON_URI = "anki_storytime__ai_button"
MAX_VOCAB_WORDS = 100

OPENAI_RESPONSE_URL = "https://api.openai.com/v1/responses"


class StoryView(QWidget):
    def __init__(self, stories: List[str], idx: int=-1, font_size_idx: int=4):
        super().__init__()
        config: Config = get_config()
        self.font_sizes = QFontDatabase.standardSizes()
        self.font_size_idx = font_size_idx
        self.story_font: QFont = QFont()
        self.story_font.setPointSize(self.font_sizes[font_size_idx])
        

        layout: QVBoxLayout = QVBoxLayout()
        font_row_layout: QHBoxLayout = QHBoxLayout()
        
        # Text view
        text_view: QPlainTextEdit = QPlainTextEdit()
        text_view.setReadOnly(True)
        text_view.setPlainText(stories[idx])
        self.text_view = text_view

        # Combo box
        story_select: QComboBox = QComboBox()
        for story in stories:
            story_select.addItem(story[0:48] + '...', userData=story)
        story_select.setCurrentIndex(len(stories) - 1)
        self.story_select = story_select
        story_select.currentIndexChanged.connect(self.story_select_on_change)
    
        # Font Box
        curr_font: str = self.text_view.fontInfo().family()
        if config['story_font_family'] == '':
            config['story_font_family'] = curr_font
            save_config(config)
        else:
            curr_font = config['story_font_family']
            
        font_select: QComboBox = QComboBox()
        font_select.addItems(QFontDatabase.families())
        font_select.setCurrentText(curr_font)
        font_row_layout.addWidget(font_select)
        font_select.currentIndexChanged.connect(self.font_select_on_change)
        self.font_select = font_select
        
        self.story_font.setFamily(curr_font)

        if curr_font in QFontDatabase.families():
            self.text_view.setFont(self.story_font)
        else:
            # The font from the config was not found. 
            # Reset config back to empty string, and show error
            showInfo(f"An error occured loading the font '{curr_font}' from config, falling back to Anki default.")
            config['story_font_family'] = ''
            save_config(config)

        
        # Copy to clipboard button
        copy_button: QPushButton = QPushButton()
        copy_button.setText("Copy to clipboard")
        copy_button.clicked.connect(self.copy_to_clipboard_on_click)

        # Font size buttons
        for (change, icon) in [(-1, QIcon.ThemeIcon.ListRemove), (1, QIcon.ThemeIcon.ListAdd)]:
            font_size_button: QPushButton = QPushButton()
            font_size_button.setIcon(QIcon.fromTheme(icon))
            font_size_button.clicked.connect(self.font_size_on_click_factory(change))
            font_row_layout.addWidget(font_size_button)

        # Layout
        layout.addWidget(story_select)
        layout.addLayout(font_row_layout)
        layout.addWidget(text_view)
        layout.addWidget(copy_button)

        self.setLayout(layout)

        self.setWindowTitle("Anki Storytime")
        self.resize(800, 600)
        self.text_view = text_view

    def copy_to_clipboard_on_click(self) -> None:
        app: QApplication = mw.app
        clipboard_success: bool = False
        clipboard = app.clipboard()
        if clipboard is not None:
            clipboard.setText(self.text_view.toPlainText())
            clipboard_success = True

        if not clipboard_success:
            raise Exception("Failed to copy to clipboard")

    def story_select_on_change(self):
        self.text_view.setPlainText(self.story_select.currentData())

    def closeEvent(self, a0: QCloseEvent | None):
        config: Config = get_config()
        
        if config['story_font_size_idx'] != self.font_size_idx:
            # Update the font size so that it may persist
            config['story_font_size_idx'] = self.font_size_idx 
            save_config(config)

        if a0:
            a0.accept()

    def font_size_on_click_factory(self, change: int):
        def font_size_on_click():
            new_font_size_idx: int = self.font_size_idx + change

            if new_font_size_idx < 0:
                new_font_size_idx = 0
            if new_font_size_idx >= len(self.font_sizes):
                new_font_size_idx = len(self.font_sizes) - 1


            self.font_size_idx = new_font_size_idx 
            self.story_font.setPointSize(self.font_sizes[self.font_size_idx])

            self.text_view.setFont(self.story_font)
        return font_size_on_click
            
    def font_select_on_change(self):
        curr_font: str = self.font_select.currentText()
        self.story_font.setFamily(curr_font)
        self.text_view.setFont(self.story_font)
        config = get_config()
        if config['story_font_family'] != curr_font:
            config['story_font_family'] = curr_font
            save_config(config)



class NoteTypeForm(QDialog):
    def __init__(self, new_notes: Dict[str, Note]):
        super().__init__()
        layout: QFormLayout = QFormLayout()
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        header_label: QLabel = QLabel(
            "The following are note types that have yet to have the correct field specified for use in this addon. Please use the dropdowns to select the field with your Japanese vocab."
        )
        header_label.setWordWrap(True)
        layout.addRow(header_label)
        self.note_selects: Dict[str, QComboBox] = {}
        new_note: Note
        for name, new_note in new_notes.items():
            select: QComboBox = QComboBox()
            select.addItems([value[0:32] for value in new_note.fields])
            self.note_selects[name] = select
            layout.addRow(QLabel(name), select)

        self.finished_button: QPushButton = QPushButton("Confirm")
        self.finished_button.clicked.connect(self.on_confirm)
        layout.addRow(self.finished_button)

        self.setLayout(layout)

    def on_confirm(self):
        config: Config = get_config()
        note_type_field = config["note_type_field"]

        for name, select in self.note_selects.items():
            note_type_field[name] = select.currentIndex()
        save_config(config)
        self.close()


class Preset(TypedDict):
    name: str
    value: str


class SaveDialog(QDialog):
    def __init__(self, preset_name: str):
        super().__init__()
        # `presets` should be a reference to the presets
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.accept)
        layout: QFormLayout = QFormLayout()
        self.name_input: QLineEdit = QLineEdit()
        self.name_input.setText(preset_name)
        layout.addRow("Name", self.name_input)
        layout.addWidget(self.save_button)
        self.setLayout(layout)


class PresetFieldRow(QObject):
    preset_update: pyqtSignal = pyqtSignal(dict)

    def __init__(self, presets: List[Preset], text_area: bool = False):
        super().__init__()
        self.value_field_dirty: bool = False
        self.presets_modified: bool = False
        self.presets = presets
        self.text_area = text_area

        self.row = QHBoxLayout()

        self.save_button = QPushButton("Save")
        self.reset_button = QPushButton("Reset")

        self.preset_select = QComboBox()
        self.preset_select.currentIndexChanged.connect(self.select_on_change)
        self.value_field: Union[QPlainTextEdit, QLineEdit]

        self.get_value: Callable[[], str]

        if text_area:
            self.get_value = lambda: cast(
                QPlainTextEdit, self.value_field
            ).toPlainText()
            self.value_field = QPlainTextEdit()
        else:
            self.get_value = lambda: cast(QLineEdit, self.value_field).text()
            self.value_field = QLineEdit()

        self.row.addWidget(self.preset_select)
        self.row.addWidget(self.value_field)
        self.row.addWidget(self.save_button)
        self.row.addWidget(self.reset_button)

        # Hide them until we need to show them when edits happen.
        self.save_button.hide()
        self.reset_button.hide()

        self.value_field.textChanged.connect(lambda: self.value_field_on_change())

        self.set_value_field: Callable = (
            QPlainTextEdit.setPlainText if text_area else QLineEdit.setText
        )

        self.save_button.clicked.connect(self.on_save_click)
        self.reset_button.clicked.connect(
            lambda _: self.set_value_field(
                self.value_field, self.preset_select.currentData()
            )
        )

        for preset in presets:
            self.preset_select.addItem(preset["name"], userData=preset["value"])

    def select_on_change(self, idx: int) -> None:
        new_value: str = self.preset_select.itemData(idx)
        self.set_value_field(self.value_field, new_value)

    def value_field_on_change(self) -> None:
        new_text: str = self.get_value()
        if new_text == self.preset_select.currentData() and self.value_field_dirty:
            # Unchanged preset has been set.
            self.save_button.hide()
            self.reset_button.hide()
            self.value_field_dirty = False
        elif (
            new_text != self.preset_select.currentData() and not self.value_field_dirty
        ):
            # We have a change that resulted in data not matching the preset and we aren't
            # already labeled dirty.
            self.value_field_dirty = True
            self.save_button.show()
            self.reset_button.show()

    def on_save_click(self):
        save_dialog = SaveDialog(self.preset_select.currentText())
        if save_dialog.exec():
            # The dialog was confirmed.
            name: str = save_dialog.name_input.text()
            value: str = self.get_value()
            curr_idx: int = self.preset_select.currentIndex()
            if name == self.preset_select.currentText():
                self.preset_select.setItemData(curr_idx, value)
            else:
                self.preset_select.addItem(name, value)
                idx: int = self.preset_select.findText(name)
                self.preset_select.setCurrentIndex(idx)
            # Manually trigger this, since it does not retrigger after we add in the new
            # option.
            self.value_field_on_change()
            self.preset_update.emit(Preset(name=name, value=value))


class Config(TypedDict):
    openai_api_key: str
    openai_model: str
    MOCK_API_RESPONSE: str
    vocab_query_presets: List[Preset]
    theme_presets: List[Preset]
    prompt_presets: List[Preset]
    lang_presets: List[Preset]
    previous_stories: Dict[str, List[str]]
    max_stories_per_collection: int
    story_font_size_idx: int
    story_font_family: str

    # This is a mapping of note types to a given field index
    # in order to determine what field to pull the vocab from.
    note_type_field: Dict[str, int]
    

def save_config(config: Config):
    mw.addonManager.writeConfig(__name__, cast(Dict, config))


class PresetRows(TypedDict):
    prompt: PresetFieldRow
    vocab_query: PresetFieldRow
    theme: PresetFieldRow
    lang: PresetFieldRow


class PromptForm(QDialog):
    # TODO: Add field for selected deck or all decks.
    def __init__(
        self,
        prompts: List[Preset],
        vocab_queries: List[Preset],
        themes: List[Preset],
        langs: List[Preset],
        previous_stories: List[str],
        config: Config,
    ):
        super(PromptForm, self).__init__()
        self.config: Config = config
        self.setWindowTitle("AI Prompt Configuration")

        self.preset_rows: PresetRows = {
            "prompt": PresetFieldRow(prompts, text_area=True),
            "vocab_query": PresetFieldRow(vocab_queries),
            "theme": PresetFieldRow(themes),
            "lang": PresetFieldRow(langs)
        }

        self.preset_rows["theme"].preset_update.connect(
            lambda preset: self.on_preset_update("theme_presets", preset)
        )

        self.preset_rows["vocab_query"].preset_update.connect(
            lambda preset: self.on_preset_update("vocab_query_presets", preset)
        )

        self.preset_rows["prompt"].preset_update.connect(
            lambda preset: self.on_preset_update("prompt_presets", preset)
        )
        
        self.preset_rows["lang"].preset_update.connect(
            lambda preset: self.on_preset_update("lang_presets", preset)
        )

        self.button = QPushButton("Run")
        self.copy_button = QPushButton("Copy to Clipboard")
        self.button.clicked.connect(self.prepare_story)
        self.copy_button.clicked.connect(
            lambda _: self.prepare_story(copy_to_clipboard=True)
        )

        layout = QFormLayout()
        run_button_row = QHBoxLayout()

        layout.addRow(QLabel("Theme"), self.preset_rows["theme"].row)
        layout.addRow(QLabel("Collection Query"), self.preset_rows["vocab_query"].row)
        layout.addRow(QLabel("Language"), self.preset_rows["lang"].row)
        layout.addRow(QLabel("Prompt"), self.preset_rows["prompt"].row)
        run_button_row.addWidget(self.button)
        run_button_row.addWidget(self.copy_button)
        layout.addRow(run_button_row)

        if not self.config["openai_api_key"]:
            # No api key provided, we disable the Run button.
            self.button.setDisabled(True)
            self.button.setToolTip(
                "No OpenAI key provided, cannot automatically query. Please use the Copy to Clipboard option"
            )

        self.previous_stories: List[str] = previous_stories

        if self.previous_stories:
            self.previous_stories_button = QPushButton("Previous Stories")
            self.previous_stories_button.clicked.connect(self.show_previous_stories)
            layout.addRow(self.previous_stories_button)
        self.setLayout(layout)
        self.resize(1200, 800)

    def show_previous_stories(self):
        story_view: StoryView = StoryView(self.previous_stories, 
                                          font_size_idx=self.config['story_font_size_idx'])
        setattr(mw, "anki_storytime__previous_story_view", story_view)
        story_view.show()
        story_view.raise_()
        story_view.activateWindow()
        self.close()

    def on_preset_update(self, field: str, new_preset: Preset):
        curr_custom_presets: List[Preset] = self.config[field]
        try:
            existing: Preset = next(
                filter(
                    lambda curr_preset: new_preset["name"] == curr_preset["name"],
                    curr_custom_presets,
                )
            )
            # Update an existing vaue.
            existing["value"] = new_preset["value"]
        except StopIteration:
            # It does not exist.
            curr_custom_presets.append(new_preset)

        save_config(self.config)

    def prepare_story(self, copy_to_clipboard: bool = False):
        # Both the following casts are guaranteed safe since the button won't show unless
        # we both have a collection and a deck is selected.
        config: Config = get_config()
        col: Collection = cast(Collection, mw.col)
        known_notes: Dict[str, int] = config["note_type_field"]
        selected_deck_id: DeckId = col.decks.selected()
        selected_deck = cast(DeckDict, col.decks.get(selected_deck_id))
        selected_deck_name = selected_deck["name"]

        vocab_query: str = (
            f'deck:"{selected_deck_name}" '
            + self.preset_rows["vocab_query"].get_value()
        )
        notes: List[Note] = list(
            map(lambda note_id: col.get_note(note_id), get_notes(mw, vocab_query))
        )

        notes_without_known_index: Dict[str, Note] = {}

        note: Note
        for note in notes:
            if note.note_type() is None:
                continue
            note_type: Union[NotetypeDict, None] = note.note_type()
            note_type_name = (note_type or {}).get("name")

            if note_type_name is not None:
                if (
                    note_type_name not in known_notes
                    and note_type_name not in notes_without_known_index
                ):
                    # we don't know which field has the value we want to use.
                    notes_without_known_index[note_type_name] = note

        if len(notes_without_known_index) > 0:
            note_type_form: NoteTypeForm = NoteTypeForm(notes_without_known_index)
            setattr(mw, "anki_storytime__note_type_window", note_type_form)
            note_type_form.show()
            return None

        vocab: List[str] = []
        note: Note
        for note in notes:
            note_type: Union[NotetypeDict, None] = note.note_type()
            if note_type is None:
                continue
            note_type_name: str = note_type["name"]
            idx: int = known_notes[note_type_name]
            vocab.append(note.fields[idx])

        theme: str = self.preset_rows["theme"].get_value()
        prompt: str = self.preset_rows["prompt"].get_value()
        lang: str = self.preset_rows["lang"].get_value()
        op = QueryOp(
            parent=mw,
            op=lambda _: prepare_story(vocab, theme, prompt, lang, copy_to_clipboard),
            success=lambda response: prepare_story_on_success(
                response, deck_name=selected_deck_name
            ),
        )

        op.with_progress().run_in_background()

        self.close()


def main():
    validate_config()
    aqt.gui_hooks.overview_will_render_bottom.append(add_ai_button)
    return

def validate_config() -> None:
    config: Dict = mw.addonManager.getConfig(__name__) or {}
    required_fields: Set[str] = set(Config.__required_keys__)
    missing_fields: Set[str] = required_fields - set(config.keys())

    # Technically, the below will only ever occur due to a programming error since if the user
    # tries to remove a field from the json config, it gets repopulated with the default value.
    if missing_fields:
        missing_fields_str: str = "\n" + "\n".join(missing_fields)

        showInfo(
            f"Anki Storytime addon is missing required configuration fields, this is likely a programming error. It may not function properly. Please try populating the provided fields or resetting to default values. Missing fields: {missing_fields_str}"
        )
        raise Exception("Invalid configuration for Anki Storytime")


def get_config() -> Config:
    return cast(Config, mw.addonManager.getConfig(__name__) or {})


def get_notes(mw: AnkiQt, query: str) -> Sequence[NoteId]:
    col: Union[Collection, None] = mw.col
    if col is None:
        return []
    # return list(map(lambda x: col.get_note(x).fields[1], col.find_notes(query)))
    return col.find_notes(query)


def prepare_story_on_success(
    story: Union[str, None], deck_name: Union[str, None] = None
) -> None:
    if story is None:
        # Likely note types without a known index were found, not an error. Just return.
        # Or the prompt was copied to the clipboard.
        return
    col_name: str = cast(Collection, mw.col).path
    name: str = (
        deck_name or col_name
    )  # If no deck name is set, we pulled from all decks so use col_name.
    config: Config = get_config()
    previous_stories: Dict[str, List[str]] = config["previous_stories"]

    if name not in previous_stories:
        previous_stories[name] = []
    previous_stories[name].append(story)
    if len(previous_stories[name]) > config["max_stories_per_collection"]:
        # Pop the first story off, which is the oldest.
        previous_stories[name].pop(0)
    save_config(config)
    
    story_view: StoryView = StoryView(previous_stories[name], font_size_idx=config['story_font_size_idx'])
    setattr(mw, "anki_storytime__story_view", story_view)
    story_view.show()


def prepare_story(
        vocab: List[str], theme: str, prompt: str, lang: str, copy_to_clipboard: bool = False
) -> Union[str, None]:
    config: Config = get_config()
    if len(vocab) > 0:
        if config.get("MOCK_API_RESPONSE") is True:
            # So we don't run up the bill while testing :)
            response: str = (
                f"ここに何かがありますよ。テーマは「{theme}」です。下には、選んだ言葉があります：\n"
                + "\n".join(vocab)
            )
            if len(response) > 1000:
                response = (
                    response[0:1000] + f"... ({len(response) - 1000} characters omitted"
                )
            return response
        api_key = config.get("openai_api_key", "")
        filled_prompt: str = prompt.format(vocab="\n".join(vocab), theme=theme, lang=lang)
        if api_key and not copy_to_clipboard:
            return get_openai_response(filled_prompt, config["openai_model"], api_key)
        elif copy_to_clipboard:
            app: QApplication = mw.app
            clipboard_success: bool = False
            clipboard = app.clipboard()
            if clipboard is not None:
                clipboard.setText(filled_prompt)
                clipboard_success = True

            if not clipboard_success:
                raise Exception("Failed to copy to clipboard")

        else:
            raise Exception(
                "No API Key set for OpenAI, please add this key in this addon's config"
            )
    else:
        raise Exception("No notes found matching your query")


def get_openai_response(prompt: str, model: str, token: str):
    headers: Dict = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    request_body: bytes = json.dumps(dict(model=model, input=prompt)).encode("utf-8")
    req: urllib.request.Request = urllib.request.Request(
        OPENAI_RESPONSE_URL, headers=headers, method="POST", data=request_body
    )

    with urllib.request.urlopen(req) as response:
        body_bytes = response.read()
        body_str: str = body_bytes.decode("utf-8")
        body_json = json.loads(body_str)
        if "output" not in body_json:
            raise Exception(f"Bad response from OpenAI model: {body_json}")
        output: str = body_json["output"][0]["content"][0]["text"]
        return output


def create_prompt_dialog():
    # Refetch the config here to ensure it refreshes.
    config: Config = get_config()
    col: Collection = cast(Collection, mw.col)
    col_name: str = col.path
    selected_deck_id: DeckId = col.decks.selected()
    selected_deck = cast(DeckDict, col.decks.get(selected_deck_id))
    selected_deck_name = selected_deck["name"]
    name: str = selected_deck_name or col_name
    previous_stories = config["previous_stories"].get(name, [])
    prompt_window = PromptForm(
        config["prompt_presets"], config["vocab_query_presets"], config["theme_presets"], config["lang_presets"], previous_stories, config=config
    )
    setattr(mw, "anki_storytime__prompt_window", prompt_window)
    prompt_window.show()


def add_ai_button(
    link_handler: Callable[[str], bool], links: List[List[str]]
) -> Callable[[str], bool]:
    links.append(["A", AI_BUTTON_URI, "Storytime"])

    def ai_button_link_handler(url: str):
        handler = link_handler(url)
        if url == AI_BUTTON_URI:
            create_prompt_dialog()

        return handler

    return ai_button_link_handler


main()
