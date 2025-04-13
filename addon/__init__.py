import sys
import os

# When bundlings the packages they will be placed here.
sys.path.insert(1, os.path.join(os.path.dirname((os.path.abspath(__file__))), 'libs'))
print(sys.path)

from typing import Callable, List, Union, Dict
import aqt
from aqt import mw
import aqt.gui_hooks
from aqt.main import AnkiQt
from aqt.overview import Overview, OverviewContent
from anki.collection import Collection
from openai import OpenAI
import openai

AI_BUTTON_URI = "anki_storytime__ai_button";

DEFAULT_PROMPT_BASE = """Create a story in Japanese with the following vocabulary words that will be listed individually on separate lines starting after the first empty newline. The story can be about anything in particular, but should provide a reasonable amount of context, not every sentence has to have one of the vocabulary words in it, but you must utilize every single vocabulary word provided. The length of the story can be as long as needed to encompass all of the vocabulary words. Do not respond with any other text other than the story. Following are the vocabulary words:

"""
MAX_VOCAB_WORDS = 100
    

CONFIG: Dict = mw.addonManager.getConfig(__name__) or {}
print(CONFIG)

def main():
    aqt.gui_hooks.overview_will_render_bottom.append(add_ai_button)
    return 

def get_forgotten_vocab(mw: AnkiQt) -> List[str]:
    col: Union[Collection, None] = mw.col 
    if col is None:
        return []
    return list(map(lambda x: col.get_note(x).fields[1], col.find_notes("rated:1:1")))





def add_ai_button(link_handler: Callable[[str], bool], links: List[List[str]]) -> Callable[[str], bool]:
    d = mw

    links.append(['A', AI_BUTTON_URI, "AI Button"])
    def ai_button_link_handler(url: str):
        handler = link_handler(url)
        if url == AI_BUTTON_URI:
            # TODO: Do something here?
            print(AI_BUTTON_URI + '_button_test')
            vocab: List[str]= get_forgotten_vocab(mw)
            if len(vocab) > 0:
                api_key = CONFIG.get('OpenAI API Key', '')
                if api_key:
                    client = OpenAI(api_key=CONFIG.get('OpenAI API Key', ''))
                    prompt: str = DEFAULT_PROMPT_BASE + "\n".join(vocab)
                    try:
                        response = client.responses.create(input=prompt, model="gpt-4o")
                        print(response.output_text)
                    except openai.RateLimitError:
                        print("Out of credits")
                    except openai.BadRequestError as e:
                        print(f"Bad request: {e}")
                else:
                    print("No API Key provided")


        return handler

    return ai_button_link_handler






main()
