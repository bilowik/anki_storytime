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
from anki.collection import Collection
from openai import OpenAI
import openai

AI_BUTTON_URI = "anki_storytime__ai_button";
MAX_VOCAB_WORDS = 100
    

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
    showInfo("Story from today's mistakes\n\n" + story, title="AI Storytime")


def prepare_story() -> str:
    config: Dict = get_config()
    vocab: List[str]= get_vocab(mw, config.get("vocab_query_presents", [""])[0])
    theme: str = config.get("theme_presets", [""])[0]
    prompt: str = config.get("prompt_prests", [""])[0]
    if len(vocab) > 0:
        if config.get("MOCK_API_RESPONSE") is True:
            # So we don't run up the bill while testing :) 
            return f"ここに何かがありますよ。テーマは「{theme}」です。下には、選んだ言葉があります：\n" + "\n".join(vocab)
        api_key = config.get("open_api_key", "")
        if api_key:
            client = OpenAI(api_key=config.get('open_api_key', ""))
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


def add_ai_button(link_handler: Callable[[str], bool], links: List[List[str]]) -> Callable[[str], bool]:
    links.append(['A', AI_BUTTON_URI, "AI Button"])
    def ai_button_link_handler(url: str):
        handler = link_handler(url)
        if url == AI_BUTTON_URI:
            op = QueryOp(
                    parent=mw,
                    op=lambda _: prepare_story(),
                    success=prepare_story_on_success,
            )

            op.with_progress().run_in_background()


        return handler

    return ai_button_link_handler


main()
