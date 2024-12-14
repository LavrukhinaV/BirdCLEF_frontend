import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import ast
import random

# Заголовок страницы
st.set_page_config(page_title="Интерактивная карта птиц", layout="wide")  # Устанавливаем заголовок и широкую верстку

# API eBird
EBIRD_API_URL = "https://api.ebird.org/v2/ref/taxonomy/ebird"
EBIRD_API_KEY = "nusv3bd5ltqk"

# Генерация случайного цвета
def random_color(alpha=160):
    return [random.randint(0, 255) for _ in range(3)] + [alpha]

# Загрузка данных из CSV
@st.cache_data
def load_data(file_path):
    try:
        data = pd.read_csv(file_path)
        if "type" in data.columns:
            data["type"] = data["type"].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)
        return data
    except FileNotFoundError:
        st.error(f"Файл {file_path} не найден. Проверьте путь и повторите попытку.")
        return pd.DataFrame()

# Получение информации о птице через eBird API
def get_bird_info(species_code):
    # Формируем URL с параметрами
    url = f"{EBIRD_API_URL}?species={species_code}&fmt=json&locale=ru"
    headers = {"X-eBirdApiToken": EBIRD_API_KEY}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Не удалось получить информацию о птице. Статус: {response.status_code}")
            st.error(f"Ответ: {response.text}")  # Выводим текст ответа для отладки
    except Exception as e:
        st.error(f"Ошибка при запросе данных: {e}")
    return None

def get_bird_image(bird_name):
    WIKIMEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
    
    # Заменяем пробелы на символы подчеркивания
    formatted_bird_name = bird_name.replace(" ", "_").lower()  # Приводим к нижнему регистру
    
    params = {
        "action": "query",
        "format": "json",
        "prop": "pageimages",
        "titles": formatted_bird_name,
        "pithumbsize": 500  # Размер изображения в пикселях
    }
    
    try:
        response = requests.get(WIKIMEDIA_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Достаём изображение
        pages = data.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if "thumbnail" in page_data:
                return page_data["thumbnail"]["source"]
            else:
                # Проверка на наличие страницы
                if "missing" in page_data:
                    st.warning(f"Страница не найдена для '{bird_name}'.")
                else:
                    st.warning(f"Изображение не найдено для '{bird_name}'.")
                return None
        
    except requests.RequestException as e:
        st.error(f"Ошибка сети при обращении к WikiMedia API: {e}")
        return None
    except Exception as e:
        st.error(f"Неизвестная ошибка: {e}")
        return None


# Загружаем данные
file_path = "./top_30.csv"  # Укажите путь к вашему файлу
data = load_data(file_path)

# Проверяем, что необходимые колонки есть в данных
required_columns = {"latitude", "longitude", "common_name", "primary_label"}
if not required_columns.issubset(data.columns):
    st.error(f"Файл {file_path} должен содержать следующие столбцы: {', '.join(required_columns)}")
else:
    # Генерируем уникальные цвета для каждого вида птиц
    unique_species = data["common_name"].unique()
    species_colors = {species: random_color() for species in unique_species}
    
    # Присваиваем цвет каждой записи в данных
    data["color"] = data["common_name"].map(species_colors)

    # Фильтруем данные
    species = st.sidebar.selectbox("Выберите вид птицы", options=["Все"] + list(data["common_name"].unique()))
    if species != "Все":
        filtered_data = data[data["common_name"] == species]
    else:
        filtered_data = data

    # Основной заголовок
    st.title("Интерактивная карта птиц")
    st.write("На карте показано распределение птиц по широте и долготе.")

    # Pydeck визуализация
    view_state = pdk.ViewState(
        latitude=filtered_data["latitude"].mean(),
        longitude=filtered_data["longitude"].mean(),
        zoom=3,
        pitch=0
    )

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=filtered_data,
        get_position="[longitude, latitude]",
        get_color="color",
        get_radius=50000,  # Радиус точек в метрах
    )

    r = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"text": "{common_name}"},
    )

    # Отображаем карту
    st.pydeck_chart(r)

    # Если выбран вид, отображаем информацию
    if species != "Все":
        st.subheader(f"Информация о птице: {species}")

        # Получаем информацию о птице
        species_code = data[data["common_name"] == species]["primary_label"].iloc[0]
        bird_info = get_bird_info(species_code)

        if bird_info:
            # Проверяем, является ли bird_info списком
            if isinstance(bird_info, list) and len(bird_info) > 0:
                first_bird_info = bird_info[0]  # Получаем первый элемент списка
                st.write(f"**Научное название:** {first_bird_info.get('sciName', 'Нет данных')}")
                st.write(f"**Название на русском:** {first_bird_info.get('comName', 'Нет данных')}")
            else:
                st.write("Нет информации о птице.")

        # Получаем изображение птицы
        bird_image = get_bird_image(species)
        if bird_image:
            st.image(bird_image, caption=f"Изображение {species}", use_column_width=True)
        else:
            st.write("Изображение не найдено.")
