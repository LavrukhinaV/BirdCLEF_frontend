import streamlit as st
import pandas as pd
import pydeck as pdk

# Заголовок страницы
st.set_page_config(page_title="Интерактивная карта птиц", layout="wide")  # Устанавливаем заголовок и широкую верстку

# Загружаем данные
data = pd.DataFrame({
    "latitude": [52.52, 40.7128, 34.0522, 48.8566, -33.8688],
    "longitude": [13.405, -74.006, -118.243, 2.3522, 151.2093],
    "bird_species": ["Sparrow", "Eagle", "Parrot", "Pigeon", "Penguin"]
})

# Добавляем цвет для каждого вида
species_colors = {
    "Sparrow": [255, 0, 0, 160],  # Красный
    "Eagle": [0, 255, 0, 160],    # Зеленый
    "Parrot": [0, 0, 255, 160],   # Синий
    "Pigeon": [255, 255, 0, 160], # Желтый
    "Penguin": [255, 0, 255, 160] # Фиолетовый
}
data["color"] = data["bird_species"].map(species_colors)

# Боковая панель для фильтрации
species = st.sidebar.selectbox("Выберите вид птицы", options=["Все"] + list(data["bird_species"].unique()))

# Фильтрация данных
if species != "Все":
    filtered_data = data[data["bird_species"] == species]
else:
    filtered_data = data

# Основной заголовок страницы
st.title("Интерактивная карта птиц")
st.write("На карте показано распределение птиц по широте и долготе.")

# Pydeck визуализация
view_state = pdk.ViewState(
    latitude=filtered_data["latitude"].mean(),
    longitude=filtered_data["longitude"].mean(),
    zoom=2,
    pitch=0
)

layer = pdk.Layer(
    "ScatterplotLayer",
    data=filtered_data,
    get_position="[longitude, latitude]",
    get_color="color",  # Используем цвет из столбца
    get_radius=100000,  # Радиус точек в метрах
)

r = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    tooltip={"text": "{bird_species}"},
)

# Отображаем карту
st.pydeck_chart(r)
