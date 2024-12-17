import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import ast
import random

# API eBird
EBIRD_API_URL = "https://api.ebird.org/v2/ref/taxonomy/ebird"
EBIRD_API_KEY = "nusv3bd5ltqk"

# Заголовок страницы
st.set_page_config(page_title="Интерактивная карта птиц", layout="wide")

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

# Генерация случайного цвета
def random_color(alpha=160):
    return [random.randint(0, 255) for _ in range(3)] + [alpha]

# Получение информации о птице через eBird API
def get_bird_info(species_code):
    url = f"{EBIRD_API_URL}?species={species_code}&fmt=json&locale=ru"
    headers = {"X-eBirdApiToken": EBIRD_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Не удалось получить информацию о птице. Статус: {response.status_code}")
    except Exception as e:
        st.error(f"Ошибка при запросе данных: {e}")
    return None

# Получение изображения птицы через Wikimedia API
def get_bird_image(bird_name):
    WIKIMEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
    formatted_bird_name = bird_name.replace(" ", "_").lower()
    params = {
        "action": "query",
        "format": "json",
        "prop": "pageimages",
        "titles": formatted_bird_name,
        "pithumbsize": 500
    }
    try:
        response = requests.get(WIKIMEDIA_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if "thumbnail" in page_data:
                return page_data["thumbnail"]["source"]
            else:
                return None
    except requests.RequestException as e:
        return None
    except Exception as e:
        return None

# Функция для отслеживания динамики
def bird_dynamics(df, bird='', longitude_left=-180, longitude_right=180, latitude_min=-90, latitude_max=90,
                  start_date=None, end_date=None):
    """
    Функция выдает датафрейм с динамикой количества записей конкретного вида птиц с учетом фильтров по локации и периоду.
    Возвращает стилизованный датафрейм, где строки закрашены в цвет уровня риска.
    """
    # Проверка обязательных параметров
    if bird == '':
        print('Необходимо указать код птицы (primary_label)!')
        return None

    # Преобразование дат
    if start_date:
        start_date = pd.to_datetime(start_date)
    if end_date:
        end_date = pd.to_datetime(end_date)

    # Фильтрация по дате
    if start_date or end_date:
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        if start_date:
            df = df[df['date'] >= start_date]
        if end_date:
            df = df[df['date'] <= end_date]

    # Проверка наличия данных после фильтрации
    if df.empty:
        print('Данные с указанными параметрами не обнаружены')
        return None

    # Фильтрация по локации
    df_filtered = df[(df['longitude'] >= longitude_left) & (df['longitude'] <= longitude_right) &
                     (df['latitude'] >= latitude_min) & (df['latitude'] <= latitude_max)]

    # Группировка по годам для всех видов
    df_total_records = df_filtered.groupby(df_filtered['date'].dt.year).agg({'latitude': 'count'}).reset_index()
    df_total_records.columns = ["Год", "Общее количество записей"]

    # Фильтрация данных для конкретного вида
    df_bird = df_filtered[df_filtered['primary_label'] == bird]
    df_bird_records = df_bird.groupby(df_bird['date'].dt.year).agg({'latitude': 'count'}).reset_index()
    df_bird_records.columns = ["Год", "Количество записей вида"]

    # Объединение данных
    df_result = pd.merge(df_total_records, df_bird_records, on='Год', how='left').fillna(0)
    df_result['Количество записей вида'] = df_result['Количество записей вида'].astype(int)

    # Рассчёт относительной частоты записей (единиц на тысячу записей)
    df_result['Частота'] = df_result['Количество записей вида'] / df_result['Общее количество записей'] * 1000

    # Скользящее среднее и риск вымирания
    min_records_in_database = 40
    min_mov_avg_or_bird_counts = 3
    threshold_drop_in_counts = 0.7
    threshold_drop_in_frequency = 0.8

    df_result['Скользящее среднее (всего)'] = df_result['Общее количество записей'].rolling(3, min_periods=1).mean()
    df_result['Скользящее среднее (вида)'] = df_result['Количество записей вида'].rolling(3, min_periods=1).mean()
    df_result['Скользящее среднее (частота)'] = df_result['Частота'].rolling(3, min_periods=1).mean()

    df_result['Уровень риска вымирания'] = 'Нет данных'
    for i in range(len(df_result)):
        if (df_result.loc[i, 'Скользящее среднее (всего)'] >= min_records_in_database) and \
           (df_result.loc[i, 'Скользящее среднее (вида)'] >= min_mov_avg_or_bird_counts):
            if (df_result.loc[i, 'Количество записей вида'] / df_result.loc[i, 'Скользящее среднее (вида)'] <= threshold_drop_in_counts) or \
               (df_result.loc[i, 'Частота'] / df_result.loc[i, 'Скользящее среднее (частота)'] <= threshold_drop_in_frequency):
                if (df_result.loc[i, 'Количество записей вида'] / df_result.loc[i, 'Скользящее среднее (вида)'] <= threshold_drop_in_counts) and \
                   (df_result.loc[i, 'Частота'] / df_result.loc[i, 'Скользящее среднее (частота)'] <= threshold_drop_in_frequency):
                    df_result.loc[i, 'Уровень риска вымирания'] = 'Высокий'
                else:
                    df_result.loc[i, 'Уровень риска вымирания'] = 'Средний'
            else:
                df_result.loc[i, 'Уровень риска вымирания'] = 'Низкий'

    # Применение стилей
    def color_rows(row):
        """Возвращает стили для строки в зависимости от уровня риска."""
        color = {
            'Нет данных': 'background-color: lightgray;',
            'Низкий': 'background-color: lightgreen;',
            'Средний': 'background-color: yellow;',
            'Высокий': 'background-color: lightcoral;'
        }.get(row['Уровень риска вымирания'], '')
        return [color] * len(row)

    # Перед стилизацией возвращаем весь датафрейм
    return df_result.style.apply(color_rows, axis=1)

# Загружаем данные
file_path = "./top_30.csv"
data = load_data(file_path)

# Проверяем наличие необходимых столбцов
required_columns = {"latitude", "longitude", "common_name", "primary_label", "date"}
if not required_columns.issubset(data.columns):
    st.error(f"Файл {file_path} должен содержать следующие столбцы: {', '.join(required_columns)}")
else:
    unique_species = data["common_name"].unique()
    species_colors = {species: random_color() for species in unique_species}
    data["color"] = data["common_name"].map(species_colors)

    # Основной заголовок
    st.title("Интерактивная карта птиц")
    st.write("На карте показано распределение птиц по широте и долготе.")

    # Виджет выбора вида птиц
    species = st.sidebar.selectbox("Вид птицы", options=["Все"] + list(unique_species))
    filtered_data = data if species == "Все" else data[data["common_name"] == species]

    # Виджет выбора широты и долготы
    min_lat, max_lat = data["latitude"].min(), data["latitude"].max()
    min_lon, max_lon = data["longitude"].min(), data["longitude"].max()
    lat_range = st.sidebar.slider("Диапазон широты", min_lat, max_lat, (min_lat, max_lat))
    lon_range = st.sidebar.slider("Диапазон долготы", min_lon, max_lon, (min_lon, max_lon))
    filtered_data = filtered_data[(filtered_data["latitude"] >= lat_range[0]) & (filtered_data["latitude"] <= lat_range[1]) &
                                   (filtered_data["longitude"] >= lon_range[0]) & (filtered_data["longitude"] <= lon_range[1])]

    # Виджет выбора даты
    min_date, max_date = pd.to_datetime(data['date']).min(), pd.to_datetime(data['date']).max()
    start_date = st.sidebar.date_input("Начало периода", min_date, min_value=min_date, max_value=max_date, format="DD.MM.YYYY")
    end_date = st.sidebar.date_input("Конец периода", max_date, min_value=start_date, max_value=max_date, format="DD.MM.YYYY")
    filtered_data = filtered_data[(pd.to_datetime(filtered_data['date']) >= pd.to_datetime(start_date)) & 
                                   (pd.to_datetime(filtered_data['date']) <= pd.to_datetime(end_date))]

    # Фильтрация по виду птицы
    if species != "Все":
        filtered_data = filtered_data[
            filtered_data["common_name"].str.strip().str.lower() == species.strip().lower()
        ]

    # Фильтрация по широте и долготе
    filtered_data = filtered_data[
        (filtered_data["latitude"] >= lat_range[0]) & 
        (filtered_data["latitude"] <= lat_range[1]) &
        (filtered_data["longitude"] >= lon_range[0]) & 
        (filtered_data["longitude"] <= lon_range[1])
    ]

    # Преобразование столбца 'date' в datetime и фильтрация по дате
    filtered_data['date'] = pd.to_datetime(filtered_data['date'], errors='coerce')  # Преобразование с обработкой ошибок
    filtered_data = filtered_data.dropna(subset=['date'])  # Удаляем записи с некорректными датами
    filtered_data = filtered_data[
        (filtered_data['date'] >= pd.to_datetime(start_date)) & 
        (filtered_data['date'] <= pd.to_datetime(end_date))
    ]

    # Pydeck визуализация
    if not filtered_data.empty:
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
            get_radius=50000,
        )
        r = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={"text": "{common_name}"},
        )
        st.pydeck_chart(r)
        
        # Статистика
        st.subheader("Статистика наблюдений")
        total_observations = len(filtered_data)
        unique_species_count = filtered_data["common_name"].nunique()
        observation_dates = filtered_data["date"].nunique()

        stats_data = {
            "Общее количество наблюдений": [total_observations],
            "Количество уникальных видов птиц": [unique_species_count],
            "Количество уникальных дней наблюдений": [observation_dates]
        }

        stats_df = pd.DataFrame(stats_data)
        st.markdown(stats_df.style.hide(axis="index").to_html(), unsafe_allow_html=True)

        # Отступ
        placeholder = st.empty()
        placeholder.write("")

        # Проверка: выбран ли конкретный вид птицы
        selected_bird = species != "Все"

        if selected_bird:
            st.subheader(f"Динамика наблюдений и риск вымирания для: {species}")

            # Получение кода птицы
            bird_code = filtered_data[filtered_data["common_name"] == species]["primary_label"].iloc[0]

            # Вызов bird_dynamics
            df_bird_dynamics = bird_dynamics(
                df=data,
                bird=bird_code,
                longitude_left=lon_range[0],
                longitude_right=lon_range[1],
                latitude_min=lat_range[0],
                latitude_max=lat_range[1],
                start_date=start_date,
                end_date=end_date,
            )

            if df_bird_dynamics is not None:
                st.write(df_bird_dynamics)
            else:
                st.warning("Недостаточно данных для анализа выбранного вида птицы.")
    else:
        st.warning("Нет данных для отображения на карте.")

    # Отображаем информацию о выбранной птице
    if species != "Все":
        st.subheader(f"Информация о птице: {species}")
        species_code = data[data["common_name"] == species]["primary_label"].iloc[0]
        bird_info = get_bird_info(species_code)

        if bird_info:
            if isinstance(bird_info, list) and bird_info:
                first_bird_info = bird_info[0]
                st.write(f"**Научное название:** {first_bird_info.get('sciName', 'Нет данных')}")
                st.write(f"**Название на русском:** {first_bird_info.get('comName', 'Нет данных')}")
            else:
                st.write("Нет информации о птице.")

        bird_image = get_bird_image(species)
        if bird_image:
            st.image(bird_image, caption=species)
        else:
            st.write("Изображение не найдено.")
