from flask import Flask, request, jsonify
import logging
import random
import sqlite3

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
# подключаем бд
con = sqlite3.connect("inf_db.sqlite")
cur = con.cursor()
result = cur.execute("""select id from information""").fetchall()
count_of_sights = int(str(result[-1])[1:-2])
con.close()
sessionStorage = {}


@app.route('/post', methods=['POST'])
def main():
    logging.info('Request: %r', request.json)
    response = {
        'session': request.json['session'],
        'version': request.json['version'],
        'response': {
            'end_session': False
        }
    }
    handle_dialog(response, request.json)
    logging.info('Response: %r', response)
    return jsonify(response)


def handle_dialog(res, req):
    user_id = req['session']['user_id']
    if req['session']['new']:
        # создаём пустой массив, в который будем записывать города, которые пользователь уже отгадал
        res['response']['text'] = 'Привет! '
        sessionStorage[user_id] = {
            'game_started': False,  # здесь информация о том, что пользователь начал игру. По умолчанию False
            'first_step': False
        }
    if sessionStorage[user_id]['first_step'] == False:
        sessionStorage[user_id]['first_step'] = True
        sessionStorage[user_id]['guessed_sights'] = []
        # Предлагаем пользователю сыграть и варианта ответа: "Да", "Нет", "Помощь", "Что ты умеешь?".
        res['response'][
            'text'] += 'Я Алиса. Отгадаешь достопримечательность в Оренбурге по фото?(Напишите "да" для начала игры или "нет" для ее завершения. Инструкцию вы можете прочитать, если напишите "помощь" или "что ты умеешь?")'
        res['response']['buttons'] = [
            {
                'title': 'Да',
                'hide': True
            },
            {
                'title': 'Нет',
                'hide': True
            },
            {
                'title': 'Помощь',
                'hide': True
            },
            {
                'title': 'Что ты умеешь?',
                'hide': True
            }
        ]
    # В sessionStorage[user_id]['game_started'] хранится True или False в зависимости от того,
    # начал пользователь игру или нет.
    elif not sessionStorage[user_id]['game_started']:
        # игра не начата, значит мы ожидаем ответ на предложение сыграть.
        if 'помощь' in req['request']['nlu']['tokens']:
            res['response'][
                'text'] = 'Если вы хотите начать игру, напишите "да", если нет, то напишите "нет". В ответе на фотографию напишите название достопримечательности. Сыграем?'
        elif 'что' in req['request']['nlu']['tokens'] and 'ты' in req['request']['nlu']['tokens'] and 'умеешь' in \
                req['request']['nlu']['tokens']:
            res['response'][
                'text'] = 'Я умею отправлять фото с достопримечательностями города Оренбурга, а также проверять на правильность твои ответы. Если вы хотите начать игру, напишите "да", если нет, то напишите "нет". В ответе на фотографию напишите название достопримечательности. Сыграем?'
        elif 'да' in req['request']['nlu']['tokens']:
            # если пользователь согласен, то проверяем не отгадал ли он уже все города.
            # По схеме можно увидеть, что здесь окажутся и пользователи, которые уже отгадывали города
            if len(sessionStorage[user_id]['guessed_sights']) == count_of_sights:
                # если все города отгаданы, то заканчиваем игру
                res['response']['text'] = 'Ты отгадал все города!'
                res['end_session'] = True
            else:
                # если есть неотгаданные города, то продолжаем игру
                sessionStorage[user_id]['game_started'] = True
                # номер попытки, чтобы показывать фото по порядку
                sessionStorage[user_id]['attempt'] = 1
                # функция, которая выбирает город для игры и показывает фото
                play_game(res, req)
        elif 'нет' in req['request']['nlu']['tokens']:
            res['response']['text'] = 'Ну и ладно!'
            res['end_session'] = True
        else:
            res['response']['text'] = 'Не поняла ответа! Так да или нет?'
            res['response']['buttons'] = [
                {
                    'title': 'Да',
                    'hide': True
                },
                {
                    'title': 'Нет',
                    'hide': True
                }
            ]
    else:
        play_game(res, req)


def play_game(res, req, id_of_sight=None):
    user_id = req['session']['user_id']
    attempt = sessionStorage[user_id]['attempt']
    if attempt == 1:
        # если попытка первая, то случайным образом выбираем город для гадания
        con = sqlite3.connect("inf_db.sqlite")
        cur = con.cursor()
        id_of_sight = random.randint(1, count_of_sights)
        sight = str(cur.execute(f"""select name from information where id == {id_of_sight}""").fetchall())[3:-4]
        # выбираем его до тех пор пока не выбираем город, которого нет в sessionStorage[user_id]['guessed_sights']
        while sight in sessionStorage[user_id]['guessed_sights']:
            id_of_sight = random.randint(1, count_of_sights)
            sight = str(cur.execute(f"""select name from information
                                 where id == {id_of_sight}""").fetchall())[3:-4]
        # записываем город в информацию о пользователе
        sessionStorage[user_id]['sight'] = sight
        # добавляем в ответ картинку
        res['response']['card'] = {}
        res['response']['card']['type'] = 'BigImage'
        res['response']['card']['title'] = 'Что это за достопримечательность?'
        image_id = str(cur.execute(f"""select id_of_image from information
                                 where id == {id_of_sight}""").fetchall())[3:-4]
        res['response']['card']['image_id'] = image_id
        res['response']['text'] = 'Тогда сыграем!'
        con.close()
    else:
        # сюда попадаем, если попытка отгадать не первая
        sight = sessionStorage[user_id]['sight']
        # проверяем есть ли правильный ответ в сообщение
        if "".join(str(x) for x in get_sight(req).lower().split()) == sight.lower():
            con = sqlite3.connect("inf_db.sqlite")
            cur = con.cursor()
            id_of_sight = str(cur.execute(f'''select id from information
                                             where name == "{"".join(str(x) for x in sight.lower().split(" "))}"''').fetchall())[
                          2:-3]
            res['response']['card'] = {}
            res['response']['card']['type'] = 'ImageGallery'
            res['response']['card']['items'] = [{}, {}]
            res['response']['card']['items'][0]['title'] = f'Вы ответили правильно! Сыграем ещё?'
            sights_on_map = str(cur.execute(f"""select id_of_map_image from information
                                 where id == {id_of_sight}""").fetchall())[3:-4]
            res['response']['card']['items'][0]['image_id'] = sights_on_map
            res['response']['card']['items'][1]['title'] = 'Немного информации о достопримечательности.'
            information_about_sights = str(cur.execute(f"""select id_of_information from information
                                             where id == {id_of_sight}""").fetchall())[3:-4]
            res['response']['card']['items'][1]['image_id'] = information_about_sights
            res['response']['card']['items'][0]['button'] = {}
            res['response']['card']['items'][0]['button']['title'] = "Построить маршрут"
            res['response']['card']['items'][0]['button'][
                'url'] = r"https://yandex.ru/maps/48/orenburg/?indoorLevel=1&ll=55.102872%2C51.768184&mode=routes&rtext=51.768205%2C55.096964&rtt=auto&ruri=ymapsbm1%3A%2F%2Fgeo%3Fdata%3DCgg1MzEwNTE4MhIe0KDQvtGB0YHQuNGPLCDQntGA0LXQvdCx0YPRgNCzIgoNSmNcQhWkEk9C&z=16.62"
            res['response']['text'] = 'Правильно!'
            sessionStorage[user_id]['guessed_sights'].append(sight)
            sessionStorage[user_id]['game_started'] = False
            con.close()
            return
        else:
            con = sqlite3.connect("inf_db.sqlite")
            cur = con.cursor()
            id_of_sight = str(cur.execute(f'''select id from information
                                                         where name == "{"".join(str(x) for x in sight.lower().split(" "))}"''').fetchall())[
                          2:-3]
            name_of_sight = str(
                cur.execute(f"""select name_of_sight from information where id == {id_of_sight}""").fetchall())[3:-4]
            res['response']['text'] = f'Вы пытались. Это {name_of_sight}. Сыграем ещё?'
            sessionStorage[user_id]['game_started'] = False
            con.close()
            return
    # увеличиваем номер попытки доля следующего шага
    sessionStorage[user_id]['attempt'] += 1


def get_sight(req):
    return req['request']['original_utterance'].lower()


if __name__ == '__main__':
    app.run()
