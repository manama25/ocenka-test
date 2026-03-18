# app.py - ПОЛНАЯ ВЕРСИЯ ДЛЯ НЕ-ПРОГРАММИСТОВ
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

# --- Настройки ---
DATA_FILE = 'test_teoriya.xlsx'
USERS_FILE = 'users.json'
RESULTS_FILE = 'results.json'

# --- Загрузка данных из Excel ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel(DATA_FILE, sheet_name='теория', engine='openpyxl')
    except Exception as e:
        st.error(f"❌ Ошибка загрузки Excel: {e}")
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
            continue
            
        question = {
            'num': str(row['Номер вопроса']),
            'text': str(row['Текст вопроса']).strip(),
            'options': options,
            'correct': correct_idx,
            'section': str(row['Раздел']).strip()
        }
        questions.append(question)
    return questions

# --- Управление пользователями ---
def load_users():
    if not os.path.exists(USERS_FILE):
        default_users = {
            "admin": {"hash": hashlib.sha256("admin123".encode()).hexdigest(), "is_active": True, "is_admin": True}
        }
        save_users(default_users)
        return default_users
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return load_users()

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password):
    users = load_users()
    if username in users:
        return False, "❌ Логин уже занят"
    users[username] = {
        "hash": hash_password(password),
        "is_active": False,  # 🔴 Требует подтверждения админа!
        "is_admin": False,
        "registered_at": datetime.now().isoformat()
    }
    save_users(users)
    return True, "✅ Регистрация отправлена. Ожидайте подтверждения администратора!"

def login_user(username, password):
    users = load_users()
    if username not in users:
        return False, "❌ Пользователь не найден"
    user = users[username]
    if user["hash"] != hash_password(password):
        return False, "❌ Неверный пароль"
    if not user.get("is_active", False) and not user.get("is_admin", False):
        return False, "⏳ Аккаунт ожидает подтверждения администратора"
    return True, "✅ Вход выполнен!"

# --- Расчет прогресса ---
def calculate_mastery(username):
    all_questions = load_data()
    total_in_db = len(all_questions)
    if total_in_db == 0:
        return 0, 0, 0
    
    results = load_results()
    mastered_question_nums = set()
    
    for session in results:
        if session['user'] == username:
            for res in session['results']:
                if res['is_correct']:
                    mastered_question_nums.add(res['num'])
    
    mastered_count = len(mastered_question_nums)
    percent = round((mastered_count / total_in_db) * 100, 1) if total_in_db > 0 else 0
    return mastered_count, total_in_db, percent

# --- Генерация PDF ---
def generate_pdf_report(username, session_data):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(f"📊 Отчёт о тестировании", styles['Heading1']))
    elements.append(Paragraph(f"Пользователь: {username}", styles['Normal']))
    elements.append(Paragraph(f"Дата: {session_data['timestamp'][:16]}", styles['Normal']))
    elements.append(Paragraph(f"Результат: {session_data['correct']}/{session_data['total']} ({session_data['score']:.1f}%)", styles['Normal']))
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

# --- Результаты ---
def load_results():
    if not os.path.exists(RESULTS_FILE):
        return []
    try:
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_result(user, score, total, correct_count, results, time_used):
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
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

# --- Отбор вопросов ---
def get_sampled_questions(questions, mode):
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

# --- Авторизация ---
def show_auth():
    tab1, tab2 = st.tabs(["🔐 Вход", "📝 Регистрация"])
    with tab1:
        username = st.text_input("Логин", key="login_user")
        password = st.text_input("Пароль", type="password", key="login_pass")
        if st.button("Войти", key="btn_login"):
            success, msg = login_user(username, password)
            if success:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.session_state.is_admin = load_users().get(username, {}).get('is_admin', False)
                st.rerun()
            else:
                st.error(msg)
    
    with tab2:
        new_user = st.text_input("Придумайте логин", key="reg_user")
        new_pass = st.text_input("Пароль", type="password", key="reg_pass")
        confirm = st.text_input("Подтвердите пароль", type="password", key="reg_confirm")
        if st.button("Зарегистрироваться", key="btn_reg"):
            if new_pass != confirm:
                st.error("❌ Пароли не совпадают")
            elif len(new_pass) < 4:
                st.error("❌ Пароль слишком короткий (минимум 4 символа)")
            else:
                success, msg = register_user(new_user, new_pass)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)

# --- Админ-панель ---
def admin_user_management():
    st.subheader("👥 Подтверждение пользователей")
    users = load_users()
    pending = {u: d for u, d in users.items() if not d.get('is_active') and not d.get('is_admin')}
    
    if not pending:
        st.info("✅ Нет пользователей, ожидающих подтверждения")
    else:
        for username, data in pending.items():
            col1, col2, col3 = st.columns([3, 2, 1])
            col1.write(f"👤 **{username}**")
            col2.write(f"📅 {data.get('registered_at', 'N/A')[:16]}")
            if col3.button("✅ Подтвердить", key=f"approve_{username}"):
                users[username]['is_active'] = True
                save_users(users)
                st.success(f"{username} активирован!")
                st.rerun()
            if col3.button("🗑️ Удалить", key=f"reject_{username}"):
                del users[username]
                save_users(users)
                st.warning(f"{username} удалён")
                st.rerun()

# --- Личный кабинет ---
def user_dashboard():
    username = st.session_state.user
    mastered, total, percent = calculate_mastery(username)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📚 Освоено вопросов", f"{mastered}/{total}")
    col2.metric("🎯 Доля освоения", f"{percent}%")
    col3.metric("📊 Всего тестов", len([r for r in load_results() if r['user'] == username]))
    
    st.progress(percent / 100)
    
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
                    mime="application/pdf"
                )
    else:
        st.info("📭 Пока нет пройденных тестов")

# --- Интерфейс теста ---
def run_test():
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
        # Формируем вопросы
        if q_mode == "По 10 из каждого раздела":
            test_questions = get_sampled_questions(questions, "По 10 из каждого раздела")
        else:
            test_questions = questions.copy()
            random.shuffle(test_questions)
        
        # Сохраняем в сессию
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
            if remaining < 300:  # меньше 5 минут
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

# --- Главное приложение ---
def main():
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
