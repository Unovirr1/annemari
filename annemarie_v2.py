from pypdf import PdfReader
from random import choice, randint
from googletrans import Translator
import re
import asyncio
import pymorphy3
import pyttsx3 #txttospeech\
import time

# Load your PDF file
reader = PdfReader("week3/annemarie-schwarzenbach-das-glueckliche-tal.pdf")
pages = reader.pages
text = ""

morph = pymorphy3.MorphAnalyzer()

for page in pages:
    page_text = page.extract_text()
    ##if WORD in page_text:
    text=text+page_text
tree_sent = ""
tree_sent_translated = ""
keywords =  set()#["Tal", "Berg", "Fluss", "Fels", "Ebene", "Halden", "Demawend", "Lied"]
def random_sentence():
    
    sentences = re.findall(r'[^.!?]+[.!?]', text)

    #sentences = [sent for sent in sentences if choice(keywords) in sent ]
    sentences_with_keyword = []
    for i_sentence in sentences:
        add_or_no = False
        for i_keyword in keywords:
            if " "+i_keyword in i_sentence.lower():
                add_or_no = True
        if add_or_no == True:
            sentences_with_keyword.append(i_sentence)
    if sentences_with_keyword:
        sentence = choice(sentences_with_keyword)
    else:
        sentence = choice(sentences)
    """pos = sentence.find(" ", sentence.find(" ") + 1)
    right = sentence[pos + 1:]
    sentence = choice(sentences)
    pos = sentence.find(" ", sentence.find(" ") + 1)
    left = sentence[:pos]
    sentence = left + " " + right"""
    
    sentence = sentence.replace('\n', " ")

    for i in sentence:
        if  i.isdigit() :
            sentence = sentence.replace(i, "")

    if sentence[0] == " ":
        sentence = sentence[1::]
    sentence = sentence[0].lower()+sentence[1:]

    if "Haschisch" in sentence:
        sentence = sentence.replace("Haschisch", "\u2588"*9 )
    if "Opium" in sentence:
            sentence = sentence.replace("Opium", "\u2588"*5 )
    
    return sentence 


def remove_with_mark(text, phrase):
    if phrase in text:
        text = re.sub(
        rf'\b{re.escape(phrase)}\b[^\w\s]?',
        f"",
        text,
        count=1
        )
        text = text[1::]
        text = text[0].capitalize()+text[1::]
    return text


def process_sentence_gender(text):
    # Разбиваем текст на слова, сохраняя знаки препинания
    tokens = re.findall(r'\w+|[^\w\s]', text, re.UNICODE)
    
    result = []
    find_verb_for_i = False  # Флаг: ищем ли мы глагол для слова "я"
    
    for token in tokens:
        # Проверяем, является ли токен словом "я" (приводим к нижнему регистру)
        if token.lower() == 'я':
            find_verb_for_i = True
            result.append(token)
            continue
        
        # Если мы в режиме поиска глагола для "я"
        if find_verb_for_i:
            # Анализируем слово
            parsed = morph.parse(token)[0]
            
            # Проверяем, глагол ли это (в прошедшем времени, так как в настоящем/будущем рода нет)
            if 'VERB' in parsed.tag:
                # Проверяем, что глагол в мужском роде, чтобы изменить его на женский
                if 'masc' in parsed.tag:
                    parsed_femn = parsed.inflect({'femn'})
                    if parsed_femn:
                        token = parsed_femn.word
                        # Сохраняем оригинальный регистр (если слово было с заглавной)
                        if token.istitle():
                            token = token.capitalize()
                
                # Выключаем режим поиска — ОДНО слово "я" изменило только ОДИН глагол
                find_verb_for_i = False
                
        result.append(token)
        
    # Собираем слова обратно в строку с базовыми правилами пунктуации
    # (убираем лишние пробелы перед знаками препинания)
    processed_text = " ".join(result)
    processed_text = re.sub(r'\s+([.,!?;:])', r'\1', processed_text)
    
    return processed_text


#  the speech

def speak(text):
    engine = pyttsx3.init()
    # Optional: Customize the speed and volume
    engine.setProperty('rate', 150)    # Speed of speech (words per minute)
    engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
    engine.say(text)
    engine.runAndWait()

'''text_parts = text.split(",")
    for part in text_parts:
        engine.setProperty('rate', randint(100,200))
        engine.say(part)
        engine.runAndWait()
        time.sleep(0.1)'''

#main func

async def main():
    translator = Translator()
    user_phrase = input()
    print("———"*30)

    while user_phrase!= "":
        res = await translator.translate(  
            user_phrase,
            src="ru",
            dest="de"
        )
        user_phrase_parsed = res.text.lower().split(" ")
        keyword = max(user_phrase_parsed, key=len)
        punctuation = '!_#$%"\'()*+,-./:;<=>?@[\\]^`{|}~'

        keyword = "".join(char for char in keyword if char not in punctuation)

        keywords.add(keyword)

        print(keywords)
        tree_sent = random_sentence().replace(".", ",")+" "+ random_sentence().replace(".", ",")+" "+ random_sentence()


        try:
            result = await translator.translate(
                "ich bin ein Mädchen, " + tree_sent,#.replace(".", ","),
                src="de",
                dest="ru"
            )
            tree_sent_translated = result.text#[12::]
            tree_sent_translated = remove_with_mark(tree_sent_translated, "Я девочка")
            tree_sent_translated = remove_with_mark(tree_sent_translated, "Я - девочка")
            tree_sent_translated = remove_with_mark(tree_sent_translated, "Я девушка")
            tree_sent_translated = remove_with_mark(tree_sent_translated, "Я - девушка")
            tree_sent_translated = remove_with_mark(tree_sent_translated, "Я девчонка")
            tree_sent_translated = process_sentence_gender(tree_sent_translated) 
            print(tree_sent_translated)
            speak(tree_sent_translated)
        
        except Exception as e:
            print(f"An error occurred: {e}")

        
        print("———"*30)
        keywords.discard(keyword)
        user_phrase = input()

asyncio.run(main())
