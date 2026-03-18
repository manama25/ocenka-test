# ============================================================================
# ПОЛНАЯ ВЕРСИЯ ПРИЛОЖЕНИЯ ДЛЯ ТЕСТИРОВАНИЯ
# Оценка недвижимости - с регистрацией, админ-панелью и отчётами
# ============================================================================

import streamlit as st
import pandas as pd
import random
import json
import os
import hashlib
from datetime import datetime, timedelta
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ============================================================================
# НАСТРОЙКИ
# ============================================================================
DATA_FILE = 'test_teoriya.xlsx'
USERS_FILE = 'users.json'
RESULTS_FILE = 'results.json'

# ============================================================================
# ЗАГРУЗКА ДАННЫХ ИЗ EXCEL
# ============================================================================
@st.cache_data
def load_data():
    """Загрузка вопросов из Excel файла"""
    try:
        df = pd.read_excel(DATA_FILE, sheet_name='теория', engine='openpyxl')
    except Exception as e:
        st.error(f"❌ Ошибка загрузки Excel: {e}")
        return []
    
    questions = []
    for _, row in df.iterrows():
        if pd.isna(row.get('Правильный ответ', '')):
            continue
        
        options = []
        for i in range(1, 6):
            col = f'Вариант {i}'
            if col in row and pd.notna(row.get(col, '')):
                options.append(str(row[col]).strip())
        
        correct_text = str(row['Правильный ответ']).strip()
        try:
            correct_idx = options.index(correct_text) + 1
        except ValueError:
            continue
        
        question = {
            'num': str(row.get('Номер вопроса', '')),
            'text': str(row.get('Текст вопроса', '')).strip(),
            'options': options,
            'correct': correct_idx,
            'section': str(row.get('Раздел', '')).strip()
        }
        questions.append(question)
    
    return questions

# ============================================================================
# УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
# ============================================================================
def load_users():
    """Загрузка данных пользователей из JSON"""
    if not os.path.exists(USERS_FILE):
        default_users = {
            "admin": {
                "hash": hashlib.sha256("admin123".encode()).hexdigest(),
                "fullname": "Администратор",
                "is_active": True,
                "is_admin": True,
                "registered_at": datetime.now().isoformat(),
                "last_login": None,
                "tests_taken": 0
            }
        }
        save_users(default_users)
        return default_users
    
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return load_users()
            users = json.loads(content)
            if not isinstance(users, dict):
                return load_users()
            return users
    except Exception as e:
        print(f"Ошибка загрузки пользователей: {e}")
        return load_users()

def save_users(users):
    """Сохранение данных пользователей в JSON"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def hash_password(password):
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password, fullname):
    """Регистрация нового пользователя"""
    users = load_users()
    if username in users:
        return False, "❌ Логин уже занят"
    users[username] = {
        "hash": hash_password(password),
        "fullname": fullname.strip(),
        "is_active": False,
        "is_admin": False,
        "registered_at": datetime.now().isoformat(),
        "last_login": None,
        "tests_taken": 0
    }
    save_users(users)
    return True, "✅ Регистрация отправлена. Ожидайте подтверждения администратора!"

def login_user(username, password):
    """Вход пользователя в систему"""
    users = load_users()
    if username not in users:
        return False, "❌ Пользователь не найден"
    user = users[username]
    if user["hash"] != hash_password(password):
        return False, "❌ Неверный пароль"
    if not user.get("is_active", False) and not user.get("is_admin", False):
        return False, "⏳ Аккаунт ожидает подтверждения администратора"
    
    # Записываем время последнего входа
    users[username]['last_login'] = datetime.now().isoformat()
    save_users(users)
    
    return True, "✅ Вход выполнен!"

# ============================================================================
# УПРАВЛЕНИЕ РЕЗУЛЬТАТАМИ ТЕСТОВ
# ============================================================================
def load_results():
    """Загрузка результатов тестов из JSON"""
    if not os.path.exists(RESULTS_FILE):
        return []
    try:
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_result(user, score, total, correct_count, results, time_used):
    """Сохранение результата теста"""
    result = {
        'user': user,
        'timestamp': datetime.now().isoformat(),
        'score': round(score, 2),
        'total': total,
        'correct': correct_count,
        'time_used': str(time_used),
        'results': results
    }
    all_results = load_results()
    all_results.append(result)
    
    # Обновляем счётчик тестов пользователя
    users = load_users()
    if user in users:
        users[user]['tests_taken'] = users[user].get('tests_taken', 0) + 1
        save_users(users)
    
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

# ============================================================================
# РАСЧЁТ ПРОГРЕССА
# ============================================================================
def calculate_mastery(username):
    """Расчёт прогресса освоения вопросов"""
    all_questions = load_data()
    total_in_db = len(all_questions)
    if total_in_db == 0:
        return 0, 0, 0, []
    
    results = load_results()
    mastered_question_nums = set()
    section_stats = {}
    
    for session in results:
        if session['user'] == username:
            for res in session['results']:
                if res['is_correct']:
                    mastered_question_nums.add(res['num'])
                    q = next((q for q in all_questions if q['num'] == res['num']), None)
                    if q:
                        sec = q['section']
                        if sec not in section_stats:
                            section_stats[sec] = {'correct': 0, 'total': 0}
                        section_stats[sec]['correct'] += 1
    
    for q in all_questions:
        sec = q['section']
        if sec not in section_stats:
            section_stats[sec] = {'correct': 0, 'total': 0}
        section_stats[sec]['total'] += 1
    
    mastered_count = len(mastered_question_nums)
    percent = round((mastered_count / total_in_db) * 100, 1) if total_in_db > 0 else 0
    
    section_progress = []
    for sec, stats in section_stats.items():
        sec_percent = round((stats['correct'] / stats['total']) * 100, 1) if stats['total'] > 0 else 0
        section_progress.append({
            'section': sec,
            'percent': sec_percent,
            'correct': stats['correct'],
            'total': stats['total']
        })
    
    return mastered_count, total_in_db, percent, section_progress

# ============================================================================
# ГЕНЕРАЦИЯ PDF ОТЧЁТА
# ============================================================================
def generate_pdf_report(username, session_data):
    """Генерация PDF отчёта с ошибками"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(f"📊 Отчёт о тестировании", styles['Heading1']))
    elements.append(Paragraph(f"Пользователь: {username}", styles['Normal']))
    elements.append(Paragraph(f"Дата: {session_data['timestamp'][:16]}", styles['Normal']))
    elements.append(Paragraph(f"Результат: {session_data['correct']}/{session_data['total']} ({session_data['score']}%)", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    wrong = [r for r in session_data['results'] if not r['is_correct']]
    if wrong:
        elements.append(Paragraph("❌ Работа над ошибками:", styles['Heading2']))
        data = [['№', 'Вопрос', 'Ваш ответ', 'Правильный ответ']]
        
        questions = {q['num']: q for q in load_data()}
        for res in wrong:
            q = questions.get(res['num'], {})
            user_ans = q['options'][res['answered']-1] if 0 < res['answered'] <= len(q.get('options', [])) else "Не выбран"
            correct_ans = q['options'][q['correct']-1] if 0 < q.get('correct', 0) <= len(q.get('options', [])) else "Н/Д"
            data.append([
                res['num'],
                (q.get('text', '')[:50] + "...") if len(q.get('text', '')) > 50 else q.get('text', ''),
                user_ans[:35] + "..." if len(user_ans) > 35 else user_ans,
                correct_ans[:35] + "..." if len(correct_ans) > 35 else correct_ans
            ])
        
        table = Table(data, colWidths=[40, 180, 130, 130])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("🎉 Ошибок нет! Отличный результат!", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# ============================================================================
# ОТБОР ВОПРОСОВ
# ============================================================================
def get_sampled_questions(questions, mode):
    """Формирование выборки вопросов для теста"""
    if mode == "По 10 из каждого раздела":
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
    return questions.copy()

# ============================================================================
# ИНТЕРФЕЙС АВТОРИЗАЦИИ
# ============================================================================
def show_auth():
    """Отображение формы входа и регистрации"""
    tab1, tab2 = st.tabs(["🔐 Вход", "📝 Регистрация"])
    
    with tab1:
        st.subheader("Вход в систему")
        username = st.text_input("Логин", key="login_user")
        password = st.text_input("Пароль", type="password", key="login_pass")
        if st.button("Войти", key="btn_login", type="primary"):
            success, msg = login_user(username, password)
            if success:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.session_state.is_admin = load_users().get(username, {}).get('is_admin', False)
                st.rerun()
            else:
                st.error(msg)
    
    with tab2:
        st.subheader("Регистрация нового пользователя")
        new_fullname = st.text_input("ФИО полностью *", key="reg_fullname")
        new_user = st.text_input("Придумайте логин *", key="reg_user")
        new_pass = st.text_input("Пароль *", type="password", key="reg_pass")
        confirm = st.text_input("Подтвердите пароль *", type="password", key="reg_confirm")
        
        if st.button("Зарегистрироваться", key="btn_reg", type="primary"):
            if not new_fullname.strip():
                st.error("❌ Укажите ФИО")
            elif not new_user.strip():
                st.error("❌ Укажите логин")
            elif new_pass != confirm:
                st.error("❌ Пароли не совпадают")
            elif len(new_pass) < 4:
                st.error("❌ Пароль слишком короткий (минимум 4 символа)")
            else:
                success, msg = register_user(new_user, new_pass, new_fullname)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)

# ============================================================================
# АДМИН-ПАНЕЛЬ
# ============================================================================
def admin_user_management():
    """Управление пользователями для администратора"""
    st.subheader("👥 Управление пользователями")
    
    users = load_users()
    results = load_results()
    all_questions = load_data()
    
    # Фильтры
    col1, col2 = st.columns(2)
    with col1:
        filter_status = st.radio("Статус:", ["Все", "Активные", "Ожидают"], key="admin_filter_status", horizontal=True)
    with col2:
        search = st.text_input("🔍 Поиск по ФИО или логину", key="admin_search")
    
    # Формируем таблицу данных
    table_data = []
    for username, data in users.items():
        if data.get('is_admin'):
            continue
        
        # Применяем фильтры
        if filter_status == "Активные" and not data.get('is_active'):
            continue
        if filter_status == "Ожидают" and data.get('is_active'):
            continue
        if search and search.lower() not in data.get('fullname', '').lower() and search.lower() not in username.lower():
            continue
        
        # Считаем активность и прогресс
        user_results = [r for r in results if r['user'] == username]
        tests_count = len(user_results)
        last_login = data.get('last_login', '—')
        if last_login and last_login != 'None':
            last_login = last_login[:16]
        
        # Прогресс освоения
        mastered = set()
        for session in user_results:
            for res in session['results']:
                if res['is_correct']:
                    mastered.add(res['num'])
        total_in_db = len(all_questions)
        progress = round((len(mastered) / total_in_db) * 100, 1) if total_in_db > 0 else 0
        
        table_data.append({
            "ФИО": data.get('fullname', 'Не указано'),
            "Логин": username,
            "Статус": "✅ Активен" if data.get('is_active') else "⏳ Ожидает",
            "Зарегистрирован": data.get('registered_at', '—')[:16],
            "Последний вход": last_login,
            "Тестов пройдено": tests_count,
            "Прогресс": f"{progress}%",
            "actions": username
        })
    
    # Отображение таблицы
    if table_data:
        df = pd.DataFrame(table_data)
        st.dataframe(
            df[["ФИО", "Логин", "Статус", "Зарегистрирован", "Последний вход", "Тестов пройдено", "Прогресс"]],
            use_container_width=True,
            hide_index=True
        )
        
        # Кнопки управления
        st.write("### ⚙️ Управление")
        for row in table_data:
            with st.expander(f"👤 {row['ФИО']} ({row['Логин']})"):
                col1, col2, col3 = st.columns([2, 1, 1])
                col1.write(f"**Статус:** {row['Статус']}")
                col1.write(f"**Прогресс:** {row['Прогресс']} | **Тестов:** {row['Тестов пройдено']}")
                
                if not users[row['actions']].get('is_active'):
                    if col2.button("✅ Активировать", key=f"activate_{row['actions']}"):
                        users[row['actions']]['is_active'] = True
                        save_users(users)
                        st.success(f"{row['ФИО']} активирован!")
                        st.rerun()
                
                if col3.button("🗑️ Удалить", key=f"delete_{row['actions']}", type="secondary"):
                    del users[row['actions']]
                    all_results = [r for r in results if r['user'] != row['actions']]
                    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(all_results, f, ensure_ascii=False, indent=2)
                    save_users(users)
                    st.warning(f"{row['ФИО']} удалён")
                    st.rerun()
    else:
        st.info("📭 Нет пользователей для отображения")
    
    # Экспорт данных
    if st.button("📥 Скачать список пользователей (CSV)"):
        if table_data:
            csv = pd.DataFrame(table_data).drop(columns=['actions']).to_csv(index=False, sep=';', encoding='utf-8-sig')
            st.download_button(
                label="📄 Скачать CSV",
                data=csv,
                file_name="users_list.csv",
                mime="text/csv"
            )

# ============================================================================
# ЛИЧНЫЙ КАБИНЕТ ПОЛЬЗОВАТЕЛЯ
# ============================================================================
def user_dashboard():
    """Личный кабинет с прогрессом и историей"""
    username = st.session_state.user
    mastered, total, percent, section_progress = calculate_mastery(username)
    
    # Карточки статистики
    col1, col2, col3 = st.columns(3)
    col1.metric("📚 Освоено вопросов", f"{mastered}/{total}")
    col2.metric("🎯 Общий прогресс", f"{percent}%")
    col3.metric("📊 Тестов пройдено", len([r for r in load_results() if r['user'] == username]))
    
    st.progress(percent / 100)
    
    # Прогресс по разделам
    if section_progress:
        st.subheader("📈 Прогресс по разделам")
        for sec in section_progress:
            st.write(f"**{sec['section']}**: {sec['percent']}% ({sec['correct']}/{sec['total']})")
            st.progress(sec['percent'] / 100)
    
    # История тестов
    st.subheader("📜 История тестов")
    history = [r for r in load_results() if r['user'] == username]
    if history:
        for i, session in enumerate(reversed(history), 1):
            with st.expander(f"Тест #{i} — {session['timestamp'][:16]} — {session['correct']}/{session['total']} ({session['score']}%)"):
                st.write(f"⏱️ Время: {session['time_used']}")
                pdf_data = generate_pdf_report(username, session)
                st.download_button(
                    label="📄 Скачать PDF с ошибками",
                    data=pdf_data,
                    file_name=f"report_{username}_{session['timestamp'][:10]}.pdf",
                    mime="application/pdf",
                    key=f"pdf_{i}"
                )
    else:
        st.info("📭 Пока нет пройденных тестов")

# ============================================================================
# ИНТЕРФЕЙС ТЕСТА
# ============================================================================
def run_test():
    """Прохождение тестирования"""
    st.subheader("🧪 Настройки тестирования")
    
    questions = load_data()
    if not questions:
        st.error("❌ Не удалось загрузить вопросы. Проверьте файл test_teoriya.xlsx")
        return
    
    # Выбор режима
    q_mode = st.radio("Количество вопросов:", ["Все вопросы", "По 10 из каждого раздела"], horizontal=True)
    timer_mode = st.checkbox("⏱️ Тест на время")
    time_limit = 30
    if timer_mode:
        time_limit = st.slider("Лимит времени (минут):", 5, 120, 30)
    
    if st.button("🚀 Начать тест", type="primary"):
        if q_mode == "По 10 из каждого раздела":
            test_questions = get_sampled_questions(questions, "По 10 из каждого раздела")
        else:
            test_questions = questions.copy()
            random.shuffle(test_questions)
        
        st.session_state.test_questions = test_questions
        st.session_state.current_index = 0
        st.session_state.answers = []
        st.session_state.test_start_time = datetime.now()
        st.session_state.timer_mode = timer_mode
        st.session_state.time_limit = time_limit
        st.session_state.in_test = True
        st.rerun()
    
    # Если тест уже идёт
    if st.session_state.get('in_test', False):
        test_questions = st.session_state.test_questions
        idx = st.session_state.current_index
        
        # Таймер
        if st.session_state.timer_mode:
            elapsed = datetime.now() - st.session_state.test_start_time
            remaining = st.session_state.time_limit * 60 - elapsed.total_seconds()
            if remaining <= 0:
                st.warning("⏰ Время вышло! Тест завершён автоматически.")
                finish_test()
                return
            mins, secs = divmod(int(remaining), 60)
            st.metric("⏱️ Осталось времени", f"{mins}:{secs:02d}")
            if remaining < 300:
                st.warning("⚠️ Осталось мало времени!")
        
        # Вопрос
        q = test_questions[idx]
        st.progress((idx + 1) / len(test_questions))
        st.write(f"### Вопрос {idx + 1} из {len(test_questions)}")
        st.write(f"**{q['num']}**. {q['text']}")
        
        # Варианты ответов
        answer = st.radio("Выберите ответ:", q['options'], key=f"q_{idx}", index=None)
        
        col1, col2 = st.columns(2)
        if idx > 0 and col1.button("⬅️ Назад"):
            st.session_state.current_index -= 1
            st.rerun()
        
        if idx < len(test_questions) - 1:
            if col2.button("Далее ➡️", type="primary"):
                if answer:
                    selected_idx = q['options'].index(answer) + 1
                    st.session_state.answers.append({
                        'num': q['num'],
                        'answered': selected_idx,
                        'is_correct': (selected_idx == q['correct'])
                    })
                    st.session_state.current_index += 1
                    st.rerun()
                else:
                    st.warning("⚠️ Выберите вариант ответа")
        else:
            if col2.button("✅ Завершить тест", type="primary"):
                if answer:
                    selected_idx = q['options'].index(answer) + 1
                    st.session_state.answers.append({
                        'num': q['num'],
                        'answered': selected_idx,
                        'is_correct': (selected_idx == q['correct'])
                    })
                    finish_test()
                else:
                    st.warning("⚠️ Выберите вариант ответа")

def finish_test():
    """Завершение теста и сохранение результатов"""
    username = st.session_state.user
    answers = st.session_state.answers
    start_time = st.session_state.test_start_time
    time_used = datetime.now() - start_time
    
    correct_count = sum(1 for a in answers if a['is_correct'])
    total = len(answers)
    score = round((correct_count / total) * 100, 1) if total > 0 else 0
    
    save_result(username, score, total, correct_count, answers, time_used)
    
    st.success(f"🎉 Тест завершён! Результат: {correct_count}/{total} ({score}%)")
    
    # Показать ошибки
    wrong = [a for a in answers if not a['is_correct']]
    if wrong:
        st.subheader("❌ Ошибки:")
        questions = {q['num']: q for q in load_data()}
        for a in wrong:
            q = questions.get(a['num'], {})
            st.write(f"**{a['num']}**. {q.get('text', '')[:100]}...")
            st.write(f"   Ваш ответ: вариант {a['answered']} | Правильный: вариант {q.get('correct', '?')}")
    
    # Кнопка скачивания PDF
    session_data = {
        'user': username,
        'timestamp': datetime.now().isoformat(),
        'score': score,
        'total': total,
        'correct': correct_count,
        'time_used': str(time_used),
        'results': answers
    }
    pdf_data = generate_pdf_report(username, session_data)
    st.download_button(
        label="📄 Скачать полный отчёт (PDF)",
        data=pdf_data,
        file_name=f"report_{username}_{datetime.now().strftime('%Y-%m-%d')}.pdf",
        mime="application/pdf"
    )
    
    # Сброс
    st.session_state.in_test = False
    st.session_state.test_questions = []
    st.session_state.answers = []
    
    if st.button("🏠 Вернуться в личный кабинет"):
        st.rerun()

# ============================================================================
# ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ============================================================================
def main():
    """Основная функция приложения"""
    st.set_page_config(page_title="🏢 Тест: Оценка недвижимости", page_icon="📚", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.session_state.update(logged_in=False, user=None, is_admin=False, in_test=False)
    
    st.title("🏢 Тестирование: Оценка недвижимости")
    
    if not st.session_state.logged_in:
        show_auth()
    else:
        # Боковая панель
        with st.sidebar:
            st.write(f"👤 **{st.session_state.user}**")
            users = load_users()
            fullname = users.get(st.session_state.user, {}).get('fullname', '')
            if fullname:
                st.write(f"📛 {fullname}")
            if st.session_state.is_admin:
                st.write("🔑 Роль: Администратор")
            if st.button("🚪 Выйти"):
                for k in list(st.session_state.keys()):
                    if k not in ['logged_in', 'user', 'is_admin']:
                        del st.session_state[k]
                st.session_state.logged_in = False
                st.rerun()
        
        # Вкладки
        if st.session_state.is_admin:
            tab1, tab2, tab3 = st.tabs(["🧪 Пройти тест", "🔐 Админ-панель", "📊 Мой прогресс"])
            with tab1:
                run_test()
            with tab2:
                admin_user_management()
            with tab3:
                user_dashboard()
        else:
            tab1, tab2 = st.tabs(["🧪 Пройти тест", "📊 Мой прогресс"])
            with tab1:
                run_test()
            with tab2:
                user_dashboard()

if __name__ == "__main__":
    main()