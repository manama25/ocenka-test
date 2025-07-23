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


# --- Генерация PDF-отчёта с поддержкой кириллицы ---
def generate_pdf_report():
    try:
        pdf = FPDF()
        pdf.add_page()

        # Подключаем шрифт с поддержкой кириллицы
        pdf.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
        pdf.set_font("DejaVu", size=12)

        pdf.cell(200, 10, txt="Отчёт по результатам тестирования", ln=True, align='C')
        pdf.ln(10)

        results = load_results()
        if not results:
            pdf.cell(200, 10, txt="Нет данных для отчёта", ln=True)
        else:
            pdf.set_font("DejaVu", size=10)
            for r in results[-10:]:
                line = f"{r['user']} — {r['score']:.1f}% — {r['timestamp'][:10]}"
                pdf.cell(200, 8, txt=line, ln=True)

        # Возвращаем PDF как байты (без .encode())
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
        st.success("Файл обновлён! Перезапустите приложение.")
        st.cache_data.clear()


# --- Редактор вопросов ---
def edit_questions():
    st.subheader("✏️ Редактор вопросов")
    questions = load_data()
    df = pd.DataFrame(questions)
    st.data_editor(df, num_rows="dynamic", key="edited_questions")


# --- Админ-панель ---
def admin_panel():
    st.title("🔐 Админ-панель")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Пользователи", "Результаты", "Анализ", "Экспорт", "Вопросы"])

    with tab1:
        st.subheader("📋 Пользователи")
        users = load_users()
        for user in users:
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
        if excel_:
            st.download_button(
                label="Скачать Excel",
                data=excel_data,
                file_name=f"результаты_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        # PDF
        pdf_data = generate_pdf_report()
        if pdf_:
            st.download_button(
                label="Скачать PDF-отчёт",
                data=pdf_data,
                file_name="отчет.pdf",
                mime="application/pdf"
            )
        else:
            st.info("PDF-отчёт недоступен (проверьте наличие файла DejaVuSans.ttf)")

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
            'start_time': None,
            'end_time': None,
            'test_questions': [],
            'answers': {},
            'timer_enabled': True
        })

    if not st.session_state.logged_in:
        show_auth()
    else:
        if st.session_state.user == "admin":
            show_admin_sidebar()
        test_interface()


# --- Сайдбар для админа ---
def show_admin_sidebar():
    st.sidebar.title("Админ")
    if st.sidebar.button("🔐 Админ-панель"):
        st.session_state.page = "admin"
        st.rerun()


# --- Авторизация ---
def show_auth():
    tab1, tab2 = st.tabs(["🔐 Вход", "📝 Регистрация"])

    with tab1:
        login()
    with tab2:
        register()


def login():
    st.header("Авторизация")
    login_input = st.text_input("Логин", key="login_username")
    password = st.text_input("Пароль", type="password", key="login_password")

    if st.button("Войти", key="login_button"):
        users = load_users()
        hashed = hash_password(password)
        if login_input in users and users[login_input] == hashed:
            st.session_state.logged_in = True
            st.session_state.user = login_input
            st.success(f"Добро пожаловать, {login_input}!")
            st.rerun()
        else:
            st.error("Неверный логин или пароль")


def register():
    st.header("Регистрация")
    new_login = st.text_input("Логин", key="register_username")
    new_password = st.text_input("Пароль", type="password", key="register_password")
    confirm_password = st.text_input("Подтвердите пароль", type="password", key="register_confirm_password")

    if st.button("Зарегистрироваться", key="register_submit"):
        if new_password != confirm_password:
            st.error("Пароли не совпадают")
        elif len(new_password) < 4:
            st.error("Пароль слишком короткий")
        elif len(new_login) < 3:
            st.error("Логин слишком короткий")
        else:
            success, msg = register_user(new_login, new_password)
            if success:
                st.success(msg)
            else:
                st.error(msg)


# --- Интерфейс теста ---
def test_interface():
    if st.session_state.get('page') == 'admin':
        admin_panel()
        if st.button("◀️ Вернуться к тесту"):
            st.session_state.page = None
            st.rerun()
        return

    questions = load_data()
    if not questions:
        st.error("Не удалось загрузить вопросы.")
        return

    st.sidebar.write(f"👤 {st.session_state.user}")

    mode = st.sidebar.radio("Режим", ["Все вопросы", "По 10 из каждого раздела"], key="mode_select")
    st.sidebar.subheader("⏱️ Таймер")
    timer_enabled = st.sidebar.checkbox("Включить таймер", value=True, key="timer_checkbox")
    duration = 30
    if timer_enabled:
        duration = st.sidebar.slider("Длительность (мин)", 10, 120, 30, key="timer_slider")
    else:
        st.sidebar.info("Таймер отключен")

    if st.sidebar.button("🚀 Начать тест", key="start_test"):
        st.session_state.test_started = True
        st.session_state.timer_enabled = timer_enabled
        if timer_enabled:
            st.session_state.start_time = datetime.now()
            st.session_state.end_time = datetime.now() + timedelta(minutes=duration)
        else:
            st.session_state.start_time = None
            st.session_state.end_time = None
        st.session_state.test_questions = get_sampled_questions(questions) if mode == "По 10 из каждого раздела" else questions.copy()
        st.session_state.answers = {}
        st.session_state.page = None
        st.rerun()

    if st.sidebar.button("📊 Анализ результатов", key="analyze_results"):
        analyze_results()

    if st.sidebar.button("🚪 Выйти", key="logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    if st.session_state.test_started:
        run_test_with_timer()
    else:
        st.info("Выберите режим и нажмите «Начать тест»")


# --- Прохождение теста с таймером ---
def run_test_with_timer():
    st.header(f"📝 Тест: {len(st.session_state.test_questions)} вопросов")

    if st.session_state.timer_enabled:
        time_left = st.session_state.end_time - datetime.now()
        if time_left.total_seconds() <= 0:
            st.warning("⏰ Время вышло!")
            finish_test()
            return

        mins, secs = divmod(time_left.seconds, 60)
        st.info(f"Осталось времени: **{mins:02d}:{secs:02d}**")

        st.markdown("""
        <script>
        setTimeout(function() {
            window.location.reload();
        }, 1000);
        </script>
        """, unsafe_allow_html=True)

    user_answers = st.session_state.answers
    for i, q in enumerate(st.session_state.test_questions):
        st.markdown(f"### {i+1}. {q['text']}")
        options = [f"{idx}. {opt}" for idx, opt in enumerate(q['options'], 1)]
        choice = st.radio("Выберите ответ:", options, index=None, key=f"q_{q['num']}", label_visibility="collapsed")
        user_answers[q['num']] = choice

    if st.button("✅ Завершить тест", key="finish_test"):
        finish_test()


# --- Завершение теста ---
def finish_test():
    st.session_state.test_started = False
    test_questions = st.session_state.test_questions
    user_answers = st.session_state.answers

    correct_count = 0
    results = []

    for q in test_questions:
        answer_str = user_answers.get(q['num'])
        answer_idx = int(answer_str.split('.')[0]) if answer_str else -1
        is_correct = (answer_idx == q['correct'])
        if is_correct:
            correct_count += 1

        results.append({
            'num': q['num'],
            'answered': answer_idx,
            'correct': q['correct'],
            'is_correct': is_correct,
            'section': q['section']
        })

    total = len(test_questions)
    score = correct_count / total * 100 if total > 0 else 0
    time_used = datetime.now() - st.session_state.start_time if st.session_state.start_time else timedelta(seconds=0)

    save_result(st.session_state.user, score, total, correct_count, results, time_used)

    st.success(f"✅ Готово! {correct_count}/{total} ({score:.1f}%)")
    if st.session_state.timer_enabled:
        st.metric("Затрачено времени", str(time_used).split('.')[0])

    st.subheader("📋 Разбор ответов")
    for q in test_questions:
        answer_str = user_answers.get(q['num'])
        answer_idx = int(answer_str.split('.')[0]) if answer_str else -1
        is_correct = (answer_idx == q['correct'])
        status = "✅" if is_correct else "❌"
        st.markdown(f"{status} **{q['num']}**: {q['text']}")
        if not is_correct:
            corr = q['options'][q['correct']-1]
            st.caption(f"Правильно: {q['correct']}. {corr}")


if __name__ == "__main__":
    main()
