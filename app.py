# app.py
import streamlit as st
import pandas as pd
import random
import json
import os
import hashlib
from datetime import datetime, timedelta
from io import BytesIO

# --- Настройки ---
DATA_FILE = 'test_teoriya.xlsx'
USERS_FILE = 'users.json'
RESULTS_FILE = 'results.json'

# --- Загрузка данных ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel(DATA_FILE, sheet_name='теория', engine='openpyxl')
    except Exception as e:
        st.error(f"Ошибка загрузки Excel: {e}")
        return []

    questions = []
    for _, row in df.iterrows():
        if pd.isna(row['Правильный ответ']):
            continue

        options = []
        for i in range(1, 6):
            col = f'Вариант {i}'
            if col in row and pd.notna(row[col]):
                options.append(str(row[col]).strip())

        correct_text = str(row['Правильный ответ']).strip()

        try:
            correct_idx = options.index(correct_text) + 1
        except ValueError:
            st.warning(f"Пропущен вопрос {row['Номер вопроса']}: правильный ответ не найден")
            continue

        question = {
            'num': row['Номер вопроса'],
            'text': row['Текст вопроса'].strip(),
            'options': options,
            'correct': correct_idx,
            'section': row['Раздел']
        }
        questions.append(question)

    return questions


# --- Управление пользователями ---
def load_users():
    if not os.path.exists(USERS_FILE):
        default_users = {"admin": hashlib.sha256("123".encode()).hexdigest()}
        save_users(default_users)
        return default_users
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(username, password):
    users = load_users()
    if username in users:
        return False, "Логин занят"
    users[username] = hash_password(password)
    save_users(users)
    return True, "Регистрация успешна!"


# --- Сохранение результатов ---
def save_result(user, score, total, correct_count, results, time_used):
    result = {
        'user': user,
        'timestamp': datetime.now().isoformat(),
        'score': score,
        'total': total,
        'correct': correct_count,
        'time_used': str(time_used),
        'results': results
    }
    all_results = []
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            try:
                all_results = json.load(f)
            except:
                pass
    all_results.append(result)
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)


# --- Загрузка результатов ---
def load_results():
    if not os.path.exists(RESULTS_FILE):
        return []
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except:
            return []


# --- Анализ результатов ---
def analyze_results():
    results = load_results()
    if not results:
        st.info("Нет данных для анализа.")
        return

    stats = {}
    section_stats = {}

    for session in results:
        for res in session['results']:
            q_num = res['num']
            sec = res['section']

            if q_num not in stats:
                stats[q_num] = {'total': 0, 'correct': 0}
            if sec not in section_stats:
                section_stats[sec] = {'total': 0, 'correct': 0}

            stats[q_num]['total'] += 1
            if res['is_correct']:
                stats[q_num]['correct'] += 1

            section_stats[sec]['total'] += 1
            if res['is_correct']:
                section_stats[sec]['correct'] += 1

    st.subheader("🔥 Самые сложные вопросы (<70%)")
    difficult = []
    for q, s in stats.items():
        perc = s['correct'] / s['total'] * 100
        if perc < 70:
            difficult.append((q, perc, s['total']))
    difficult.sort(key=lambda x: x[1])
    if difficult:
        df_diff = pd.DataFrame(difficult, columns=["Номер", "Правильно, %", "Всего ответов"])
        st.dataframe(df_diff, use_container_width=True)
    else:
        st.write("Нет особенно сложных вопросов.")

    st.subheader("📊 Эффективность по разделам")
    df_sec = []
    for sec, s in section_stats.items():
        perc = s['correct'] / s['total'] * 100
        df_sec.append({"Раздел": sec, "Процент": perc, "Правильно": s['correct'], "Всего": s['total']})
    df_sec = pd.DataFrame(df_sec)
    st.bar_chart(df_sec.set_index("Раздел")["Процент"])
    st.dataframe(df_sec, use_container_width=True)


# --- Анализ по логинам ---
def analyze_by_user():
    st.subheader("🔍 Анализ по логинам")
    results = load_results()
    if not results:
        st.info("Нет результатов тестирования.")
        return

    users = sorted(list(set(r['user'] for r in results)))
    selected_user = st.selectbox("Выберите пользователя", users)

    user_results = [r for r in results if r['user'] == selected_user]
    st.write(f"**Результаты пользователя: {selected_user}**")

    for i, r in enumerate(user_results, 1):
        st.markdown(f"### Попытка {i}")
        st.write(f"📅 Дата: {r['timestamp'][:16]}")
        st.write(f"📊 Результат: **{r['correct']}/{r['total']} ({r['score']:.1f}%)**")
        st.write(f"⏱️ Время: {r['time_used']}")

        with st.expander("Разбор ответов"):
            for res in r['results']:
                status = "✅" if res['is_correct'] else "❌"
                st.markdown(f"{status} **{res['num']}**:
