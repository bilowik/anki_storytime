import sys
import os

# When bundlings the packages they will be placed here.
sys.path.insert(1, os.path.join(os.path.dirname((os.path.abspath(__file__))), 'libs'))

from typing import Callable, List, Union, Dict
import aqt
from aqt import mw
import aqt.gui_hooks
from aqt.main import AnkiQt
from aqt.utils import showInfo
from aqt.operations import QueryOp
from aqt.qt.qt6 import QDialog, QComboBox, QPushButton, QVBoxLayout
from anki.collection import Collection
from openai import OpenAI
import openai
from typing import TypedDict

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

class PromptForm(QDialog):
    def __init__(self, prompts: List[Prompt], vocab_queries: List[VocabQuery], themes: List[Theme], ):
        super(PromptForm, self).__init__()
        self.setWindowTitle("AI Prompt Configuration")

        self.prompt = QComboBox()
        self.theme = QComboBox()
        self.vocab_query = QComboBox()
        
        for prompt in prompts:
            self.prompt.addItem(prompt["name"], userData=prompt["body"])

        for vocab_query in vocab_queries:
            self.vocab_query.addItem(vocab_query["name"], userData=vocab_query["query"])
        
        for theme in themes:
            self.theme.addItem(theme["name"], userData=theme["body"])


        self.button = QPushButton("Run")
        self.button.clicked.connect(self.prepare_story)

        layout = QVBoxLayout()

        layout.addWidget(self.prompt)
        layout.addWidget(self.theme)
        layout.addWidget(self.vocab_query)
        layout.addWidget(self.button)
        self.setLayout(layout)


    

    def prepare_story(self):
        vocab_query: str = self.vocab_query.currentData()
        theme: str = self.theme.currentData()
        prompt: str = self.prompt.currentData()
        op = QueryOp(
                parent=mw,
                op=lambda _: prepare_story(vocab_query, theme, prompt),
                success=prepare_story_on_success,
        )

        op.with_progress().run_in_background()



def main():
    aqt.gui_hooks.overview_will_render_bottom.append(add_ai_button)
    return 

def get_config() -> Dict:
    return mw.addonManager.getConfig(__name__) or {}


def get_vocab(mw: AnkiQt, query: str) -> List[str]:
    col: Union[Collection, None] = mw.col 
    if col is None:
        return []
    return list(map(lambda x: col.get_note(x).fields[1], col.find_notes(query)))



def prepare_story_on_success(story: str) -> None:
    showInfo(story, title="AI Storytime")


def prepare_story(vocab_query: str, theme: str, prompt: str) -> str:
    config: Dict = get_config()
    vocab: List[str]= get_vocab(mw, vocab_query)
    if len(vocab) > 0:
        if config.get("MOCK_API_RESPONSE") is True:
            # So we don't run up the bill while testing :) 
            response: str = f"ここに何かがありますよ。テーマは「{theme}」です。尋ねは「{vocab_query}｀」です。下には、選んだ言葉があります：\n" + "\n".join(vocab)
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


def create_prompt_dialog(config: Dict):
    vocab_queries: List[VocabQuery] = config["vocab_query_presets"]
    themes: List[Theme] = config["theme_presets"]
    prompts: List[Prompt] = config["prompt_presets"]
    prompt_window = PromptForm(prompts, vocab_queries, themes)
    setattr(mw, "anki_storytime__prompt_window", prompt_window)
    prompt_window.show()


def add_ai_button(link_handler: Callable[[str], bool], links: List[List[str]]) -> Callable[[str], bool]:
    config: Dict = get_config()
    links.append(['A', AI_BUTTON_URI, "AI Button"])
    def ai_button_link_handler(url: str):
        handler = link_handler(url)
        if url == AI_BUTTON_URI:
            create_prompt_dialog(config)

        return handler

    return ai_button_link_handler


main()
