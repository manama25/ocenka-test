# app.py
import streamlit as st
import pandas as pd
import random
import json
import os
import hashlib
from datetime import datetime, timedelta
from io import BytesIO
from fpdf import FPDF

# --- Настройки ---
DATA_FILE = 'test_teoriya.xlsx'
USERS_FILE = 'users.json'
RESULTS_FILE = 'results.json'

# --- Загрузка данных ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel(DATA_FILE, sheet_name='теория', engine='openpyxl')
    except FileNotFoundError:
        st.error(f"Файл '{DATA_FILE}' не найден!")
        return []
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


# --- Отбор по 10 вопросов из каждого раздела ---
def get_sampled_questions(questions):
    by_section = {}
    for q in questions:
        sec = q['section']
        if sec not in by_section:
            by_section[sec] = []
        by_section[sec].append(q)

    sampled = []
    for sec, qs in by_section.items():
        selected = random.sample(qs, min(10, len(qs)))
        sampled.extend(selected)
    random.shuffle(sampled)
    return sampled


# --- Экспорт в Excel ---
def export_results_to_excel():
    results = load_results()
    if not results:
        st.warning("Нет результатов для экспорта.")
        return None

    data = []
    for session in results:
        for res in session['results']:
            data.append({
                'Пользователь': session['user'],
                'Дата': session['timestamp'],
                'Номер вопроса': res['num'],
                'Правильно': 'Да' if res['is_correct'] else 'Нет',
                'Раздел': res['section']
            })

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Результаты')
    return output.getvalue()


# --- Генерация PDF-отчета с поддержкой кириллицы ---
def generate_pdf_report():
    font_path = "DejaVuSans.ttf"
    if not os.path.isfile(font_path):
        st.error("Файл шрифта DejaVuSans.ttf не найден. Пожалуйста, добавьте его в каталог проекта.")
        return None

    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=12)

        pdf.cell(200, 10, txt="Отчёт по результатам тестирования", ln=True, align='C')
        pdf.ln(10)

        results = load_results()
        if not results:
            pdf.cell(200, 10, txt="Нет данных для отчёта", ln=True)
        else:
            pdf.set_font("DejaVu", size=10)
            for r in sorted(results, key=lambda x: x['timestamp'], reverse=True):
                line = f"{r['user']} — {r['score']:.1f}% — {r['timestamp'][:10]}"
                pdf.cell(200, 8, txt=line, ln=True)

        return pdf.output(dest='S')

    except Exception as e:
        st.error(f"Ошибка генерации PDF: {e}")
        return None


# --- Загрузка нового файла ---
def upload_new_data():
    st.subheader("📤 Обновить базу вопросов")
    uploaded = st.file_uploader("Загрузите новый Excel-файл", type=["xlsx"])
    if uploaded:
        with open(DATA_FILE, "wb") as f:
            f.write(uploaded.read())
        st.success("Файл обновлен! Перезапустите приложение.")
        st.cache_data.clear()


# --- Редактор вопросов ---
def edit_questions():
    st.subheader("✏️ Редактор вопросов")
    questions = load_data()
    df = pd.DataFrame(questions)
    edited_df = st.data_editor(df, num_rows="dynamic", key="edited_questions")
    if st.button("Сохранить изменения"):
        edited_questions = edited_df.to_dict('records')
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(edited_questions, f, ensure_ascii=False, indent=2)
        st.success("Изменения сохранены!")


# --- Логика выхода из аккаунта
def logout():
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.test_started = False
    st.session_state.start_time = None


# --- Админ-панель ---
def admin_panel():
    st.title("🔐 Админ-панель")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Пользователи", "Результаты", "Анализ", "Экспорт", "Вопросы"])

    with tab1:
        st.subheader("📌 Пользователи")
        users = load_users()
        for user in list(users.keys()):
            col1, col2 = st.columns([4, 1])
            col1.write(f"👤 {user}")
            if user != "admin":
                if col2.button("Удалить", key=f"del_{user}"):
                    del users[user]
                    save_users(users)
                    st.success(f"Пользователь {user} удалён")
                    st.rerun()

    with tab2:
        st.subheader("📊 Все результаты")
        results = load_results()
        if not results:
            st.info("Нет результатов")
        else:
            df = pd.DataFrame([
                {
                    'Пользователь': r['user'],
                    'Дата': r['timestamp'][:16],
                    'Результат': f"{r['correct']}/{r['total']} ({r['score']:.1f}%)",
                    'Время': r['time_used']
                } for r in results
            ])
            st.dataframe(df, use_container_width=True)

    with tab3:
        analyze_results()

    with tab4:
        st.subheader("💾 Экспорт данных")

        # Excel
        excel_data = export_results_to_excel()
        if excel_data is not None:
            st.download_button(
                label="Скачать Excel",
                data=excel_data,
                file_name=f"результаты_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Excel экспорт недоступен (нет данных).")

        # PDF
        pdf_data = generate_pdf_report()
        if pdf_data is not None:
            st.download_button(
                label="Скачать PDF-отчёт",
                data=pdf_data,
                file_name="отчет.pdf",
                mime="application/pdf"
            )
        else:
            st.info("PDF отчёт недоступен (проверьте наличие файла DejaVuSans.ttf)")

    with tab5:
        upload_new_data()
        edit_questions()


# --- Главное приложение ---
def main():
    st.set_page_config(page_title="Тест по оценке недвижимости", layout="centered")

    if 'logged_in' not in st.session_state:
        st.session_state.update({
            'logged_in': False,
            'user': None,
            'test_started': False,
            'start_time': None
        })

    if not st.session_state.logged_in:
        st.header("Авторизация")
        username = st.text_input("Имя пользователя:")
        password = st.text_input("Пароль:", type="password")
        login_clicked = st.button("Войти")
        register_clicked = st.button("Зарегистрироваться")

        if login_clicked or register_clicked:
            users = load_users()
            hashed_pass = hash_password(password)
            
            if login_clicked:
                if username in users and users[username] == hashed_pass:
                    st.session_state.logged_in = True
                    st.session_state.user = username
                    st.success("Вы успешно вошли!")
                else:
                    st.error("Неправильное имя пользователя или пароль.")
                    
            elif register_clicked:
                success, message = register_user(username, password)
                st.info(message)
                
    else:
        menu_options = ["Главная страница", "Администратор"]
        choice = st.sidebar.selectbox("Меню", menu_options)

        if choice == "Главная страница":
            st.title("Добро пожаловать в тест по оценке недвижимости!")
            st.write(f"Ваш аккаунт: {st.session_state.user}")
            st.button("Выход", on_click=logout)

        elif choice == "Администратор":
            admin_panel()

if __name__ == "__main__":
    main()
