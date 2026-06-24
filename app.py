import pandas as pd
import streamlit as st

WORD_COLUMNS = ["eng", "kor"]

st.set_page_config(page_title="영단어 퀴즈", page_icon="📘")


def clean_words(df):
    df = df.dropna(subset=WORD_COLUMNS).copy()
    df[WORD_COLUMNS] = df[WORD_COLUMNS].apply(lambda col: col.astype(str).str.strip())
    df = df[(df["eng"] != "") & (df["kor"] != "")]

    duplicate_key = df["eng"].str.casefold()
    df = df.loc[~duplicate_key.duplicated()]

    return df.reset_index(drop=True)


def load_all_days(uploaded_file):
    raw = pd.read_excel(uploaded_file, header=None)
    days = {}

    for col in range(0, raw.shape[1] - 1, 2):
        header = raw.iat[0, col]

        if pd.isna(header) or not str(header).strip():
            day_name = f"day{col // 2 + 1}"
        else:
            day_name = str(header).strip()

        day_df = raw.iloc[1:, [col, col + 1]].copy()
        day_df.columns = WORD_COLUMNS
        day_df = clean_words(day_df)

        if not day_df.empty:
            days[day_name] = day_df

    return days


def split_answers(text):
    return {
        item.strip()
        for item in str(text).replace("，", ",").split(",")
        if item.strip()
    }


def init_state():
    if "df" not in st.session_state:
        st.session_state.df = pd.DataFrame(columns=WORD_COLUMNS)
        st.session_state.quiz_source = pd.DataFrame(columns=WORD_COLUMNS)
        st.session_state.current_day_name = ""
        st.session_state.current_index = 0
        st.session_state.correct_count = 0
        st.session_state.answered = False
        st.session_state.wrong_words = []
        st.session_state.result = None
        st.session_state.input_clear_count = 0


def reset_quiz(day_name, df):
    st.session_state.current_day_name = day_name
    st.session_state.quiz_source = df.copy().reset_index(drop=True)
    st.session_state.df = df.sample(frac=1).reset_index(drop=True)
    st.session_state.current_index = 0
    st.session_state.correct_count = 0
    st.session_state.answered = False
    st.session_state.wrong_words = []
    st.session_state.result = None
    st.session_state.input_clear_count = 0


def next_question():
    st.session_state.current_index += 1
    st.session_state.answered = False
    st.session_state.result = None
    st.session_state.input_clear_count += 1


def check_answer(answer):
    answer = answer.strip()

    if not answer:
        st.session_state.result = ("답을 입력해 주세요.", "info")
        return

    row = st.session_state.df.iloc[st.session_state.current_index]
    korean = str(row["kor"]).strip()

    user_answers = split_answers(answer)
    correct_answers = split_answers(korean)

    if user_answers and user_answers.issubset(correct_answers):
        st.session_state.correct_count += 1
        st.session_state.result = (f"정답 · {korean}", "success")
    else:
        st.session_state.wrong_words.append({"eng": row["eng"], "kor": row["kor"]})
        st.session_state.result = (f"오답 · {korean}", "error")

    st.session_state.answered = True


init_state()

st.title("📘 영단어 퀴즈")

uploaded_file = st.file_uploader("엑셀 파일을 업로드하세요", type=["xlsx"])

if uploaded_file is None:
    st.info("word.xlsx 파일을 업로드하면 Day 선택 화면이 나옵니다.")
    st.stop()

try:
    days = load_all_days(uploaded_file)
except Exception as e:
    st.error(f"엑셀 파일을 불러오는 중 오류가 발생했습니다.\n\n{e}")
    st.stop()

if not days:
    st.error("불러온 단어가 없습니다. 엑셀 구조를 확인하세요.")
    st.stop()


if st.session_state.current_day_name == "":
    st.subheader("학습할 Day를 선택하세요")

    day_names = list(days.keys())

    for i in range(0, len(day_names), 3):
        cols = st.columns(3)

        for col, day_name in zip(cols, day_names[i:i + 3]):
            with col:
                if st.button(
                    f"{day_name}\n\n{len(days[day_name])}단어",
                    use_container_width=True,
                ):
                    reset_quiz(day_name, days[day_name])
                    st.rerun()

    st.divider()

    all_words = clean_words(pd.concat(days.values(), ignore_index=True))

    if st.button(
        f"전체 Day 학습\n\n{len(all_words)}단어",
        use_container_width=True,
    ):
        reset_quiz("전체 Day", all_words)
        st.rerun()

    st.caption("엑셀 오른쪽에 두 열씩 day3, day4를 추가하면 자동으로 Day가 추가됩니다.")

else:
    df = st.session_state.df
    index = st.session_state.current_index

    if index >= len(df):
        total = len(df)
        correct = st.session_state.correct_count
        wrong = len(st.session_state.wrong_words)
        accuracy = correct / total * 100 if total else 0

        st.subheader("퀴즈 완료")
        st.write(f"{total}문제 중 {correct}문제를 맞혔습니다.")
        st.write(f"정답률: **{accuracy:.1f}%**")
        st.write(f"틀린 문제: **{wrong}개**")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("같은 문제 다시 풀기", use_container_width=True):
                reset_quiz(
                    st.session_state.current_day_name,
                    st.session_state.quiz_source,
                )
                st.rerun()

        with col2:
            if st.button(
                "틀린 문제 다시 풀기",
                use_container_width=True,
                disabled=wrong == 0,
            ):
                wrong_df = pd.DataFrame(st.session_state.wrong_words)
                reset_quiz("틀린 문제 복습", wrong_df)
                st.rerun()

        with col3:
            if st.button("메인 화면", use_container_width=True):
                st.session_state.current_day_name = ""
                st.session_state.result = None
                st.rerun()

    else:
        row = df.iloc[index]

        top_col1, top_col2, top_col3 = st.columns([1, 2, 1])

        with top_col1:
            if st.button("메인 화면"):
                st.session_state.current_day_name = ""
                st.session_state.result = None
                st.rerun()

        with top_col2:
            st.markdown(
                f"<h4 style='text-align:center'>{st.session_state.current_day_name}</h4>",
                unsafe_allow_html=True,
            )

        with top_col3:
            st.write(f"{index + 1} / {len(df)}")

        st.divider()

        st.markdown(
            f"<h1 style='text-align:center'>{row['eng']}</h1>",
            unsafe_allow_html=True,
        )

        form_key = (
            f"quiz_form_{index}_"
            f"{st.session_state.answered}_"
            f"{st.session_state.input_clear_count}"
        )

        with st.form(key=form_key):
            answer = st.text_input(
                "뜻을 입력하세요",
                disabled=st.session_state.answered,
            )

            submitted = st.form_submit_button(
                "다음 문제" if st.session_state.answered else "정답 확인",
                use_container_width=True,
            )

        if submitted:
            if st.session_state.answered:
                next_question()
                st.rerun()
            else:
                check_answer(answer)
                st.rerun()

        if st.session_state.result:
            message, kind = st.session_state.result

            if kind == "success":
                st.success(message)
            elif kind == "error":
                st.error(message)
            else:
                st.info(message)

        st.write(f"정답 {st.session_state.correct_count}개")
