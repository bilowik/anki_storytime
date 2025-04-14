import sys
import os

# When bundlings the packages they will be placed here.
sys.path.insert(1, os.path.join(os.path.dirname((os.path.abspath(__file__))), 'libs'))

from typing import Callable, List, Union, Dict, TypedDict, cast, Callable, Self, Set
import aqt
from aqt import mw
import aqt.gui_hooks
from aqt.main import AnkiQt
from aqt.utils import showInfo
from aqt.operations import QueryOp
from aqt.qt.qt6 import QDialog, QComboBox, QPushButton, QFormLayout, QLabel, QLineEdit, QPlainTextEdit, QHBoxLayout
from anki.collection import Collection
from anki.decks import DeckId, DeckDict
from openai import OpenAI
import openai

AI_BUTTON_URI = "anki_storytime__ai_button";
MAX_VOCAB_WORDS = 100


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
        col: Collection = cast(Collection, mw.col) 
        selected_deck_id: DeckId = col.decks.selected()
        selected_deck_name = cast(DeckDict, col.decks.get(selected_deck_id))["name"]
        vocab_query: str = f'deck:"{selected_deck_name}" ' + self.vocab_query_select.currentData()
        theme: str = self.theme.text()
        prompt: str = self.prompt.toPlainText()
        op = QueryOp(
                parent=mw,
                op=lambda _: prepare_story(vocab_query, theme, prompt),
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

        showInfo(f"Anki Storytime addon is missing required configuration fields, this is likely a programming error. It may not function properly. Please try populating the provided fields or resetting to default values. Missing fields: {"\n".join(missing_fields)}")
        raise Exception("Invalid configuration for Anki Storytime")
    # Can safely cast here since we know it has all required fields.
    return cast(Config, config)


def get_vocab(mw: AnkiQt, query: str) -> List[str]:
    col: Union[Collection, None] = mw.col 
    if col is None:
        return []
    return list(map(lambda x: col.get_note(x).fields[1], col.find_notes(query)))



def prepare_story_on_success(story: str, deck_name: Union[str, None]=None) -> None:
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


def prepare_story(vocab_query: str, theme: str, prompt: str) -> str:
    config: Config = get_config()
    vocab: List[str]= get_vocab(mw, vocab_query)
    if len(vocab) > 0:
        if config.get("MOCK_API_RESPONSE") is True:
            # So we don't run up the bill while testing :) 
            response: str = f"ここに何かがありますよ。テーマは「{theme}」です。尋ねは「{vocab_query}」です。下には、選んだ言葉があります：\n" + "\n".join(vocab)
            if len(response) > 1000:
                response = response[0:1000] + f"... ({len(response) - 1000} characters omitted"
            print(response)
            return response
        api_key = config.get("openai_api_key", "")
        if api_key:
            client = OpenAI(api_key=api_key)
            formatted_prompt: str = prompt.format(vocab="\n".join(vocab), theme=theme)
            try:
                return client.responses.create(input=formatted_prompt, model="gpt-4o").output_text
            except openai.RateLimitError:
                raise Exception("The account associated with the provided API key may have run out of credits")
            except openai.BadRequestError as e:
                raise Exception(f"Failed to retrieve response from OpenAI: {e}")
        else:
            raise Exception("No API Key set for OpenAI, please add this key in this addon's config")
    else:
        raise Exception("No notes found matching your query")


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
