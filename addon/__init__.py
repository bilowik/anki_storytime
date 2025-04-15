from typing import Callable, List, Union, Dict, TypedDict, cast, Callable, Set, Sequence 
import urllib.request
import json
import aqt
from aqt import mw
import aqt.gui_hooks
from aqt.main import AnkiQt
from aqt.utils import showInfo
from aqt.operations import QueryOp
from aqt.qt.qt6 import QDialog, QComboBox, QPushButton, QFormLayout, QLabel, QLineEdit, QPlainTextEdit, QHBoxLayout
from anki.collection import Collection
from anki.decks import DeckId, DeckDict
from anki.notes import NoteId, Note
from anki.models import NotetypeDict

AI_BUTTON_URI = "anki_storytime__ai_button";
MAX_VOCAB_WORDS = 100

OPENAI_RESPONSE_URL = "https://api.openai.com/v1/responses"


class NoteTypeForm(QDialog):
    def __init__(self, new_notes: Dict[str, Note]):
        super().__init__()
        layout: QFormLayout = QFormLayout()
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        header_label: QLabel = QLabel("The following are note types that have yet to have the correct field specified for use in this addon. Please use the dropdowns to select the field with your Japanese vocab.")
        header_label.setWordWrap(True)
        layout.addRow(header_label)
        self.note_selects: Dict[str, QComboBox] = {}
        new_note: Note
        for (name, new_note) in new_notes.items():
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

        for (name, select) in self.note_selects.items():
            note_type_field[name] = select.currentIndex()
        mw.addonManager.writeConfig(__name__, cast(Dict, config))
        self.close()
        


class Prompt(TypedDict):
    name: str
    body: str

class Theme(TypedDict):
    name: str
    body: str

class VocabQuery(TypedDict):
    name: str
    query: str

class Config(TypedDict):
    openai_api_key: str
    openai_model: str
    MOCK_API_RESPONSE: str
    vocab_query_presets: List[VocabQuery]
    theme_presets: List[Theme]
    prompt_presets: List[Prompt]
    custom_vocab_query_presets: List[VocabQuery]
    custom_theme_presets: List[Theme]
    custom_prompt_presets: List[Prompt]
    previous_stories: Dict[str, List[str]] 
    max_stories_per_collection: int

    # This is a mapping of note types to a given field index
    # in order to determine what field to pull the vocab from.
    note_type_field: Dict[str, int] 

class PromptForm(QDialog):
    # TODO: Add field for selected deck or all decks.
    def __init__(self, prompts: List[Prompt], vocab_queries: List[VocabQuery], themes: List[Theme], previous_stories: List[str] ):
        super(PromptForm, self).__init__()
        self.setWindowTitle("AI Prompt Configuration")

        self.prompt_select = QComboBox()
        self.theme_select = QComboBox()
        self.vocab_query_select = QComboBox()
        
        self.prompt = QPlainTextEdit()
        self.theme = QLineEdit()
        self.vocab_query = QLineEdit()

        self.prompt_select.currentIndexChanged.connect(self.select_on_change_factory(self.prompt_select, self.prompt))
        self.theme_select.currentIndexChanged.connect(self.select_on_change_factory(self.theme_select, self.theme))
        self.vocab_query_select.currentIndexChanged.connect(self.select_on_change_factory(self.vocab_query_select, self.vocab_query))

        prompt_row: QHBoxLayout = QHBoxLayout()
        prompt_row.addWidget(self.prompt_select)
        prompt_row.addWidget(self.prompt)
        
        theme_row: QHBoxLayout = QHBoxLayout()
        theme_row.addWidget(self.theme_select)
        theme_row.addWidget(self.theme)

        vocab_query_row: QHBoxLayout = QHBoxLayout()
        vocab_query_row.addWidget(self.vocab_query_select)
        vocab_query_row.addWidget(self.vocab_query)
        
        for prompt in prompts:
            self.prompt_select.addItem(prompt["name"], userData=prompt["body"])

        for vocab_query in vocab_queries:
            self.vocab_query_select.addItem(vocab_query["name"], userData=vocab_query["query"])
        
        for theme in themes:
            self.theme_select.addItem(theme["name"], userData=theme["body"])

        
        self.button = QPushButton("Run")
        self.button.clicked.connect(self.prepare_story)
        

        layout = QFormLayout()


        layout.addRow(QLabel("Theme"), theme_row)
        layout.addRow(QLabel("Collection Query"), vocab_query_row)
        layout.addRow(QLabel("Prompt"), prompt_row)
        layout.addWidget(self.button)

        self.previous_stories: List[str] = previous_stories

        if self.previous_stories:
            self.previous_stories_button = QPushButton("Previous Stories")
            self.previous_stories_button.clicked.connect(self.show_previous_stories)
            layout.addWidget(self.previous_stories_button)
        self.setLayout(layout)
    
    
    def select_on_change_factory(self, select: QComboBox, text: Union[QLineEdit, QPlainTextEdit]) -> Callable[[int], None]:
        text_setter: Callable[[str]]
        if isinstance(text, QLineEdit):
            text_setter = lambda s: cast(QLineEdit, text).setText(s)
        else:
            text_setter = lambda s: cast(QPlainTextEdit, text).setPlainText(s)

        def select_on_change(idx: int):
            text_setter(select.itemData(idx))

        return select_on_change

    def show_previous_stories(self):
        showInfo(self.previous_stories[-1])
    

    def prepare_story(self):
        # Both the following casts are guaranteed safe since the button won't show unless
        # we both have a collection and a deck is selected.
        config: Config = get_config()
        col: Collection = cast(Collection, mw.col) 
        known_notes: Dict[str, int] = config['note_type_field']
        selected_deck_id: DeckId = col.decks.selected()
        selected_deck = cast(DeckDict, col.decks.get(selected_deck_id))
        selected_deck_name = selected_deck["name"]
        
        vocab_query: str = f'deck:"{selected_deck_name}" ' + self.vocab_query_select.currentData()
        notes: List[Note] = list(map(lambda note_id: col.get_note(note_id), get_notes(mw, vocab_query)))
        
        notes_without_known_index: Dict[str, Note] = {}
        
        note: Note
        for note in notes:
            if note.note_type() is None:
                continue
            note_type: Union[NotetypeDict, None] = note.note_type()
            note_type_name = (note_type or {}).get("name")

            if note_type_name is not None:
                if note_type_name not in known_notes and note_type_name not in notes_without_known_index:
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
            

        theme: str = self.theme.text()
        prompt: str = self.prompt.toPlainText()
        op = QueryOp(
                parent=mw,
                op=lambda _: prepare_story(vocab, theme, prompt),
                success=lambda response: prepare_story_on_success(response, deck_name=selected_deck_name), 
        )

        op.with_progress().run_in_background()

        self.close()



def main():
    aqt.gui_hooks.overview_will_render_bottom.append(add_ai_button)
    return 

def get_config() -> Config:
    config: Dict = mw.addonManager.getConfig(__name__) or {}
    required_fields: Set[str] = set(Config.__required_keys__)
    missing_fields: Set[str] = required_fields - set(config.keys())
    
    # Technically, the below will only ever occur due to a programming error since if the user
    # tries to remove a field from the json config, it gets repopulated with the default value.
    if missing_fields: 
        missing_fields_str: str = "\n" + "\n".join(missing_fields)

        showInfo(f"Anki Storytime addon is missing required configuration fields, this is likely a programming error. It may not function properly. Please try populating the provided fields or resetting to default values. Missing fields: {missing_fields_str}")
        raise Exception("Invalid configuration for Anki Storytime")
    # Can safely cast here since we know it has all required fields.
    return cast(Config, config)


def get_notes(mw: AnkiQt, query: str) -> Sequence[NoteId]:
    col: Union[Collection, None] = mw.col 
    if col is None:
        return []
    # return list(map(lambda x: col.get_note(x).fields[1], col.find_notes(query)))
    return col.find_notes(query)



def prepare_story_on_success(story: Union[str, None], deck_name: Union[str, None]=None) -> None:
    if story is None:
        # Likely note types without a known index were found, not an error. Just return.
        return
    col_name: str = cast(Collection, mw.col).path
    name: str = deck_name or col_name # If no deck name is set, we pulled from all decks so use col_name.
    config: Config = get_config()
    previous_stories: Dict[str, List[str]] = config["previous_stories"]

    if name not in previous_stories:
        previous_stories[name] = []
    previous_stories[name].append(story)
    if len(previous_stories[name]) > config["max_stories_per_collection"]:
        # Pop the first story off, which is the oldest.
        previous_stories[name].pop(0)
    mw.addonManager.writeConfig(__name__, cast(Dict, config))
    showInfo(story, title="AI Storytime")


def prepare_story(vocab: List[str], theme: str, prompt: str) -> str:
    config: Config = get_config()
    if len(vocab) > 0:
        if config.get("MOCK_API_RESPONSE") is True:
            # So we don't run up the bill while testing :) 
            response: str = f"ここに何かがありますよ。テーマは「{theme}」です。下には、選んだ言葉があります：\n" + "\n".join(vocab)
            if len(response) > 1000:
                response = response[0:1000] + f"... ({len(response) - 1000} characters omitted"
            print(response)
            return response
        api_key = config.get("openai_api_key", "")
        if api_key:
            filled_prompt: str = prompt.format(vocab=vocab, theme=theme)  
            return get_openai_response(filled_prompt, config['openai_model'], api_key) 

        else:
            raise Exception("No API Key set for OpenAI, please add this key in this addon's config")
    else:
        raise Exception("No notes found matching your query")


def get_openai_response(prompt: str, model: str, token: str):
    headers: Dict = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    request_body: bytes = json.dumps(dict(model=model, input=prompt)).encode('utf-8')
    req: urllib.request.Request = urllib.request.Request(OPENAI_RESPONSE_URL, headers=headers, method="POST", data=request_body)

    with urllib.request.urlopen(req) as response:
        body_bytes = response.read()
        body_str: str = body_bytes.decode('utf-8')
        body_json = json.loads(body_str)
        if 'output' not in body_json:
            raise Exception(f"Bad response from OpenAI model: {body_json}")
        output: str = body_json["output"][0]["content"][0]["text"]
        return output


def create_prompt_dialog():
    # Refetch the config here to ensure it refreshes.
    config: Config = get_config()
    col_name: str = cast(Collection, mw.col).path
    previous_stories = config["previous_stories"].get(col_name, [])
    vocab_queries: List[VocabQuery] = [*config["vocab_query_presets"], *config["custom_vocab_query_presets"]]
    themes: List[Theme] = [*config["theme_presets"], *config["custom_theme_presets"]]
    prompts: List[Prompt] = [*config["prompt_presets"], *config["custom_prompt_presets"]]
    prompt_window = PromptForm(prompts, vocab_queries, themes, previous_stories)
    setattr(mw, "anki_storytime__prompt_window", prompt_window)
    prompt_window.show()


def add_ai_button(link_handler: Callable[[str], bool], links: List[List[str]]) -> Callable[[str], bool]:
    links.append(['A', AI_BUTTON_URI, "Storytime"])
    def ai_button_link_handler(url: str):
        handler = link_handler(url)
        if url == AI_BUTTON_URI:
            create_prompt_dialog()

        return handler

    return ai_button_link_handler


main()
